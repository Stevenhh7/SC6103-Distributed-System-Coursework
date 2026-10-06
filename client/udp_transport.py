"""[C-03] UDP 传输边界；构造对象不创建 socket，不进行网络通信。"""

import socket
from dataclasses import dataclass
from typing import Optional

from .config import ClientConfig


@dataclass(frozen=True, slots=True)
class ReceivedDatagram:
    """实际收到的 bytes 与源端点；源端点供调用层验证。"""

    data: bytes
    peer: tuple[str, int]


class UdpTransport:
    """一个实例复用同一本地端口，供普通调用和监控共同使用。"""

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self._socket: Optional[socket.socket] = None

    def open(self) -> None:
        """TODO(C-03): 创建 AF_INET/SOCK_DGRAM socket，确定服务端 IPv4 端点。"""
        raise NotImplementedError("[C-03] UDP socket setup is not implemented")

    def send(self, payload: bytes) -> None:
        """TODO(C-03): 用已打开的 socket 发送完整数据报；不自行修改请求。"""
        raise NotImplementedError("[C-03] UDP send is not implemented")

    def receive(self, timeout_ms: float) -> ReceivedDatagram:
        """TODO(C-03): 按剩余毫秒设置超时，recvfrom(65535)，保留来源。

        timeout_ms 是调用层提供的剩余等待时间，不能擅自重置为默认 1 秒。
        """
        raise NotImplementedError("[C-03] UDP receive is not implemented")

    def close(self) -> None:
        """资源清理已提供；未来 open 创建的 socket 由此关闭。"""
        if self._socket is not None:
            self._socket.close()
            self._socket = None
