"""[C-02] Python 手工二进制编解码，按规范第 2-6、10 节实现。

输入/输出都使用完整消息；不能把整个接收缓冲区当有效消息。
所有占位函数明确失败，避免将空字节或虚假成功结果发到服务器。
"""

from typing import Union

from .models import CallbackMessage, Reply, Request


class ProtocolError(ValueError):
    """收到畸形消息时使用；业务错误应保留为 Reply 中的 status。"""


def encode_request(request: Request) -> bytes:
    """TODO(C-02): 写 32 字节头及六类请求体；检查宽度、UTF-8 和长度。

    reserved 写 0；UUID 使用 bytes 而非 bytes_le；票价使用单个 binary32。
    同一逻辑调用只在 Invoker 中编码一次，重传复用结果。
    """
    raise NotImplementedError("[C-02] encode_request is not implemented")


def decode_message(data: bytes) -> Union[Reply, CallbackMessage]:
    """TODO(C-02): 校验完整消息，再按 messageType/status/operation 分派。

    错误回复统一解析 ErrorBody；callback 固定 12 字节体。解析后禁止尾字节。
    来源 IP/端口匹配由 Invoker 完成，不属于字节解码器职责。
    """
    raise NotImplementedError("[C-02] decode_message is not implemented")
