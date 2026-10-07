"""核对器对接 C 的真实日志生成流程；传输/时钟为模拟，不能证明 Java 联调。"""

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import logging
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from client.config import ExperimentConfig
from client.event_log import LOGGER
from client.experiments import ExperimentFailure, run_case
from client.protocol import Semantics
from client.tests.helpers import FakeClock, PEER, SESSION, i32, make_invoker, packet
from .analyze_results import CASES, EvidenceError, analyze, load_events, main


def client_evidence(case="reply_loss_reserve", mode="amo"):
    wire_mode = 1 if mode == "alo" else 2
    seats = {"baseline": 9, "request_loss_reserve": 9,
             "reply_loss_reserve": 8 if mode == "alo" else 9,
             "all_reply_loss": 5 if mode == "alo" else 9}.get(case, 10)
    fare = {"baseline": 140, "reply_loss_set": 120,
            "reply_loss_increase": 140 if mode == "alo" else 120}.get(case, 100)
    def reply(body, op, request_id):
        return packet(body, op=op, request_id=request_id, mode=wire_mode)
    def details(seats, fare, request_id):
        return reply(struct.pack("!iiiiifi", 2026, 10, 17, 9, 30, fare, seats), 2, request_id)
    arrivals = [(0.1, details(10, 100, 1), PEER)]
    unknown = case in ("all_request_loss", "all_reply_loss")
    if case == "baseline":
        arrivals.extend([
            (0.2, reply(i32(2) + i32(1001) + i32(1002), 1, 2), PEER),
            (0.3, reply(i32(1001) + i32(9), 3, 3), PEER),
            (0.4, reply(i32(1001) + struct.pack("!f", 120), 5, 4), PEER),
            (0.5, reply(i32(1001) + struct.pack("!f", 140), 6, 5), PEER),
            (0.6, reply(i32(1001) + i32(1000), 4, 6), PEER),
            (1.7, details(seats, fare, 7), PEER),
        ])
    elif case == "monitor":
        arrivals.extend([(0.2, reply(i32(1001) + i32(1000), 4, 2), PEER),
                         (1.3, details(seats, fare, 3), PEER)])
    elif unknown:
        arrivals.append((5.2, details(seats, fare, 3), PEER))
    else:
        op = 6 if case.endswith("increase") else 5 if case.endswith("set") else 3
        body = i32(1001) + (i32(seats) if op == 3 else struct.pack("!f", fare))
        arrivals.extend([(1.2, reply(body, op, 2), PEER), (1.3, details(seats, fare, 3), PEER)])
    clock = FakeClock()
    invoker = make_invoker(clock, arrivals, semantics=Semantics[mode.upper()],
                           experiment=ExperimentConfig(1001, "Singapore", "Beijing", delta=20,
                                                       monitor_seconds=2))
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    old_level = LOGGER.level
    LOGGER.setLevel(logging.INFO)
    LOGGER.addHandler(handler)
    exit_code = 0
    try:
        with patch("client.invoker.time.monotonic", clock.monotonic), redirect_stdout(io.StringIO()):
            try:
                run_case(invoker, "reply_loss_reserve" if unknown else case)
            except ExperimentFailure:
                exit_code = 1
    finally:
        LOGGER.removeHandler(handler)
        LOGGER.setLevel(old_level)
        invoker.close()
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    proxy = [dict(event="DROP_ALL_TARGET", direction="requests" if case == "all_request_loss" else "replies",
                  sessionId=str(SESSION), requestId=2, targetSessionId=str(SESSION), targetRequestId=2,
                  operation=3, messageType=1 if case == "all_request_loss" else 2, mode=wire_mode)
             for _ in range(5)] if unknown else []
    return events, exit_code, proxy


