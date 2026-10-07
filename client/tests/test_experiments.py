"""C 的调用驱动测试；不声称模拟报文验证了 A 的执行次数或 B 的业务。"""

from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch

from client.config import ExperimentConfig
from client.experiments import ExperimentFailure, run_case
from client.models import RequestKey
from client.tests.helpers import (
    SESSION, PEER, FakeClock, detail, i32, make_invoker, monitor_reply, packet,
)


def seat_reply(request_id=2):
    return packet(i32(1001) + i32(8), op=3, request_id=request_id)


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        timer = patch("client.invoker.time.monotonic", self.clock.monotonic)
        timer.start()
        self.addCleanup(timer.stop)
        self.output = io.StringIO()
        stdout = redirect_stdout(self.output)
        stdout.__enter__()
        self.addCleanup(stdout.__exit__, None, None, None)

    def test_request_loss_case_drops_write_not_initial_query(self):
        invoker = make_invoker(self.clock, [(0.1, detail(), PEER), (1.2, seat_reply(), PEER),
                                           (1.3, detail(request_id=3), PEER)],
                               experiment=ExperimentConfig(1001))
        run_case(invoker, "request_loss_reserve")
        self.assertEqual([int.from_bytes(raw[20:24], "big") for _, raw in invoker.transport.sent], [1, 2, 3])
        self.assertEqual(invoker.transport.sent[1][0], 101.1)
        self.assertIn(f"写操作故障目标：{SESSION}:2", self.output.getvalue())
        self.assertIn("尝试 2 次", self.output.getvalue())

    def test_reply_loss_cases_use_same_invoker_and_read_final_state(self):
        cases = [("reply_loss_reserve", 3, i32(8)), ("reply_loss_increase", 6, bytes.fromhex("43020000")),
                 ("reply_loss_set", 5, bytes.fromhex("42f00000"))]
        for name, op, field in cases:
            with self.subTest(case=name):
                self.clock.now = 100
                reply = packet(i32(1001) + field, op=op, request_id=2)
                invoker = make_invoker(self.clock, [(0.1, detail(), PEER), (1.2, reply, PEER),
                                                   (1.3, detail(request_id=3), PEER)],
                                       experiment=ExperimentConfig(1001))
                run_case(invoker, name)
                sent = [raw for _, raw in invoker.transport.sent]
                self.assertEqual([int.from_bytes(raw[2:4], "big") for raw in sent], [2, op, op, 2])
                self.assertEqual(sent[1], sent[2])

    def test_unknown_write_queries_after_but_never_repeats_new_write(self):
        invoker = make_invoker(self.clock, [(0.1, detail(), PEER), (1.2, detail(request_id=3), PEER)],
                               max_attempts=1, experiment=ExperimentConfig(1001))
        with self.assertRaises(ExperimentFailure):
            run_case(invoker, "reply_loss_reserve")
        self.assertEqual([int.from_bytes(raw[2:4], "big") for _, raw in invoker.transport.sent], [2, 3, 2])
        self.assertIn("执行结果未知", self.output.getvalue())

    def test_prequery_failure_prevents_write(self):
        invoker = make_invoker(self.clock, max_attempts=1, experiment=ExperimentConfig(1001))
        with self.assertRaises(ExperimentFailure):
            run_case(invoker, "reply_loss_reserve")
        self.assertEqual(len(invoker.transport.sent), 1)
        self.assertEqual(int.from_bytes(invoker.transport.sent[0][1][2:4], "big"), 2)

    def test_baseline_runs_six_operations_and_blocks_for_monitor(self):
        events = [
            (0.1, detail(), PEER),
            (0.2, packet(i32(1) + i32(1001), op=1, request_id=2), PEER),
            (0.3, seat_reply(3), PEER),
            (0.4, packet(i32(1001) + bytes.fromhex("42f00000"), op=5, request_id=4), PEER),
            (0.5, packet(i32(1001) + bytes.fromhex("43020000"), op=6, request_id=5), PEER),
            (0.6, monitor_reply(500, request_id=6), PEER),
            (1.2, detail(request_id=7), PEER),
        ]
        invoker = make_invoker(self.clock, events, experiment=ExperimentConfig(1001, "北京", "SIN"))
        run_case(invoker, "baseline")
        self.assertEqual([int.from_bytes(raw[2:4], "big") for _, raw in invoker.transport.sent],
                         [2, 1, 3, 5, 6, 4, 2])
        self.assertAlmostEqual(invoker.transport.sent[-1][0], 101.1)

    def test_monitor_case_for_other_client(self):
        invoker = make_invoker(self.clock, [(0.1, detail(), PEER), (0.2, monitor_reply(0, request_id=2), PEER),
                                           (0.3, detail(request_id=3), PEER)],
                               experiment=ExperimentConfig(1001))
        run_case(invoker, "monitor")
        self.assertEqual([int.from_bytes(raw[2:4], "big") for _, raw in invoker.transport.sent], [2, 4, 2])

    def test_case_configuration_fails_before_network(self):
        invoker = make_invoker(self.clock)
        with self.assertRaises(ValueError):
            run_case(invoker, "unknown")
        with self.assertRaises(ValueError):
            run_case(invoker, "baseline")
        invoker = make_invoker(self.clock, experiment=ExperimentConfig(1001),
                               drop_first_request=RequestKey(SESSION, 1))
        with self.assertRaises(ValueError):
            run_case(invoker, "request_loss_reserve")
        self.assertEqual(invoker.transport.sent, [])


if __name__ == "__main__":
    unittest.main()
