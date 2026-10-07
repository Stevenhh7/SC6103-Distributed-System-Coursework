"""B 的本地 UDP 全丢故障代理：只影响指定写请求，查询和 callback 正常放行。

每次实验启动独立代理，只接受一个客户端端点；Java 观察到稳定的代理后端端点。
此工具属于实验，不替代 A 的服务端、调用语义或 codec。
"""

import argparse
import json
import selectors
import socket
import struct
import threading
from uuid import UUID


HEADER = struct.Struct("!BBH16siHBBi")


class UdpLossProxy:
    def __init__(self, listen: tuple[str, int], server: tuple[str, int],
                 session: UUID, request_id: int, direction: str, emit=print):
        if direction not in ("requests", "replies") or session.int == 0 or not 1 <= request_id <= 2147483647:
            raise ValueError("invalid fault direction or target")
        self.server = socket.getaddrinfo(server[0], server[1], socket.AF_INET,
                                         socket.SOCK_DGRAM)[0][4]
        self.session = session.bytes
        self.request_id = request_id
        self.direction = direction
        self.emit = emit
        self.client = None
        self.front = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.back = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.front.bind(listen)
            self.back.bind(("0.0.0.0", 0))
        except BaseException:
            self.close()
            raise

    @property
    def endpoint(self):
        return self.front.getsockname()

    def close(self):
        self.front.close()
        self.back.close()

    def target(self, payload: bytes, message_type: int) -> bool:
        if len(payload) < HEADER.size:
            return False
        version, kind, operation, session, request_id, status, mode, reserved, length = HEADER.unpack_from(payload)
        return (version == 1 and kind == message_type and session == self.session
                and request_id == self.request_id and operation in (3, 5, 6)
                and length == len(payload) - HEADER.size)

    def log(self, action: str, direction: str, payload: bytes):
        fields = {"event": action, "direction": direction, "bytes": len(payload),
                  "targetSessionId": str(UUID(bytes=self.session)),
                  "targetRequestId": self.request_id}
        # selector 是故障目标，sessionId/requestId 则是实际收到的包，不能混写。
        if len(payload) >= HEADER.size:
            version, kind, operation, session, request_id, status, mode, reserved, length = HEADER.unpack_from(payload)
            fields.update(version=version, messageType=kind, operation=operation,
                          sessionId=str(UUID(bytes=session)), requestId=request_id,
                          status=status, mode=mode, reserved=reserved, bodyLength=length)
        self.emit(json.dumps(fields, ensure_ascii=False), flush=True)

    def serve(self, stop: threading.Event):
        with selectors.DefaultSelector() as selector:
            selector.register(self.front, selectors.EVENT_READ, "requests")
            selector.register(self.back, selectors.EVENT_READ, "replies")
            self.emit(json.dumps({"event": "PROXY_READY", "listen": self.endpoint,
                                  "server": self.server, "direction": self.direction,
                                  "targetSessionId": str(UUID(bytes=self.session)),
                                  "targetRequestId": self.request_id}), flush=True)
            while not stop.is_set():
                for selected, _ in selector.select(0.1):
                    payload, peer = selected.fileobj.recvfrom(65535)
                    direction = selected.data
                    if direction == "requests":
                        if self.client is None:
                            self.client = peer
                        if peer != self.client:
                            self.log("IGNORE_SECOND_CLIENT", direction, payload)
                            continue
                    elif peer != self.server or self.client is None:
                        self.log("IGNORE_SOURCE", direction, payload)
                        continue
                    if direction == self.direction and self.target(payload, 1 if direction == "requests" else 2):
                        self.log("DROP_ALL_TARGET", direction, payload)
                        continue
                    if direction == "requests":
                        self.back.sendto(payload, self.server)
                    else:
                        self.front.sendto(payload, self.client)
                    self.log("FORWARD", direction, payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description="B local experiment UDP loss proxy")
    parser.add_argument("--listen-port", type=int, default=6790)
    parser.add_argument("--server", default="127.0.0.1")
    parser.add_argument("--server-port", type=int, default=6789)
    parser.add_argument("--session-id", type=UUID, required=True)
    parser.add_argument("--request-id", type=int, default=2)
    parser.add_argument("--drop", choices=("requests", "replies"), required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.listen_port <= 65535 or not 1 <= args.server_port <= 65535:
        parser.error("ports must be 1..65535")
    proxy = UdpLossProxy(("127.0.0.1", args.listen_port), (args.server, args.server_port),
                         args.session_id, args.request_id, args.drop)
    try:
        proxy.serve(threading.Event())
    except KeyboardInterrupt:
        return 0
    finally:
        proxy.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
