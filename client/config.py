"""[C-00] 客户端启动配置；实际收发和故障注入仍为待办。"""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from .models import RequestKey
from .protocol import DEFAULT_MAX_ATTEMPTS, DEFAULT_PORT, DEFAULT_TIMEOUT_MS, Semantics


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

    def __post_init__(self) -> None:
        """只验证启动参数，业务参数和数据报校验由后续模块完成。"""
        if not self.server.strip():
            raise ValueError("server cannot be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be in 1..65535")
        if self.timeout_ms <= 0 or self.max_attempts <= 0:
            raise ValueError("timeout-ms and max-attempts must be positive")
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
