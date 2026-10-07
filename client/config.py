"""[C-00/C-08] 客户端及本地实验配置，不增加任何线上字段。"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from .models import RequestKey
from .input_validation import location, positive_int, price
from .protocol import DEFAULT_MAX_ATTEMPTS, DEFAULT_PORT, DEFAULT_TIMEOUT_MS, Semantics


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """航班 ID 必须来自 B 的实际数据；不把规范示例当成固定种子数据。"""

    flight_id: int
    source: Optional[str] = None
    destination: Optional[str] = None
    quantity: int = 1
    new_price: float = 120.0
    delta: float = 10.0
    monitor_seconds: int = 5

    def __post_init__(self) -> None:
        positive_int(self.flight_id)
        positive_int(self.quantity)
        positive_int(self.monitor_seconds, 3600)
        object.__setattr__(self, "new_price", price(self.new_price))
        object.__setattr__(self, "delta", price(self.delta, positive=True))
        if self.source is not None:
            object.__setattr__(self, "source", location(self.source))
        if self.destination is not None:
            object.__setattr__(self, "destination", location(self.destination))


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """单位明确：port 为 UDP 端口，timeout_ms 为毫秒，max_attempts 含首次。"""

    server: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    semantics: Semantics = Semantics.AMO
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    session_id: Optional[UUID] = None
    drop_first_request: Optional[RequestKey] = None
    experiment: Optional[ExperimentConfig] = None

    def __post_init__(self) -> None:
        """只验证启动参数，业务参数和数据报校验由后续模块完成。"""
        if not self.server.strip():
            raise ValueError("server cannot be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be in 1..65535")
        if self.timeout_ms <= 0 or self.max_attempts <= 0:
            raise ValueError("timeout-ms and max-attempts must be positive")
        if self.semantics not in tuple(Semantics):
            raise ValueError("semantics must be ALO or AMO")
        if self.session_id is not None and self.session_id.int == 0:
            raise ValueError("session-id cannot be the zero UUID")


def parse_request_selector(text: str) -> RequestKey:
    """两端约定故障选择器为 UUID:requestId，例如 UUID:1。"""
    try:
        session, request = text.rsplit(":", 1)
        key = RequestKey(UUID(session), int(request))
    except (ValueError, AttributeError) as exc:
        raise ValueError("request selector must be UUID:requestId") from exc
    if key.clientSessionId.int == 0 or not 1 <= key.requestId <= 2147483647:
        raise ValueError("request selector requires a nonzero UUID and positive i32 ID")
    return key
