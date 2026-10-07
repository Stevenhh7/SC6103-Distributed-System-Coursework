"""真实本机 UDP 测试；报文应答器只实现测试脚本，不充当 Java 业务实现。"""

from contextlib import contextmanager, redirect_stdout
import io
import socket
import threading
import unittest
from unittest.mock import patch

from client.config import ClientConfig
from client.invoker import Invoker
from client.models import FlightQuery, IncreaseAirfare, MonitorRegistration, Reservation, RouteQuery, SetAirfare
from client.monitor import accepted_monitor, monitor_until_expiry
from client.protocol import Semantics
from client.protocol_codec import ProtocolError, decode_message
from client.tests.helpers import SESSION, callback, detail, i32, monitor_reply, packet
from client.udp_transport import UdpTransport


@contextmanager
def scripted_peer(script):
    errors = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(2.0)

    def worker():
        try:
            script(sock)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        yield sock.getsockname()
    finally:
        thread.join(3.0)
        sock.close()
        if thread.is_alive():
            raise AssertionError("test UDP peer did not terminate")
        if errors:
            raise errors[0]


class UdpTests(unittest.TestCase):
    def test_construction_and_check_do_not_open_network(self):
        with patch("socket.socket", side_effect=AssertionError("must not create socket")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("must not resolve DNS")):
            transport = UdpTransport(ClientConfig())
            self.assertIsNone(transport.server_endpoint)
            transport.close()

    def test_real_receive_preserves_source_and_full_oversized_packet(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as peer:
            peer.bind(("127.0.0.1", 0))
            peer.settimeout(1)
            transport = UdpTransport(ClientConfig(server="localhost", port=peer.getsockname()[1]))
            try:
                transport.open()
                original = transport._socket
                transport.open()
                self.assertIs(transport._socket, original)
                self.assertEqual(transport.server_endpoint, peer.getsockname())
                transport.send(b"probe")
                data, source = peer.recvfrom(65535)
                self.assertEqual(data, b"probe")
                peer.sendto(b"x" * 2048, source)
                received = transport.receive(1000)
                self.assertEqual(received.peer, peer.getsockname())
                self.assertEqual(len(received.data), 2048)
                with self.assertRaises(ProtocolError):
                    decode_message(received.data)
                with self.assertRaises(socket.timeout):
                    transport.receive(1.5)
                with self.assertRaises(ValueError):
                    transport.send(b"x" * 1025)
            finally:
                transport.close()
                transport.close()
            self.assertEqual(original.fileno(), -1)

    def test_real_retry_retains_port_and_monitor_reuses_socket(self):
        observed = []

        def script(sock):
            first, source = sock.recvfrom(65535)
            second, source2 = sock.recvfrom(65535)
            observed.extend([(first, source), (second, source2)])
            # 同一内容但来源不同，客户端应忽略。
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as rogue:
                rogue.sendto(detail(), source)
            sock.sendto(detail(), source)
            monitor, monitor_source = sock.recvfrom(65535)
            observed.append((monitor, monitor_source))
            sock.sendto(callback(3, request_id=2), source)
            sock.sendto(monitor_reply(30, request_id=2), source)
            sock.sendto(callback(4, request_id=2), source)

        with scripted_peer(script) as peer:
            invoker = Invoker(ClientConfig(port=peer[1], session_id=SESSION, timeout_ms=100, max_attempts=5))
            try:
                result = invoker.invoke(2, FlightQuery(1001))
                self.assertEqual(result.attempts, 2)
                outcome = invoker.invoke(4, MonitorRegistration(1001, 1))
                self.assertEqual(outcome.pending_callback.updateSequence, 3)
                output = io.StringIO()
                with redirect_stdout(output):
                    monitor_until_expiry(invoker, accepted_monitor(outcome))
                self.assertIn("序号 3", output.getvalue())
                self.assertIn("序号 4", output.getvalue())
            finally:
                invoker.close()
        self.assertEqual(observed[0][0], observed[1][0])
        self.assertEqual(len({source for _, source in observed}), 1)

    def test_six_operations_over_real_udp_with_independent_response_bytes(self):
        self._check_six_operations(Semantics.AMO)

    def test_six_operations_alo_over_real_udp(self):
        self._check_six_operations(Semantics.ALO)

    def _check_six_operations(self, mode):
        requests = [
            (1, RouteQuery("北京", "SIN"), bytes.fromhex("00000006e58c97e4baac0000000353494e")),
            (2, FlightQuery(1001), i32(1001)),
            (3, Reservation(1001, 2), i32(1001) + i32(2)),
            (4, MonitorRegistration(1001, 1), i32(1001) + i32(1)),
            (5, SetAirfare(1001, 120), i32(1001) + bytes.fromhex("42f00000")),
            (6, IncreaseAirfare(1001, 20), i32(1001) + bytes.fromhex("41a00000")),
        ]
        seen = []

        def script(sock):
            for op, _, expected in requests:
                raw, source = sock.recvfrom(65535)
                self.assertEqual(raw, packet(expected, kind=1, op=op, request_id=op, mode=mode))
                seen.append(source)
                if op == 1:
                    reply = packet(i32(1) + i32(1001), op=1, request_id=op, mode=mode)
                elif op == 2:
                    reply = detail(request_id=op, mode=mode)
                elif op == 3:
                    reply = packet(i32(1001) + i32(8), op=3, request_id=op, mode=mode)
                elif op == 4:
                    reply = monitor_reply(0, request_id=op, mode=mode)
                else:
                    reply = packet(i32(1001) + bytes.fromhex("42f00000"), op=op, request_id=op, mode=mode)
                sock.sendto(reply, source)

        with scripted_peer(script) as peer:
            invoker = Invoker(ClientConfig(port=peer[1], session_id=SESSION, semantics=mode))
            try:
                for op, body, _ in requests:
                    outcome = invoker.invoke(op, body)
                    self.assertFalse(outcome.timed_out)
                    self.assertEqual(outcome.reply.header.operation, op)
                    self.assertEqual(outcome.attempts, 1)
            finally:
                invoker.close()
        self.assertEqual(len(set(seen)), 1)


if __name__ == "__main__":
    unittest.main()
