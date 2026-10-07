"""代理自身的真实回环 UDP 测试，不代表 Java 服务端联调。"""

import socket
import json
import threading
import unittest
from uuid import UUID

from .udp_loss_proxy import HEADER, UdpLossProxy


SESSION = UUID("11111111-1111-4111-8111-111111111111")


def packet(kind, request_id, operation=3, session=SESSION):
    body = b"\0" * 8
    return HEADER.pack(1, kind, operation, session.bytes, request_id, 0, 2, 0, len(body)) + body


class ProxyTest(unittest.TestCase):
    def setUp(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.settimeout(0.2)
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client.bind(("127.0.0.1", 0))
        self.client.settimeout(0.2)
        self.proxy = None
        self.stop = threading.Event()
        self.thread = None

    def start(self, direction):
        self.proxy = UdpLossProxy(("127.0.0.1", 0), self.server.getsockname(), SESSION, 2,
                                  direction, emit=lambda *a, **k: None)
        self.thread = threading.Thread(target=self.proxy.serve, args=(self.stop,), daemon=True)
        self.thread.start()

    def tearDown(self):
        self.stop.set()
        if self.thread:
            self.thread.join(2)
            self.assertFalse(self.thread.is_alive())
        if self.proxy:
            self.proxy.close()
        self.client.close()
        self.server.close()

    def test_all_target_requests_dropped_queries_forward_and_backend_stable(self):
        self.start("requests")
        self.client.sendto(packet(1, 1, 2), self.proxy.endpoint)
        before, peer = self.server.recvfrom(65535)
        self.assertEqual(packet(1, 1, 2), before)
        for _ in range(3):
            self.client.sendto(packet(1, 2), self.proxy.endpoint)
            with self.assertRaises(socket.timeout):
                self.server.recvfrom(65535)
        self.client.sendto(packet(1, 3, 2), self.proxy.endpoint)
        after, same_peer = self.server.recvfrom(65535)
        self.assertEqual(peer, same_peer)
        self.assertEqual(packet(1, 3, 2), after)

    def test_all_target_replies_dropped_callback_passes(self):
        self.start("replies")
        self.client.sendto(packet(1, 2), self.proxy.endpoint)
        request, peer = self.server.recvfrom(65535)
        self.assertEqual(packet(1, 2), request)
        for _ in range(3):
            self.server.sendto(packet(2, 2), peer)
            with self.assertRaises(socket.timeout):
                self.client.recvfrom(65535)
        callback = packet(3, 2, 4)
        self.server.sendto(callback, peer)
        delivered, source = self.client.recvfrom(65535)
        self.assertEqual(callback, delivered)
        self.assertEqual(self.proxy.endpoint, source)

    def test_other_identity_or_query_reply_is_not_dropped(self):
        self.start("replies")
        self.client.sendto(packet(1, 1, 2), self.proxy.endpoint)
        _, peer = self.server.recvfrom(65535)
        for payload in (packet(2, 1, 2), packet(2, 2, 2), packet(2, 2, 3, UUID(int=3))):
            self.server.sendto(payload, peer)
            self.assertEqual(payload, self.client.recvfrom(65535)[0])

    def test_unexpected_source_and_second_client_ignored(self):
        self.start("replies")
        self.client.sendto(packet(1, 1, 2), self.proxy.endpoint)
        _, peer = self.server.recvfrom(65535)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as other:
            other.sendto(packet(1, 1, 2), self.proxy.endpoint)
            with self.assertRaises(socket.timeout):
                self.server.recvfrom(65535)
            other.sendto(packet(2, 1, 2), peer)
            with self.assertRaises(socket.timeout):
                self.client.recvfrom(65535)

    def test_invalid_fault_selector_rejected(self):
        for direction, session, request_id in (("bad", SESSION, 2), ("requests", UUID(int=0), 2),
                                                ("replies", SESSION, 0), ("requests", SESSION, 2147483648)):
            with self.assertRaises(ValueError):
                UdpLossProxy(("127.0.0.1", 0), self.server.getsockname(), session, request_id, direction)

    def test_log_separates_actual_packet_identity_from_fault_target(self):
        records = []
        self.proxy = UdpLossProxy(("127.0.0.1", 0), self.server.getsockname(), SESSION, 2,
                                  "replies", emit=lambda line, **kwargs: records.append(json.loads(line)))
        self.proxy.log("FORWARD", "replies", packet(2, 7, 2, UUID(int=3)))
        actual = records[-1]
        self.assertEqual(str(UUID(int=3)), actual["sessionId"])
        self.assertEqual(7, actual["requestId"])
        self.assertEqual(2, actual["operation"])
        self.assertEqual(str(SESSION), actual["targetSessionId"])
        self.assertEqual(2, actual["targetRequestId"])
        self.proxy.log("FORWARD", "requests", b"short")
        self.assertNotIn("sessionId", records[-1])


if __name__ == "__main__":
    unittest.main()
