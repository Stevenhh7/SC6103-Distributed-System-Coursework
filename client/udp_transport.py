"""[C-03] UDP/IPv4 边界；创建后在会话内复用同一个未 connect 的 socket。"""

from dataclasses import dataclass
import math
import socket
from typing import Optional

from .config import ClientConfig
from .protocol import MAX_MESSAGE_BYTES, RECEIVE_BUFFER_BYTES


@dataclass(frozen=True, slots=True)
class ReceivedDatagram:
    """有效数据及实际来源；不能用预设服务器地址替换 peer。"""

    data: bytes
    peer: tuple[str, int]


class UdpTransport:
    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self._socket: Optional[socket.socket] = None
        self.server_endpoint: Optional[tuple[str, int]] = None

    def open(self) -> None:
        """只解析/绑定一次；即使第一次请求被丢弃，也已分配稳定本地端口。"""
        if self._socket is not None:
            return
        addresses = socket.getaddrinfo(self.config.server, self.config.port, socket.AF_INET, socket.SOCK_DGRAM)
        endpoint = addresses[0][4]
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("0.0.0.0", 0))
            # Windows 的 UDP ICMP 错误不应冒充一次业务回复。
            if hasattr(socket, "SIO_UDP_CONNRESET"):
                sock.ioctl(socket.SIO_UDP_CONNRESET, False)
        except BaseException:
            sock.close()
            raise
        self.server_endpoint = (endpoint[0], endpoint[1])
        self._socket = sock

    def send(self, payload: bytes) -> None:
        if self._socket is None or self.server_endpoint is None:
            raise RuntimeError("transport is not open")
        if not 0 < len(payload) <= MAX_MESSAGE_BYTES:
            raise ValueError("outgoing datagram exceeds protocol limit")
        # receive 会按剩余时间缩短 socket 超时；下一次发送必须重新设置上限，
        # 也不能让第一次 sendto 使用默认的无限阻塞等待。
        self._socket.settimeout(self.config.timeout_ms / 1000.0)
        sent = self._socket.sendto(payload, self.server_endpoint)
        if sent != len(payload):
            raise OSError("incomplete UDP send")

    def receive(self, timeout_ms: float) -> ReceivedDatagram:
        if self._socket is None:
            raise RuntimeError("transport is not open")
        if not math.isfinite(timeout_ms):
            raise ValueError("timeout must be finite")
        if timeout_ms <= 0:
            raise socket.timeout("receive deadline reached")
        self._socket.settimeout(timeout_ms / 1000.0)
        data, peer = self._socket.recvfrom(RECEIVE_BUFFER_BYTES)
        return ReceivedDatagram(data, (peer[0], peer[1]))

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self.server_endpoint = None
