"""二次需求核查回归：发送超时、实验终态、证据字段及模式/监控组合。"""

from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
import io
import json
import socket
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from client.config import ClientConfig, ExperimentConfig
from client.experiments import ExperimentFailure, run_case
from client.invoker import Invoker
from client.models import FlightQuery, MonitorRegistration
from client.monitor import accepted_monitor, monitor_until_expiry
from client.protocol import Semantics
from client.tests.helpers import (
    SESSION, PEER, FakeClock, callback, detail, error, i32, make_invoker, monitor_reply, packet,
)
from client.tests.test_udp_transport import scripted_peer
from client.udp_transport import UdpTransport


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        timer = patch("client.invoker.time.monotonic", self.clock.monotonic)
        timer.start()
        self.addCleanup(timer.stop)
        self.output = io.StringIO()
        stdout = redirect_stdout(self.output)
        stdout.__enter__()
        self.addCleanup(stdout.__exit__, None, None, None)

    def test_send_timeout_uses_remaining_attempt_time_then_retries_same_request(self):
        invoker = make_invoker(self.clock, [(1.1, detail(), PEER)])
        sent = []

        def send(raw):
            sent.append((self.clock.now, raw))
            if len(sent) == 1:
                self.clock.now += 0.25
                raise socket.timeout("send buffer busy")

        invoker.transport.send = send
        result = invoker.invoke(2, FlightQuery(1001))
        self.assertFalse(result.timed_out)
        self.assertEqual(result.attempts, 2)
        self.assertEqual([at for at, _ in sent], [100, 101])
        self.assertEqual(sent[0][1], sent[1][1])
        self.assertAlmostEqual(invoker.transport.waits[0], 750)

    def test_all_send_timeouts_return_unknown_after_finite_attempts(self):
        invoker = make_invoker(self.clock, max_attempts=3)
        sent = []

        def send(raw):
            sent.append(raw)
            self.clock.now += 1
            raise socket.timeout("send deadline")

        invoker.transport.send = send
        result = invoker.invoke(2, FlightQuery(1001))
        self.assertTrue(result.timed_out)
        self.assertEqual((result.reply, result.pending_callback, result.reply_received_at), (None, None, None))
        self.assertEqual(result.attempts, 3)
        self.assertEqual(len(set(sent)), 1)
        self.assertEqual(self.clock.now, 103)

    def test_baseline_unknown_write_still_reads_final_state_without_more_writes(self):
        events = [(0.1, detail(), PEER),
                  (0.2, packet(i32(1) + i32(1001), op=1, request_id=2), PEER),
                  (1.3, detail(request_id=4), PEER)]
        invoker = make_invoker(self.clock, events, max_attempts=1,
                               experiment=ExperimentConfig(1001, "SIN", "PEK"))
        with self.assertRaises(ExperimentFailure):
            run_case(invoker, "baseline")
        self.assertEqual([int.from_bytes(raw[2:4], "big") for _, raw in invoker.transport.sent], [2, 1, 3, 2])
        self.assertIn("after (read-only)", self.output.getvalue())

    def test_request_log_contains_reproducible_parameters(self):
        invoker = make_invoker(self.clock, [(0.1, detail(), PEER)], timeout_ms=750, max_attempts=3)
        with self.assertLogs("sc6103.client", level="INFO") as logged:
            invoker.invoke(2, FlightQuery(1001))
        events = [json.loads(item.getMessage()) for item in logged.records]
        created = next(item for item in events if item["event"] == "REQUEST_CREATED")
        self.assertEqual(created["body"], {"flightId": 1001})
        self.assertEqual((created["timeoutMs"], created["maxAttempts"]), (750, 3))
        self.assertEqual((created["sessionId"], created["requestId"]), (str(SESSION), 1))

    def test_case_log_contains_values_for_reproduction(self):
        options = ExperimentConfig(1001, quantity=2, new_price=135, delta=15, monitor_seconds=2)
        invoker = make_invoker(self.clock, [(0.1, detail(), PEER),
                                           (0.2, monitor_reply(0, request_id=2), PEER),
                                           (0.3, detail(request_id=3), PEER)], experiment=options)
        with self.assertLogs("sc6103.client", level="INFO") as logged:
            run_case(invoker, "monitor")
        start = next(json.loads(item.getMessage()) for item in logged.records
                     if json.loads(item.getMessage())["event"] == "CASE_START")
        self.assertEqual(start["parameters"]["quantity"], 2)
        self.assertEqual(start["parameters"]["delta"], 15.0)
        self.assertEqual(start["parameters"]["monitor_seconds"], 2)

    def test_alo_retries_and_accepts_only_alo_confirmation(self):
        invoker = make_invoker(self.clock, [(0.1, detail(mode=2), PEER), (1.1, detail(mode=1), PEER)],
                               semantics=Semantics.ALO)
        result = invoker.invoke(2, FlightQuery(1001))
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.reply.header.semantics, Semantics.ALO)
        self.assertTrue(all(raw[26] == 1 for _, raw in invoker.transport.sent))
        self.assertEqual(invoker.transport.sent[0][1], invoker.transport.sent[1][1])

    def test_alo_receives_mode_mismatch_echoing_alo(self):
        invoker = make_invoker(self.clock, [(0.1, error(mode=1, status=7, text="Server uses AMO"), PEER)],
                               semantics=Semantics.ALO)
        result = invoker.invoke(2, FlightQuery(1001))
        self.assertEqual(result.reply.header.status, 7)
        self.assertEqual(result.attempts, 1)

    def test_monitor_replayed_confirmation_uses_reduced_remaining_time(self):
        events = [(0.1, callback(2), PEER), (1.2, monitor_reply(250), PEER),
                  (1.25, monitor_reply(3000), PEER), (1.3, callback(3), PEER),
                  (1.5, callback(4), PEER)]
        invoker = make_invoker(self.clock, events)
        result = invoker.invoke(4, MonitorRegistration(1001, 3))
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.pending_callback.updateSequence, 2)
        monitor_until_expiry(invoker, accepted_monitor(result))
        self.assertAlmostEqual(self.clock.now, 101.45)
        self.assertIn("序号 2", self.output.getvalue())
        self.assertIn("序号 3", self.output.getvalue())
        self.assertNotIn("序号 4", self.output.getvalue())

    def test_expired_replayed_confirmation_discards_pending_callback(self):
        invoker = make_invoker(self.clock, [(0.1, callback(), PEER), (1.2, monitor_reply(0), PEER)])
        result = invoker.invoke(4, MonitorRegistration(1001, 1))
        self.assertEqual(result.attempts, 2)
        wait_count = len(invoker.transport.waits)
        monitor_until_expiry(invoker, accepted_monitor(result))
        self.assertEqual(len(invoker.transport.waits), wait_count)
        self.assertNotIn("座位更新", self.output.getvalue())


