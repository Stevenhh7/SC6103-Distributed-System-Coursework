"""[C-01] 协议常量已定义；A/C 改动线上数值前必须同步规范及两端。

枚举值就是线上的数值，禁止依赖枚举声明顺序或使用 pickle/JSON 替代编码。
"""

from enum import IntEnum

VERSION = 1
HEADER_BYTES = 32
MAX_MESSAGE_BYTES = 1024
MAX_BODY_BYTES = MAX_MESSAGE_BYTES - HEADER_BYTES
RECEIVE_BUFFER_BYTES = 65535
CALLBACK_BODY_BYTES = 12
MAX_LOCATION_UTF8_BYTES = 128
MAX_ERROR_UTF8_BYTES = 256
MAX_FLIGHTS = 100
MAX_MONITOR_SECONDS = 3600
MAX_REQUEST_ID = 2147483647
DEFAULT_PORT = 6789
DEFAULT_TIMEOUT_MS = 1000
DEFAULT_MAX_ATTEMPTS = 5


class MessageType(IntEnum):
    """成功和错误都使用 REPLY，通过头部 status 区分。"""

    REQUEST = 1
    REPLY = 2
    CALLBACK = 3


class Semantics(IntEnum):
    """服务器必须核对该模式，不能仅凭客户端启动配置假定模式一致。"""

    ALO = 1
    AMO = 2


class Operation(IntEnum):
    """六项远程操作。CALLBACK 的操作码固定使用 MONITOR_SEATS。"""

    QUERY_ROUTE = 1
    QUERY_FLIGHT = 2
    RESERVE_SEATS = 3
    MONITOR_SEATS = 4
    SET_AIRFARE = 5
    INCREASE_AIRFARE = 6


class Status(IntEnum):
    """错误体统一为长度前缀 UTF-8 文本；判断错误使用数值。"""

    OK = 0
    ROUTE_NOT_FOUND = 1
    FLIGHT_NOT_FOUND = 2
    INSUFFICIENT_SEATS = 3
    INVALID_ARGUMENT = 4
    MALFORMED_MESSAGE = 5
    UNSUPPORTED_OPERATION = 6
    SEMANTICS_MISMATCH = 7
    REQUEST_ID_REUSE = 8
    LIMIT_EXCEEDED = 9
