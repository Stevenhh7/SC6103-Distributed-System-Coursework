"""[C-04] 单线程调用层：一次编码、稳定身份、绝对截止时间、有限重传。"""

import socket
import time
from dataclasses import asdict
from typing import Optional, Union
from uuid import uuid4

from .config import ClientConfig
from .event_log import record
from .loss_simulator import LossSimulator
from .models import (
    CallbackMessage, CallOutcome, Header, MonitorRegistration, MonitorResult, Reply,
    Request, RequestBody, RequestKey,
)
from .protocol import MAX_REQUEST_ID, MessageType, Operation, Status, VERSION
from .protocol_codec import ProtocolError, decode_message, encode_request, request_body_length
from .udp_transport import UdpTransport


class SessionExhaustedError(RuntimeError):
    """不能回绕 ID；退出当前客户端后以新的 UUID 启动。"""


class Invoker:
    """菜单、实验、监控共用同一传输对象；构造与 --check 不访问网络。"""

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self.session_id = config.session_id or uuid4()
        self.next_request_id = 1
        self.transport = UdpTransport(config)
        self.loss_simulator = LossSimulator(config.drop_first_request)

    def log(self, event: str, key: RequestKey, operation: int, **fields: object) -> None:
        record(event, mode=self.config.semantics.name, sessionId=str(key.clientSessionId),
               requestId=key.requestId, operation=int(operation),
               peer=self.transport.server_endpoint, **fields)

    def receive_message(self, timeout_ms: float) -> tuple[Optional[Union[Reply, CallbackMessage]], float]:
        """共享来源/格式检查；无效报文交回循环，调用者继续按原 deadline 等待。"""
        datagram = self.transport.receive(timeout_ms)
        if datagram.peer != self.transport.server_endpoint:
            record("IGNORE_SOURCE", peer=datagram.peer, expected=self.transport.server_endpoint)
            return None, time.monotonic()
        try:
            message = decode_message(datagram.data)
        except ProtocolError as exc:
            record("IGNORE_MALFORMED", peer=datagram.peer, reason=str(exc))
            return None, time.monotonic()
        return message, time.monotonic()

    def matches_callback(self, message: CallbackMessage, key: RequestKey, flight_id: int) -> bool:
        h = message.header
        return (
            h.clientSessionId == key.clientSessionId
            and h.requestId == key.requestId
            and h.operation == Operation.MONITOR_SEATS
            and h.semantics == self.config.semantics
            and message.flightId == flight_id
        )

    def invoke(self, operation: int, body: RequestBody) -> CallOutcome:
        """成功/业务错误返回 Reply；耗尽返回结果未知，绝不创建新 ID 重做写操作。"""
        if self.next_request_id > MAX_REQUEST_ID:
            raise SessionExhaustedError("requestId 已用尽；请退出并以新的 session UUID 重启客户端")
        key = RequestKey(self.session_id, self.next_request_id)
        header = Header(VERSION, MessageType.REQUEST, operation, self.session_id,
                        key.requestId, Status.OK, self.config.semantics,
                        request_body_length(operation, body))
        payload = encode_request(Request(header, body))
        # 编码失败尚未占用 ID；分配后即使网络异常也不再复用。
        self.next_request_id += 1
        self.transport.open()
        self.log("REQUEST_CREATED", key, operation, body=asdict(body), encodedHex=payload.hex(),
                 timeoutMs=self.config.timeout_ms, maxAttempts=self.config.max_attempts)
        pending: Optional[CallbackMessage] = None
        for attempt in range(1, self.config.max_attempts + 1):
            deadline = time.monotonic() + self.config.timeout_ms / 1000.0
            if self.loss_simulator.should_drop_request(key, attempt):
                self.log("DROP_REQUEST", key, operation, attempt=attempt)
            else:
                try:
                    self.transport.send(payload)
                except socket.timeout:
                    # 发送超时也消耗本次尝试；保留原 ID/字节，继续等剩余时间。
                    # 即使不能确认是否已交给网络，也不能换 ID 再做一次业务。
                    self.log("SEND_TIMEOUT", key, operation, attempt=attempt)
                except (ConnectionResetError, ConnectionRefusedError) as exc:
                    self.log("NETWORK_NOTICE", key, operation, attempt=attempt, reason=str(exc))
                else:
                    self.log("SEND", key, operation, attempt=attempt, bytes=len(payload))
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    message, received_at = self.receive_message(remaining * 1000.0)
                except socket.timeout:
                    break
                except (ConnectionResetError, ConnectionRefusedError) as exc:
                    # ICMP 不确认业务是否执行；保留本次 deadline 和原请求身份。
                    self.log("NETWORK_NOTICE", key, operation, attempt=attempt, reason=str(exc))
                    continue
                if received_at >= deadline:
                    break
                if message is None:
                    continue
                if isinstance(message, CallbackMessage):
                    if isinstance(body, MonitorRegistration) and self.matches_callback(message, key, body.flightId):
                        if pending is None or message.updateSequence > pending.updateSequence:
                            pending = message
                            self.log("PENDING_CALLBACK", key, operation, attempt=attempt,
                                     flightId=message.flightId, sequence=message.updateSequence)
                    else:
                        self.log("IGNORE_CALLBACK", key, operation, attempt=attempt)
                    continue
                h = message.header
                if (h.clientSessionId != key.clientSessionId or h.requestId != key.requestId
                        or h.operation != operation or h.semantics != self.config.semantics):
                    self.log("IGNORE_REPLY", key, operation, attempt=attempt)
                    continue
                result = message.response.body
                # 成功体若带 ID，必须仍然属于本次请求的航班。
                if h.status == Status.OK:
                    if hasattr(result, "flightId") and result.flightId != body.flightId:
                        self.log("IGNORE_FLIGHT", key, operation, attempt=attempt)
                        continue
                    if isinstance(result, MonitorResult) and result.remainingMillis > body.durationSeconds * 1000:
                        self.log("IGNORE_DURATION", key, operation, attempt=attempt)
                        continue
                if h.status != Status.OK:
                    pending = None
                self.log("REPLY", key, operation, attempt=attempt, status=int(h.status),
                         body=asdict(message.response.body))
                return CallOutcome(key, message, attempt, False, pending, received_at)
            self.log("ATTEMPT_TIMEOUT", key, operation, attempt=attempt)
        self.log("RESULT_UNKNOWN", key, operation, attempt=self.config.max_attempts)
        return CallOutcome(key, None, self.config.max_attempts, True, None, None)

    def close(self) -> None:
        self.transport.close()
