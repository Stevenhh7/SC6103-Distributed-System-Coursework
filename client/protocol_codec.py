"""[C-02] v1 手工编解码；struct 仅转换单个 binary32，不打包整条消息。"""

from datetime import datetime
import math
import struct
from typing import Union
from uuid import UUID

from .models import (
    CallbackMessage, ErrorBody, FareResult, FlightDetails, FlightQuery, FlightTime,
    Header, IncreaseAirfare, MonitorRegistration, MonitorResult, Reply, Request,
    RequestBody, Reservation, ReservationResult, Response, RouteQuery, RouteResult,
    SetAirfare,
)
from .protocol import (
    HEADER_BYTES, MAX_BODY_BYTES, MAX_ERROR_UTF8_BYTES, MAX_FLIGHTS,
    MAX_LOCATION_UTF8_BYTES, MAX_MESSAGE_BYTES, MAX_MONITOR_SECONDS, MAX_REQUEST_ID,
    MessageType, Operation, Semantics, Status, VERSION,
)


class ProtocolError(ValueError):
    """畸形报文/不可表示的输入；服务端业务失败仍解码成普通 Reply。"""


def _integer(value: int, size: int, *, signed: bool = True) -> bytes:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProtocolError("integer field must be an int")
    try:
        return value.to_bytes(size, "big", signed=signed)
    except OverflowError as exc:
        raise ProtocolError(f"integer outside {size * 8}-bit range") from exc


def to_binary32(value: float) -> float:
    """先舍入到线上 float32；调用方再校验正数/非负等业务范围。"""
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ProtocolError("price must be a number")
    try:
        rounded = struct.unpack(">f", struct.pack(">f", value))[0]
    except (OverflowError, struct.error) as exc:
        raise ProtocolError("price exceeds binary32 range") from exc
    if not math.isfinite(rounded):
        raise ProtocolError("price must be finite (no NaN/Infinity)")
    return rounded


def _string(value: str) -> bytes:
    if not isinstance(value, str):
        raise ProtocolError("location must be a string")
    try:
        raw = value.encode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ProtocolError("invalid UTF-8 input") from exc
    if len(raw) > MAX_LOCATION_UTF8_BYTES:
        raise ProtocolError("location exceeds 128 UTF-8 bytes")
    # 空串在表示层合法；菜单/B 的业务层负责非空校验和 U+0020 修剪。
    return _integer(len(raw), 4) + raw


def _request_body(operation: int, body: RequestBody) -> bytes:
    expected = {
        Operation.QUERY_ROUTE: RouteQuery, Operation.QUERY_FLIGHT: FlightQuery,
        Operation.RESERVE_SEATS: Reservation, Operation.MONITOR_SEATS: MonitorRegistration,
        Operation.SET_AIRFARE: SetAirfare, Operation.INCREASE_AIRFARE: IncreaseAirfare,
    }
    if operation not in expected or not isinstance(body, expected[operation]):
        raise ProtocolError("operation and request body type do not match")
    if isinstance(body, RouteQuery):
        return _string(body.source) + _string(body.destination)
    result = _integer(body.flightId, 4)
    if isinstance(body, Reservation):
        result += _integer(body.quantity, 4)
    elif isinstance(body, MonitorRegistration):
        result += _integer(body.durationSeconds, 4)
    elif isinstance(body, (SetAirfare, IncreaseAirfare)):
        value = body.newPrice if isinstance(body, SetAirfare) else body.delta
        result += struct.pack(">f", to_binary32(value))
    return result


def request_body_length(operation: int, body: RequestBody) -> int:
    """本地组装 Header 的辅助函数，不改变公开 Request DTO。"""
    return len(_request_body(operation, body))


def encode_request(request: Request) -> bytes:
    """校验头部与体的一致性；业务非法的 i32 值仍可供错误用例发送。"""
    h = request.header
    body = _request_body(h.operation, request.body)
    if h.version != VERSION or h.messageType != MessageType.REQUEST or h.status != Status.OK:
        raise ProtocolError("invalid request version/type/status")
    if not isinstance(h.clientSessionId, UUID) or h.clientSessionId.int == 0:
        raise ProtocolError("session must be a nonzero UUID")
    if not 1 <= h.requestId <= MAX_REQUEST_ID or h.semantics not in tuple(Semantics):
        raise ProtocolError("invalid request ID or semantics")
    if h.bodyLength != len(body) or len(body) > MAX_BODY_BYTES:
        raise ProtocolError("bodyLength does not match encoded body")
    header = (
        _integer(h.version, 1, signed=False)
        + _integer(h.messageType, 1, signed=False)
        + _integer(h.operation, 2, signed=False)
        + h.clientSessionId.bytes
        + _integer(h.requestId, 4)
        + _integer(h.status, 2, signed=False)
        + _integer(h.semantics, 1, signed=False)
        + b"\x00"
        + _integer(h.bodyLength, 4)
    )
    return header + body


