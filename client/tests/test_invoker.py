"""确定时钟下的调用身份/重传测试，不用真实等待模拟网络丢失。"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from client.loss_simulator import LossSimulator
from client.invoker import SessionExhaustedError
from client.models import FlightQuery, MonitorRegistration, RequestKey, Reservation
from client.protocol import MAX_REQUEST_ID, Operation
from client.protocol_codec import encode_request
from client.tests.helpers import (
    SESSION, PEER, FakeClock, callback, detail, error, i32, make_invoker, monitor_reply, packet,
)


class InvokerTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.clock_patch = patch("client.invoker.time.monotonic", self.clock.monotonic)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

    def test_retransmit_same_bytes_and_encode_once(self):
        invoker = make_invoker(self.clock, [(1.1, detail(), PEER)])
        with patch("client.invoker.encode_request", wraps=encode_request) as encoder:
            outcome = invoker.invoke(2, FlightQuery(1001))
        self.assertEqual(outcome.attempts, 2)
        self.assertEqual(outcome.reply_received_at, 101.1)
        self.assertEqual(encoder.call_count, 1)
        self.assertEqual(invoker.transport.sent[0][1], invoker.transport.sent[1][1])
        self.assertEqual([at for at, _ in invoker.transport.sent], [100, 101])
        self.assertEqual(invoker.next_request_id, 2)

    def test_business_and_mode_errors_end_without_retry(self):
        for status in range(1, 10):
            with self.subTest(status=status):
                self.clock.now = 100
                invoker = make_invoker(self.clock, [(0.1, error(status=status), PEER)])
                outcome = invoker.invoke(2, FlightQuery(1001))
                self.assertFalse(outcome.timed_out)
                self.assertEqual(outcome.reply.header.status, status)
                self.assertEqual(outcome.attempts, 1)
                self.assertIsNone(outcome.pending_callback)
                self.assertEqual(len(invoker.transport.sent), 1)

    def test_all_identity_fields_and_source_must_match(self):
        events = [
            (0.1, detail(), ("127.0.0.2", 6789)),
            (0.2, detail(), ("127.0.0.1", 9999)),
            (0.3, detail(session=uuid4()), PEER),
            (0.4, detail(request_id=2), PEER),
            (0.5, detail(mode=1), PEER),
            (0.6, packet(i32(1001)+i32(8), op=3), PEER),
            (0.7, b"malformed", PEER),
            (0.8, callback(), PEER),
            (0.9, detail(), PEER),
        ]
        invoker = make_invoker(self.clock, events)
        outcome = invoker.invoke(2, FlightQuery(1001))
        self.assertEqual(outcome.reply_received_at, 100.9)
        self.assertEqual(outcome.attempts, 1)
        self.assertLess(invoker.transport.waits[-1], 201)

    def test_noise_cannot_extend_attempt_deadlines(self):
        events = [(n / 10, detail(request_id=99), PEER) for n in range(1, 20)]
        invoker = make_invoker(self.clock, events, max_attempts=2)
        outcome = invoker.invoke(2, FlightQuery(1001))
        self.assertTrue(outcome.timed_out)
        self.assertEqual(self.clock.now, 102)
        self.assertEqual([at for at, _ in invoker.transport.sent], [100, 101])

    def test_first_request_loss_consumes_attempt_and_waits(self):
        key = RequestKey(SESSION, 1)
        invoker = make_invoker(self.clock, [(1.1, detail(), PEER)], drop_first_request=key)
        outcome = invoker.invoke(2, FlightQuery(1001))
        self.assertEqual(outcome.attempts, 2)
        self.assertEqual(invoker.transport.sent[0][0], 101)
        self.assertEqual(len(invoker.transport.sent), 1)

    def test_all_requests_lost_result_unknown_without_send(self):
        invoker = make_invoker(self.clock)
        invoker.loss_simulator.should_drop_request = lambda key, attempt: True
        outcome = invoker.invoke(3, Reservation(1001, 1))
        self.assertTrue(outcome.timed_out)
        self.assertEqual(outcome.attempts, 5)
        self.assertEqual(self.clock.now, 105)
        self.assertEqual(invoker.transport.sent, [])
        self.assertEqual((outcome.reply, outcome.reply_received_at, outcome.pending_callback), (None, None, None))

    def test_all_replies_lost_no_extra_write_after_exhaustion(self):
        invoker = make_invoker(self.clock)
        outcome = invoker.invoke(3, Reservation(1001, 1))
        self.assertTrue(outcome.timed_out)
        self.assertEqual(len(invoker.transport.sent), 5)
        self.assertEqual(len({raw for _, raw in invoker.transport.sent}), 1)
        self.assertEqual(invoker.next_request_id, 2)

    def test_pending_callback_keeps_highest_matching_sequence(self):
        events = [(0.1, callback(8, flight=1002), PEER),
                  (0.2, callback(7, request_id=2), PEER),
                  (0.3, callback(4), PEER), (0.4, callback(2), PEER),
                  (0.5, callback(6, mode=1), PEER), (0.6, monitor_reply(), PEER)]
        invoker = make_invoker(self.clock, events)
        outcome = invoker.invoke(4, MonitorRegistration(1001, 3))
        self.assertEqual(outcome.pending_callback.updateSequence, 4)
        self.assertEqual(outcome.reply_received_at, 100.6)

    def test_pending_callbacks_never_confirm_and_do_not_extend_deadline(self):
        events = [(n/10, callback(n), PEER) for n in range(1, 20)]
        invoker = make_invoker(self.clock, events, max_attempts=2)
        outcome = invoker.invoke(4, MonitorRegistration(1001, 5))
        self.assertTrue(outcome.timed_out)
        self.assertIsNone(outcome.pending_callback)
        self.assertEqual(self.clock.now, 102)

    def test_monitor_error_discards_pending(self):
        invoker = make_invoker(self.clock, [(0.1, callback(), PEER), (0.2, error(op=4), PEER)])
        outcome = invoker.invoke(4, MonitorRegistration(1001, 3))
        self.assertIsNone(outcome.pending_callback)
        self.assertFalse(outcome.timed_out)

    def test_wrong_flight_or_excessive_duration_ignored(self):
        invoker = make_invoker(self.clock, [(0.1, monitor_reply(flight=1002), PEER),
                                           (0.2, monitor_reply(2000), PEER),
                                           (0.3, monitor_reply(0), PEER)])
        outcome = invoker.invoke(4, MonitorRegistration(1001, 1))
        self.assertEqual(outcome.reply_received_at, 100.3)
        self.assertEqual(outcome.reply.response.body.remainingMillis, 0)

    def test_late_reply_from_old_call_not_used_for_new_call(self):
        invoker = make_invoker(self.clock, [(1.1, detail(), PEER),
                                           (1.2, detail(request_id=2), PEER)], max_attempts=1)
        self.assertTrue(invoker.invoke(2, FlightQuery(1001)).timed_out)
        outcome = invoker.invoke(2, FlightQuery(1002))
        self.assertEqual(outcome.request_key.requestId, 2)
        self.assertEqual(outcome.reply_received_at, 101.2)

    def test_id_exhaustion_does_not_wrap_or_reopen_socket(self):
        invoker = make_invoker(self.clock, [(0.1, detail(request_id=MAX_REQUEST_ID), PEER)])
        invoker.next_request_id = MAX_REQUEST_ID
        self.assertFalse(invoker.invoke(2, FlightQuery(1001)).timed_out)
        with self.assertRaises(SessionExhaustedError):
            invoker.invoke(2, FlightQuery(1001))
        self.assertEqual(len(invoker.transport.sent), 1)

    def test_invalid_input_never_sends_or_consumes_id(self):
        invoker = make_invoker(self.clock)
        with self.assertRaises(ValueError):
            invoker.invoke(2, Reservation(1001, 1))
        self.assertEqual(invoker.next_request_id, 1)
        self.assertFalse(invoker.transport.opened)

    def test_sessions_are_independent(self):
        from client.config import ClientConfig
        from client.invoker import Invoker
        a, b = Invoker(ClientConfig()), Invoker(ClientConfig())
        self.assertNotEqual(a.session_id, b.session_id)
        self.assertEqual((a.next_request_id, b.next_request_id), (1, 1))

    def test_loss_simulator_target_and_once(self):
        target = RequestKey(SESSION, 7)
        loss = LossSimulator(target)
        self.assertFalse(loss.should_drop_request(RequestKey(uuid4(), 7), 1))
        self.assertFalse(loss.should_drop_request(RequestKey(SESSION, 1), 1))
        self.assertFalse(loss.should_drop_request(target, 2))
        self.assertTrue(loss.should_drop_request(target, 1))
        self.assertFalse(loss.should_drop_request(target, 1))
        self.assertFalse(loss.should_drop_request(target, 2))


if __name__ == "__main__":
    unittest.main()
