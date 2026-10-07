"""监控时间与序号测试；重复确认、噪声与处理延迟均不续期。"""

from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch
from uuid import uuid4

from client.models import AcceptedMonitor, RequestKey, MonitorRegistration
from client.monitor import accepted_monitor, monitor_until_expiry
from client.protocol_codec import decode_message
from client.tests.helpers import SESSION, PEER, FakeClock, callback, make_invoker, monitor_reply


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        timer = patch("client.monitor.time.monotonic", self.clock.monotonic)
        timer.start()
        self.addCleanup(timer.stop)
        self.output = io.StringIO()
        stdout = redirect_stdout(self.output)
        stdout.__enter__()
        self.addCleanup(stdout.__exit__, None, None, None)

    def accepted(self, deadline=101.0, pending=None):
        return AcceptedMonitor(RequestKey(SESSION, 1), 1001, deadline, pending)

    def test_pending_highest_then_only_increasing_and_current_identity(self):
        pending = decode_message(callback(4))
        events = [(0.1, callback(3), PEER), (0.2, callback(4), PEER),
                  (0.3, callback(10, flight=1002), PEER),
                  (0.4, callback(11, request_id=2), PEER),
                  (0.5, callback(12, session=uuid4()), PEER),
                  (0.6, callback(13, mode=1), PEER),
                  (0.7, callback(14), ("127.0.0.2", 6789)),
                  (0.8, callback(8), PEER), (0.9, callback(7), PEER)]
        invoker = make_invoker(self.clock, events)
        monitor_until_expiry(invoker, self.accepted(pending=pending))
        updates = [line for line in self.output.getvalue().splitlines() if "座位更新" in line]
        self.assertEqual(len(updates), 2)
        self.assertIn("序号 4", updates[0])
        self.assertIn("序号 8", updates[1])
        self.assertEqual(self.clock.now, 101)
        self.assertEqual(invoker.transport.sent, [])

    def test_repeated_confirmation_and_noise_do_not_extend(self):
        invoker = make_invoker(self.clock, [(0.1, monitor_reply(3600000), PEER),
                                           (0.5, b"broken", PEER), (0.9, monitor_reply(1000), PEER)])
        monitor_until_expiry(invoker, self.accepted())
        self.assertEqual(self.clock.now, 101)
        self.assertNotIn("座位更新", self.output.getvalue())

    def test_no_events_expires(self):
        invoker = make_invoker(self.clock)
        monitor_until_expiry(invoker, self.accepted())
        self.assertEqual(invoker.transport.waits, [1000])
        self.assertEqual(self.clock.now, 101)

    def test_zero_or_already_expired_never_receives_or_displays_pending(self):
        for deadline in (99, 100):
            invoker = make_invoker(self.clock)
            monitor_until_expiry(invoker, self.accepted(deadline, decode_message(callback())))
            self.assertEqual(invoker.transport.waits, [])
        self.assertNotIn("座位更新", self.output.getvalue())

    def test_confirmation_timestamp_not_menu_time(self):
        invoker = make_invoker(self.clock, [(0.2, monitor_reply(500), PEER)])
        outcome = invoker.invoke(4, MonitorRegistration(1001, 3))
        self.clock.now = 100.6  # 模拟结果打印耗时，不能重新起一个 500ms 定时器。
        accepted = accepted_monitor(outcome)
        self.assertAlmostEqual(accepted.deadline_monotonic, 100.7)
        monitor_until_expiry(invoker, accepted)
        self.assertAlmostEqual(self.clock.now, 100.7)
        self.assertAlmostEqual(invoker.transport.waits[-1], 100.0)

    def test_callback_arriving_after_deadline_not_shown(self):
        invoker = make_invoker(self.clock, [(1.001, callback(), PEER)])
        monitor_until_expiry(invoker, self.accepted())
        self.assertNotIn("座位更新", self.output.getvalue())
        self.assertEqual(self.clock.now, 101)

    def test_unknown_registration_cannot_start_monitor(self):
        invoker = make_invoker(self.clock, max_attempts=1)
        outcome = invoker.invoke(4, MonitorRegistration(1001, 1))
        with self.assertRaises(ValueError):
            accepted_monitor(outcome)


if __name__ == "__main__":
    unittest.main()
