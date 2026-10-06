"""[C-01] 不可变消息 DTO；字段名与接口规范、Java record 保持一致。

这里不实现字节编码或业务校验。范围和报文合法性检查归 C-02；调用状态检查归
C-04/C-05。Python float 并不自动保证 binary32，必须在 codec 中显式转换。
"""

from dataclasses import dataclass
from typing import Optional, Union
from uuid import UUID

from .protocol import MessageType, Semantics, Status


@dataclass(frozen=True, slots=True)
class Header:
    """reserved 固定为 0，由 codec 写入；它不需要成为可变 DTO 字段。"""

    version: int
    messageType: MessageType
    operation: int
    clientSessionId: UUID
    requestId: int
    status: Status
    semantics: Semantics
    bodyLength: int


@dataclass(frozen=True, slots=True)
class RequestKey:
    """同一个逻辑请求的所有重传都保持该键不变。"""

    clientSessionId: UUID
    requestId: int


@dataclass(frozen=True, slots=True)
class FlightTime:
    """UTC+8，五个 i32；秒固定为 0，不能改成时间字符串传输。"""

    year: int
    month: int
    day: int
    hour: int
    minute: int


@dataclass(frozen=True, slots=True)
class RouteQuery:
    """操作 1：出发地和目的地是两个独立的长度前缀字符串。"""

    source: str
    destination: str


@dataclass(frozen=True, slots=True)
class FlightQuery:
    """操作 2：查询一个航班。"""

    flightId: int


@dataclass(frozen=True, slots=True)
class Reservation:
    """操作 3：quantity 是订座数量，不是期望剩余座位数。"""

    flightId: int
    quantity: int


@dataclass(frozen=True, slots=True)
class MonitorRegistration:
    """操作 4：请求时长使用秒；回复剩余时长使用毫秒。"""

    flightId: int
    durationSeconds: int


@dataclass(frozen=True, slots=True)
class SetAirfare:
    """操作 5：幂等地设置绝对票价。"""

    flightId: int
    newPrice: float


@dataclass(frozen=True, slots=True)
class IncreaseAirfare:
    """操作 6：非幂等地增加票价，delta 必须为正的有限 binary32。"""

    flightId: int
    delta: float


RequestBody = Union[
    RouteQuery, FlightQuery, Reservation, MonitorRegistration, SetAirfare, IncreaseAirfare
]


@dataclass(frozen=True, slots=True)
class Request:
    """仅为逻辑消息对象；发送前由 protocol_codec 编成 bytes。"""

    header: Header
    body: RequestBody


@dataclass(frozen=True, slots=True)
class RouteResult:
    """count 由元组长度导出，线上不能重复写两次列表数量。"""

    flightIds: tuple[int, ...]

    def __post_init__(self) -> None:
        # 即使调用方传入 list，也保存不可变快照。
        object.__setattr__(self, "flightIds", tuple(self.flightIds))


@dataclass(frozen=True, slots=True)
class FlightDetails:
    """28 字节成功体，不额外包含 flightId。"""

    departure: FlightTime
    airfare: float
    availableSeats: int


@dataclass(frozen=True, slots=True)
class ReservationResult:
    """余座是本次执行后的快照；重放不重新查询业务状态。"""

    flightId: int
    availableSeats: int


@dataclass(frozen=True, slots=True)
class MonitorResult:
    """remainingMillis=0 表示原登记已没有有效时间。"""

    flightId: int
    remainingMillis: int


@dataclass(frozen=True, slots=True)
class FareResult:
    """操作 5/6 共用成功体，返回总票价而非增加金额。"""

    flightId: int
    airfare: float


@dataclass(frozen=True, slots=True)
class ErrorBody:
    """错误码仅放在 Header.status，不在错误体重复编码。"""

    message: str


ReplyBody = Union[
    RouteResult, FlightDetails, ReservationResult, MonitorResult, FareResult, ErrorBody
]


@dataclass(frozen=True, slots=True)
class Response:
    """status 非零时 body 必须是 ErrorBody，待 C-02 验证。"""

    status: Status
    body: ReplyBody


@dataclass(frozen=True, slots=True)
class Reply:
    """Header.status 必须等于 response.status。"""

    header: Header
    response: Response


@dataclass(frozen=True, slots=True)
class CallbackMessage:
    """头部关联监控注册 ID，而非触发更新的订座 ID。"""

    header: Header
    flightId: int
    availableSeats: int
    updateSequence: int


@dataclass(frozen=True, slots=True)
class CallOutcome:
    """调用结果；超时时不声称服务器未执行。状态不变量归 C-04。"""

    request_key: RequestKey
    reply: Optional[Reply]
    attempts: int
    timed_out: bool
    pending_callback: Optional[CallbackMessage]
    reply_received_at: Optional[float]


@dataclass(frozen=True, slots=True)
class AcceptedMonitor:
    """deadline_monotonic 是本机秒计时值，不通过网络发送。"""

    request_key: RequestKey
    flight_id: int
    deadline_monotonic: float
    pending_callback: Optional[CallbackMessage]