class AnalyzerTest(unittest.TestCase):
    def setUp(self):
        self.events, self.exit_code, self.proxy = client_evidence()

    def check(self, events=None, case="reply_loss_reserve", mode="amo", exit_code=None, proxy=None):
        return analyze(self.events if events is None else events, case, mode, SESSION,
                       self.exit_code if exit_code is None else exit_code,
                       self.proxy if proxy is None else proxy)

    def item(self, event, request_id):
        return next(e for e in self.events if e.get("event") == event and e.get("requestId") == request_id)

    def test_all_sixteen_controlled_flows_use_actual_c_logging(self):
        for case in CASES:
            for mode in ("alo", "amo"):
                with self.subTest(case=case, mode=mode):
                    events, code, proxy = client_evidence(case, mode)
                    result = self.check(events, case, mode, code, proxy)
                    self.assertEqual("STATE_VERIFIED_NEEDS_A_LOG_REVIEW", result["result"])
                    self.assertNotIn("business_executions", result)
                    self.assertNotIn("cache_hits", result)
                    if case in ("baseline", "monitor"):
                        self.assertEqual("", result["mutation_attempts"])

    def test_missing_before_cannot_be_replaced_by_after(self):
        self.events.remove(self.item("REPLY", 1))
        with self.assertRaises(EvidenceError): self.check()

    def test_foreign_session_rejected(self):
        self.item("REPLY", 3)["sessionId"] = "11111111-1111-4111-8111-111111111111"
        with self.assertRaises(EvidenceError): self.check()

    def test_wrong_mode_rejected(self):
        self.item("REPLY", 2)["mode"] = "ALO"
        with self.assertRaises(EvidenceError): self.check()

    def test_missing_identity_is_not_accepted(self):
        for field in ("sessionId", "mode"):
            events = deepcopy(self.events)
            event = next(e for e in events if e.get("event") == "REPLY" and e.get("requestId") == 2)
            del event[field]
            with self.subTest(field=field), self.assertRaises(EvidenceError): self.check(events)

    def test_correct_state_without_retry_is_not_fault_verified(self):
        self.item("REPLY", 2)["attempt"] = 1
        with self.assertRaises(EvidenceError): self.check()

    def test_wrong_flight_or_input_rejected(self):
        self.item("REQUEST_CREATED", 1)["body"]["flightId"] = 1002
        with self.assertRaises(EvidenceError): self.check()

    def test_wrong_operation_rejected(self):
        self.item("REPLY", 2)["operation"] = 5
        with self.assertRaises(EvidenceError): self.check()

    def test_unexpected_state_rejected(self):
        self.item("REPLY", 3)["body"]["availableSeats"] = 8
        with self.assertRaises(EvidenceError): self.check()

    def test_duplicate_terminal_rejected(self):
        self.events.append(deepcopy(self.item("REPLY", 2)))
        with self.assertRaises(EvidenceError): self.check()

    def test_out_of_order_phases_rejected(self):
        a = self.events.index(self.item("REQUEST_CREATED", 3))
        b = self.events.index(self.item("REPLY", 2))
        self.events[a], self.events[b] = self.events[b], self.events[a]
        with self.assertRaises(EvidenceError): self.check()

    def test_missing_attempt_timeout_rejected(self):
        self.events.remove(self.item("ATTEMPT_TIMEOUT", 2))
        with self.assertRaises(EvidenceError): self.check()

    def test_retry_cannot_precede_previous_attempt_timeout(self):
        timeout_index = self.events.index(self.item("ATTEMPT_TIMEOUT", 2))
        send_index = next(i for i, e in enumerate(self.events)
                          if e.get("event") == "SEND" and e.get("requestId") == 2 and e.get("attempt") == 2)
        self.events[timeout_index], self.events[send_index] = self.events[send_index], self.events[timeout_index]
        with self.assertRaises(EvidenceError): self.check()

    def test_controlled_parameters_must_match(self):
        next(e for e in self.events if e["event"] == "CASE_START")["parameters"]["quantity"] = 2
        with self.assertRaises(EvidenceError): self.check()

    def test_unknown_exit_cannot_be_silently_accepted_as_success(self):
        events, code, proxy = client_evidence("all_reply_loss")
        with self.assertRaises(EvidenceError): self.check(events, "all_reply_loss", exit_code=0, proxy=proxy)

    def test_all_loss_requires_exact_actual_proxy_drops(self):
        events, code, proxy = client_evidence("all_request_loss")
        for bad in ([], proxy[:-1], proxy + [deepcopy(proxy[0])]):
            with self.subTest(count=len(bad)), self.assertRaises(EvidenceError):
                self.check(events, "all_request_loss", exit_code=code, proxy=bad)
        for field, value in (("requestId", 3), ("targetSessionId", "wrong"), ("direction", "replies"), ("mode", 1)):
            bad = deepcopy(proxy); bad[0][field] = value
            with self.subTest(field=field), self.assertRaises(EvidenceError):
                self.check(events, "all_request_loss", exit_code=code, proxy=bad)

    def test_incomplete_log_cli_writes_failure_analysis(self):
        with tempfile.TemporaryDirectory() as folder:
            log, output = Path(folder) / "client.jsonl", Path(folder) / "analysis.json"
            log.write_text('{"event":', encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = main(["--client-log", str(log), "--case", "baseline", "--mode", "amo",
                             "--session", str(SESSION), "--client-exit", "0", "--output", str(output)])
            self.assertEqual(1, code)
            self.assertEqual("FAILED_OR_INCOMPLETE", json.loads(output.read_text())["result"])
            with self.assertRaises(EvidenceError): load_events(log)


if __name__ == "__main__":
    unittest.main()
