"""运行前检查：真实端口冲突 + 模拟 C 查询结果，不代表 Java 联调。"""

import socket
import unittest
from unittest.mock import patch

from client.models import CallOutcome, FlightDetails, FlightTime, Header, Reply, RequestKey, Response
from client.protocol import Semantics, Status
from client.tests.helpers import SESSION
from .runtime_check import check_ports, wait_ready


class RuntimeCheckTest(unittest.TestCase):
    def test_occupied_udp_port_rejected(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as existing:
            existing.bind(("127.0.0.1", 0))
            with self.assertRaises(OSError): check_ports([existing.getsockname()[1]])

    def test_free_port_probe_is_closed_even_after_failure(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp:
            temp.bind(("127.0.0.1", 0))
            free_port = temp.getsockname()[1]
        with self.assertRaises(ValueError): check_ports([free_port, 0])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as next_owner:
            next_owner.bind(("127.0.0.1", free_port))

    def test_port_probe_succeeds_without_leaving_socket_open(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp:
            temp.bind(("127.0.0.1", 0)); port = temp.getsockname()[1]
        check_ports([port])
        check_ports([port])

    def test_readiness_is_read_only_and_rejects_unknown_errors_stale_seed(self):
        key = RequestKey(SESSION, 1)
        def outcome(seats=10, fare=100, status=Status.OK, timed_out=False):
            body = FlightDetails(FlightTime(2026, 10, 17, 9, 30), fare, seats)
            reply = Reply(Header(1, 2, 2, SESSION, 1, status, Semantics.AMO, 28), Response(status, body))
            return CallOutcome(key, None if timed_out else reply, 1, timed_out, None, 1.0)
        with patch("client.invoker.Invoker") as factory:
            invoker = factory.return_value
            invoker.session_id = SESSION
            invoker.invoke.return_value = outcome()
            self.assertEqual("SERVER_READY", wait_ready(6789, "amo")["event"])
            self.assertEqual(2, invoker.invoke.call_args.args[0])
            self.assertEqual(1001, invoker.invoke.call_args.args[1].flightId)
            for result in (outcome(timed_out=True), outcome(status=Status.FLIGHT_NOT_FOUND),
                           outcome(seats=9), outcome(fare=120)):
                invoker.invoke.return_value = result
                with self.assertRaises(ValueError): wait_ready(6789, "amo")
            self.assertEqual(5, invoker.close.call_count)


if __name__ == "__main__":
    unittest.main()
