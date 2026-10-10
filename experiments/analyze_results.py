"""B 受控单例取证核对；读取 C 原日志，不修改客户端或推断 A 执行次数。"""

import argparse
import json
import math
from pathlib import Path
from uuid import UUID

CASES = ("baseline", "request_loss_reserve", "reply_loss_reserve", "reply_loss_increase",
         "reply_loss_set", "all_request_loss", "all_reply_loss", "monitor")
DATE = dict(year=2026, month=10, day=17, hour=9, minute=30)
PARAMETERS = dict(flight_id=1001, source="Singapore", destination="Beijing", quantity=1,
                  new_price=120.0, delta=20.0, monitor_seconds=2)


class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def load_events(path):
    try:
        events = [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines()
                  if line.strip()]
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"Cannot read JSONL evidence: {path}: {exc}") from exc
    require(all(isinstance(event, dict) for event in events), "JSONL events must be objects")
    return events


def analyze(events, case, mode, session, client_exit, proxy_events=()):
    require(case in CASES and mode in ("alo", "amo"), "Invalid case/mode")
    session = str(UUID(str(session)))
    require(UUID(session).int != 0, "Session must be nonzero")
    unknown = case in ("all_request_loss", "all_reply_loss")
    client_case = "reply_loss_reserve" if unknown else case
    seats = {"baseline": 9, "request_loss_reserve": 9,
             "reply_loss_reserve": 8 if mode == "alo" else 9,
             "all_reply_loss": 5 if mode == "alo" else 9}.get(case, 10)
    fare = {"baseline": 140, "reply_loss_set": 120,
            "reply_loss_increase": 140 if mode == "alo" else 120}.get(case, 100)
    attempts = 5 if unknown else 2 if "loss" in case else 1
    require(all(isinstance(e, dict) for e in events), "Events must be objects")
    for event in events:
        identity_event = event.get("event") in ("CASE_START", "CASE_END", "CASE_STEP", "REQUEST_CREATED",
                                                "SEND", "DROP_REQUEST", "ATTEMPT_TIMEOUT", "REPLY",
                                                "RESULT_UNKNOWN", "MONITOR_START", "MONITOR_END", "CALLBACK")
        if "sessionId" in event or identity_event:
            require(event.get("sessionId") == session, "Mixed, wrong or missing client session")
        if "mode" in event or (identity_event and event.get("event") != "CASE_STEP"):
            require(event.get("mode") == mode.upper(), "Wrong/missing client mode")
    def named(name):
        return [e for e in events if e.get("event") == name]
    def one(name):
        items = named(name)
        require(len(items) == 1, f"Expected one {name}")
        return items[0]
    start, end = one("CASE_START"), one("CASE_END")
    require(start.get("case") == client_case and end.get("case") == client_case,
            "Wrong client case")
    require(start.get("flightId") == 1001 and start.get("parameters") == PARAMETERS
            and start.get("timeoutMs") == 1000 and start.get("maxAttempts") == 5,
            "Wrong controlled parameters/timeout/attempt limit")
    require(end.get("allConfirmed") is (not unknown), "Wrong CASE_END outcome")
    require(client_exit == (1 if unknown else 0), "Unexpected client exit code")
    require(not named("SEND_TIMEOUT") and not named("NETWORK_NOTICE"),
            "Extra network/send failure; controlled expectations do not apply")
    before = dict(departure=DATE, airfare=100, availableSeats=10)
    after = dict(departure=DATE, airfare=fare, availableSeats=seats)
    plan = [("before", 2, dict(flightId=1001), before, 1)]
    if case == "baseline":
        plan.extend([
            ("route", 1, dict(source="Singapore", destination="Beijing"), dict(flightIds=[1001, 1002]), 1),
            ("reserve", 3, dict(flightId=1001, quantity=1), dict(flightId=1001, availableSeats=9), 1),
            ("set", 5, dict(flightId=1001, newPrice=120), dict(flightId=1001, airfare=120), 1),
            ("increase", 6, dict(flightId=1001, delta=20), dict(flightId=1001, airfare=140), 1),
        ])
    if case in ("baseline", "monitor"):
        plan.append(("monitor", 4, dict(flightId=1001, durationSeconds=2), None, 1))
    else:
        operation = 6 if case.endswith("increase") else 5 if case.endswith("set") else 3
        field, value = {3: ("quantity", 1), 5: ("newPrice", 120), 6: ("delta", 20)}[operation]
        body = dict(flightId=1001, **{field: value})
        result = dict(flightId=1001, **({"availableSeats": seats} if operation == 3 else {"airfare": fare}))
        plan.append(("mutation", operation, body, result, attempts))
    plan.append(("after (read-only)", 2, dict(flightId=1001), after, 1))
    created, steps = named("REQUEST_CREATED"), named("CASE_STEP")
    require(len(created) == len(plan) and len(steps) == len(plan), "Missing/extra request or case step")
    require(len(named("REPLY")) + len(named("RESULT_UNKNOWN")) == len(plan),
            "Missing/duplicate terminal result")
    previous_step_index = events.index(start)
    for request_id, (label, operation, body, expected_body, count) in enumerate(plan, 1):
        request, step = created[request_id - 1], steps[request_id - 1]
        require(request.get("requestId") == request_id and request.get("operation") == operation
                and request.get("body") == body and request.get("timeoutMs") == 1000
                and request.get("maxAttempts") == 5, f"Wrong request {request_id}/{label}")
        related = [e for e in events if e.get("requestId") == request_id
                   and e.get("event") in ("SEND", "DROP_REQUEST", "ATTEMPT_TIMEOUT", "REPLY", "RESULT_UNKNOWN")]
        require(all(e.get("operation") == operation for e in related), f"Wrong operation for ID {request_id}")
        terminals = [e for e in related if e["event"] in ("REPLY", "RESULT_UNKNOWN")]
        require(len(terminals) == 1, f"Missing/duplicate result for ID {request_id}")
        terminal = terminals[0]
        is_unknown = unknown and request_id == 2
        require(terminal.get("event") == ("RESULT_UNKNOWN" if is_unknown else "REPLY")
                and terminal.get("attempt") == count, f"Wrong outcome/attempt count for ID {request_id}")
        if not is_unknown:
            require(terminal.get("status") == 0, f"Business error for ID {request_id}")
            actual_body = terminal.get("body")
            if operation == 4:
                require(isinstance(actual_body, dict) and actual_body.get("flightId") == 1001
                        and type(actual_body.get("remainingMillis")) is int
                        and 0 <= actual_body["remainingMillis"] <= 2000, "Wrong monitor result")
            else:
                require(actual_body == expected_body, f"Wrong response state for ID {request_id}/{label}")
        require(step.get("case") == client_case and step.get("step") == label
                and step.get("requestId") == request_id and step.get("attempts") == count
                and step.get("confirmed") is (not is_unknown)
                and step.get("status") == (None if is_unknown else 0), f"Wrong case step {label}")
        sends = [e for e in related if e["event"] in ("SEND", "DROP_REQUEST")]
        require([e.get("attempt") for e in sends] == list(range(1, count + 1)),
                f"Missing/duplicate sends for ID {request_id}")
        for attempt, send in enumerate(sends, 1):
            drop = case == "request_loss_reserve" and request_id == 2 and attempt == 1
            require(send["event"] == ("DROP_REQUEST" if drop else "SEND"), "Wrong request fault injection")
        timeouts = [e.get("attempt") for e in related if e["event"] == "ATTEMPT_TIMEOUT"]
        require(timeouts == list(range(1, count + 1 if is_unknown else count)),
                f"Wrong timeout evidence for ID {request_id}")
        expected_attempts = []
        for attempt, send in enumerate(sends, 1):
            expected_attempts.append((send["event"], attempt))
            if is_unknown or attempt < count:
                expected_attempts.append(("ATTEMPT_TIMEOUT", attempt))
        expected_attempts.append((terminal["event"], count))
        require([(e["event"], e.get("attempt")) for e in related] == expected_attempts,
                f"Send/timeout order differs for ID {request_id}")
        create_index, terminal_index, step_index = map(events.index, (request, terminal, step))
        require(previous_step_index < create_index < terminal_index < step_index,
                "Before/write/after evidence is out of order")
        require(all(create_index < events.index(e) < terminal_index for e in related if e is not terminal),
                "Attempt evidence is out of order")
        previous_step_index = step_index
    require(previous_step_index < events.index(end), "CASE_END precedes last query")
    known_ids = set(range(1, len(plan) + 1))
    require(all(e.get("requestId") in known_ids for e in events
                if e.get("event") in ("SEND", "DROP_REQUEST", "ATTEMPT_TIMEOUT", "REPLY", "RESULT_UNKNOWN")),
            "Unexpected logical request in client log")
    if case in ("baseline", "monitor"):
        for name in ("MONITOR_START", "MONITOR_END"):
            event = one(name)
            monitor_id = 6 if case == "baseline" else 2
            require(event.get("requestId") == monitor_id and event.get("operation") == 4
                    and event.get("flightId") == 1001, "Wrong monitor lifecycle identity")
        monitor_reply = next(e for e in named("REPLY") if e["requestId"] == monitor_id)
        require(events.index(monitor_reply) < events.index(one("MONITOR_START")) < events.index(one("MONITOR_END"))
                < events.index(created[-1]), "Missing monitor completion before after-query")
        start_event, end_event = one("MONITOR_START"), one("MONITOR_END")
        values = (start_event.get("monotonic"), start_event.get("deadline"), end_event.get("monotonic"))
        require(all(type(value) in (int, float) and math.isfinite(value) for value in values),
                "Monitor timing fields must be finite numbers")
        started, deadline, ended = values
        require(ended >= started and ended + 1e-6 >= deadline,
                "Monitor ended before its deadline")
        require(not named("CALLBACK"), "Unexpected callback in quiet controlled case")
    if unknown:
        drops = [e for e in proxy_events if e.get("event") == "DROP_ALL_TARGET"]
        direction = "requests" if case == "all_request_loss" else "replies"
        require(len(drops) == 5, "Need exactly five target drops in proxy evidence")
        for event in drops:
            require(event.get("sessionId") == session and event.get("requestId") == 2
                    and event.get("targetSessionId") == session and event.get("targetRequestId") == 2
                    and event.get("direction") == direction and event.get("operation") == 3
                    and event.get("messageType") == (1 if direction == "requests" else 2)
                    and event.get("mode") == (1 if mode == "alo" else 2), "Wrong proxy fault identity")
    observed_before = next(e["body"] for e in named("REPLY") if e["requestId"] == 1)
    observed_after = next(e["body"] for e in named("REPLY") if e["requestId"] == len(plan))
    return dict(initial_seats=observed_before["availableSeats"], final_seats=observed_after["availableSeats"],
                initial_fare=observed_before["airfare"], final_fare=observed_after["airfare"],
                mutation_attempts="" if case in ("baseline", "monitor") else attempts,
                client_unknown=unknown, result="STATE_VERIFIED_NEEDS_A_LOG_REVIEW",
                notes="Client identity/steps/state/attempts verified; proxy drops verified when used. "
                      "A business/cache/DROP_REPLY logs still require review. Baseline per-operation attempts are in client.jsonl.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-log", required=True)
    parser.add_argument("--proxy-log")
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--mode", choices=("alo", "amo"), required=True)
    parser.add_argument("--session", type=UUID, required=True)
    parser.add_argument("--client-exit", type=int, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = analyze(load_events(args.client_log), args.case, args.mode, args.session,
                         args.client_exit, load_events(args.proxy_log) if args.proxy_log else ())
        code = 0
    except EvidenceError as exc:
        result = dict(result="FAILED_OR_INCOMPLETE", notes=str(exc))
        code = 1
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
