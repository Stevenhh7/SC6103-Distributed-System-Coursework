"""仅测试使用的可控时钟/传输和独立报文构造器。"""

from collections import deque
import socket
from uuid import UUID

from client.config import ClientConfig
from client.invoker import Invoker
from client.udp_transport import ReceivedDatagram

SESSION = UUID("00112233-4455-4677-8899-aabbccddeeff")
PEER = ("127.0.0.1", 6789)


def i32(value):
    return value.to_bytes(4, "big", signed=True)


def packet(body, *, kind=2, op=2, request_id=1, status=0, mode=2, session=SESSION):
    return (bytes([1, kind]) + op.to_bytes(2, "big") + session.bytes
            + i32(request_id) + status.to_bytes(2, "big") + bytes([mode, 0])
            + i32(len(body)) + body)


def detail(**header):
    # 2026-10-17 14:30, 120 SGD, 10 seats，独立固定位模式。
    return packet(bytes.fromhex("000007ea0000000a000000110000000e0000001e42f000000000000a"), **header)


def error(*, text="Flight not found", **header):
    raw = text.encode("utf-8")
    return packet(i32(len(raw)) + raw, status=header.pop("status", 2), **header)


def callback(sequence=1, *, flight=1001, seats=8, **header):
    return packet(i32(flight) + i32(seats) + i32(sequence), kind=3, op=4, **header)


def monitor_reply(remaining=1000, *, flight=1001, **header):
    return packet(i32(flight) + i32(remaining), op=4, **header)


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now


class FakeTransport:
    """events=(自 100 起的秒数, bytes, peer)；等待不会依赖真实 sleep。"""

    def __init__(self, clock, events=()):
        self.clock = clock
        self.events = deque((100.0 + delay, data, peer) for delay, data, peer in events)
        self.server_endpoint = PEER
        self.sent = []
        self.waits = []
        self.closed = False
        self.opened = False

    def open(self):
        self.opened = True

    def send(self, payload):
        self.sent.append((self.clock.now, payload))

    def receive(self, timeout_ms):
        self.waits.append(timeout_ms)
        deadline = self.clock.now + timeout_ms / 1000.0
        if self.events and self.events[0][0] < deadline:
            at, data, peer = self.events.popleft()
            self.clock.now = max(self.clock.now, at)
            return ReceivedDatagram(data, peer)
        self.clock.now = deadline
        raise socket.timeout()

    def close(self):
        self.closed = True


def make_invoker(clock, events=(), **options):
    invoker = Invoker(ClientConfig(session_id=SESSION, **options))
    invoker.transport = FakeTransport(clock, events)
    return invoker