class TransportAuditTests(unittest.TestCase):
    def test_send_does_not_inherit_tiny_receive_timeout(self):
        transport = UdpTransport(ClientConfig(timeout_ms=1000))
        sock = Mock()
        sock.recvfrom.side_effect = socket.timeout()
        sock.sendto.return_value = 5
        transport._socket = sock
        transport.server_endpoint = PEER
        try:
            with self.assertRaises(socket.timeout):
                transport.receive(0.5)
            transport.send(b"probe")
            self.assertEqual(sock.settimeout.call_args.args[0], 1.0)
        finally:
            transport.close()

    def test_two_real_clients_same_request_id_have_separate_ports_and_callbacks(self):
        observed = []
        outcomes = []

        def script(sock):
            # 两个注册均已到达后，再发各自身份的确认/回调。
            for _ in range(2):
                raw, peer = sock.recvfrom(65535)
                observed.append((UUID(bytes=raw[4:20]), int.from_bytes(raw[20:24], "big"), peer))
            for index, (session, request_id, peer) in enumerate(observed):
                other = observed[1-index][0]
                sock.sendto(callback(99, session=other), peer)
                sock.sendto(callback(3, session=session), peer)
                sock.sendto(monitor_reply(0, session=session), peer)

        with scripted_peer(script) as peer:
            clients = [Invoker(ClientConfig(port=peer[1], timeout_ms=1000)) for _ in range(2)]
            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    jobs = [pool.submit(client.invoke, 4, MonitorRegistration(1001, 1)) for client in clients]
                    outcomes = [job.result(timeout=3) for job in jobs]
            finally:
                for client in clients:
                    client.close()
        self.assertEqual(len({session for session, _, _ in observed}), 2)
        self.assertEqual(len({peer for _, _, peer in observed}), 2)
        self.assertEqual({request_id for _, request_id, _ in observed}, {1})
        for outcome in outcomes:
            self.assertFalse(outcome.timed_out)
            self.assertEqual(outcome.pending_callback.updateSequence, 3)
            self.assertEqual(outcome.pending_callback.header.clientSessionId, outcome.request_key.clientSessionId)


if __name__ == "__main__":
    unittest.main()