class _Reader:
    """所有字段先检查剩余长度；finish 拒绝任何未消费尾字节。"""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.offset = 0

    def take(self, size: int) -> bytes:
        if size < 0 or size > len(self.data) - self.offset:
            raise ProtocolError("truncated field or invalid length")
        value = self.data[self.offset:self.offset + size]
        self.offset += size
        return value

    def integer(self, size: int = 4, *, signed: bool = True) -> int:
        return int.from_bytes(self.take(size), "big", signed=signed)

    def bounded(self, minimum: int, maximum: int = MAX_REQUEST_ID) -> int:
        value = self.integer()
        if not minimum <= value <= maximum:
            raise ProtocolError("integer field outside allowed range")
        return value

    def fare(self) -> float:
        value = struct.unpack(">f", self.take(4))[0]
        if not math.isfinite(value) or value < 0 or (value == 0 and math.copysign(1, value) < 0):
            raise ProtocolError("invalid airfare in successful reply")
        return value

    def error_string(self) -> str:
        size = self.bounded(1, MAX_ERROR_UTF8_BYTES)
        try:
            return self.take(size).decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ProtocolError("invalid UTF-8 in error message") from exc

    def finish(self) -> None:
        if self.offset != len(self.data):
            raise ProtocolError("unexpected trailing bytes")


def decode_message(data: bytes) -> Union[Reply, CallbackMessage]:
    """解码完整 REPLY/CALLBACK；未知操作仅允许使用统一错误体。"""
    if not isinstance(data, bytes) or not HEADER_BYTES <= len(data) <= MAX_MESSAGE_BYTES:
        raise ProtocolError("datagram size must be 32..1024 bytes")
    reader = _Reader(data)
    version = reader.integer(1, signed=False)
    try:
        kind = MessageType(reader.integer(1, signed=False))
        operation = reader.integer(2, signed=False)
        session = UUID(bytes=reader.take(16))
        request_id = reader.bounded(1)
        status = Status(reader.integer(2, signed=False))
        semantics = Semantics(reader.integer(1, signed=False))
    except ValueError as exc:
        raise ProtocolError("invalid header enum or identity") from exc
    reserved = reader.integer(1, signed=False)
    length = reader.integer()
    if version != VERSION or session.int == 0 or reserved != 0:
        raise ProtocolError("unsupported version, zero session or reserved byte")
    if length != len(data) - HEADER_BYTES:
        raise ProtocolError("bodyLength does not match datagram")
    header = Header(version, kind, operation, session, request_id, status, semantics, length)
    if kind == MessageType.CALLBACK:
        if operation != Operation.MONITOR_SEATS or status != Status.OK or length != 12:
            raise ProtocolError("invalid callback header")
        callback = CallbackMessage(header, reader.bounded(1), reader.bounded(0), reader.bounded(1))
        reader.finish()
        return callback
    if kind != MessageType.REPLY:
        raise ProtocolError("client cannot accept REQUEST messages")
    if status != Status.OK:
        body = ErrorBody(reader.error_string())
    elif operation == Operation.QUERY_ROUTE:
        count = reader.bounded(1, MAX_FLIGHTS)
        ids = tuple(reader.bounded(1) for _ in range(count))
        if any(left >= right for left, right in zip(ids, ids[1:])):
            raise ProtocolError("route IDs must be unique and ascending")
        body = RouteResult(ids)
    elif operation == Operation.QUERY_FLIGHT:
        departure = FlightTime(*(reader.integer() for _ in range(5)))
        try:
            datetime(departure.year, departure.month, departure.day, departure.hour, departure.minute)
        except ValueError as exc:
            raise ProtocolError("invalid departure date/time") from exc
        body = FlightDetails(departure, reader.fare(), reader.bounded(0))
    elif operation == Operation.RESERVE_SEATS:
        body = ReservationResult(reader.bounded(1), reader.bounded(0))
    elif operation == Operation.MONITOR_SEATS:
        body = MonitorResult(reader.bounded(1), reader.bounded(0, MAX_MONITOR_SECONDS * 1000))
    elif operation in (Operation.SET_AIRFARE, Operation.INCREASE_AIRFARE):
        body = FareResult(reader.bounded(1), reader.fare())
    else:
        raise ProtocolError("unknown operation in successful reply")
    reader.finish()
    return Reply(header, Response(status, body))
