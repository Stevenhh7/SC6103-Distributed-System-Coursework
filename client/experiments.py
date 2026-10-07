"""[C-08] 客户端实验驱动；B 组织复位/验收，A 提供实际执行次数与缓存日志。"""

from dataclasses import asdict

from .event_log import record
from .invoker import Invoker
from .loss_simulator import LossSimulator
from .models import (
    FlightQuery, IncreaseAirfare, MonitorRegistration, RequestKey, Reservation,
    RouteQuery, SetAirfare,
)
from .monitor import accepted_monitor, monitor_until_expiry
from .presentation import show_outcome
from .protocol import Operation

CASE_NAMES = ("baseline", "request_loss_reserve", "reply_loss_reserve",
              "reply_loss_increase", "reply_loss_set", "monitor")


class ExperimentFailure(RuntimeError):
    """用例未取得全部成功确认；详细未知/错误结果已打印并记录。"""


def run_case(invoker: Invoker, case_name: str) -> None:
    """复用 Invoker；前后查询是明确的新只读请求，绝不自动补做超时写操作。"""
    if case_name not in CASE_NAMES:
        raise ValueError(f"unknown case: {case_name}")
    options = invoker.config.experiment
    if options is None:
        raise ValueError("--case requires --flight-id from the server seed manifest")
    if case_name == "baseline" and (options.source is None or options.destination is None):
        raise ValueError("baseline requires --source and --destination")
    print(f"实验 {case_name}，模式 {invoker.config.semantics.name}，session={invoker.session_id}")
    print("每例开始前由 B 重启服务端复位；以下只记录实际结果，执行次数须结合 A 的日志。")
    record("CASE_START", case=case_name, mode=invoker.config.semantics.name,
           sessionId=str(invoker.session_id), flightId=options.flight_id,
           parameters=asdict(options), timeoutMs=invoker.config.timeout_ms,
           maxAttempts=invoker.config.max_attempts)

    def call(label, operation, body):
        print(f"\n[{label}]")
        outcome = invoker.invoke(operation, body)
        ok = show_outcome(outcome)
        record("CASE_STEP", case=case_name, step=label, requestId=outcome.request_key.requestId,
               sessionId=str(outcome.request_key.clientSessionId), attempts=outcome.attempts,
               confirmed=not outcome.timed_out,
               status=None if outcome.reply is None else int(outcome.reply.header.status))
        return outcome, ok

    def finish_case(operations_ok: bool, failure_reason: str = "") -> None:
        # 包括 baseline 中途业务错误/未知：停止后续写操作，仍采集终态。
        # 终态查询成功不会把先前的未知写操作重新标成“已确认”。
        _, after_ok = call("after (read-only)", Operation.QUERY_FLIGHT, FlightQuery(options.flight_id))
        record("CASE_END", case=case_name, sessionId=str(invoker.session_id),
               mode=invoker.config.semantics.name, allConfirmed=bool(operations_ok and after_ok),
               reason=failure_reason)
        if not operations_ok or not after_ok:
            raise ExperimentFailure(failure_reason or "本例含错误或未知结果；请保留日志并结合服务端状态分析")

    if case_name.startswith(("request_loss_", "reply_loss_")):
        # 一次初态查询后才写入，故新进程写操作为 ID=2；先打印便于核对 A 的选择器。
        target = RequestKey(invoker.session_id, invoker.next_request_id + 1)
        print(f"写操作故障目标：{target.clientSessionId}:{target.requestId}", flush=True)
        if case_name == "request_loss_reserve":
            if invoker.config.drop_first_request not in (None, target):
                raise ValueError("--drop-first-request must match this case's write request key")
            invoker.loss_simulator = LossSimulator(target)
        elif invoker.config.drop_first_request is not None:
            raise ValueError("reply-loss cases require server-side loss only")
    _, ok = call("before", Operation.QUERY_FLIGHT, FlightQuery(options.flight_id))
    if not ok:
        record("CASE_END", case=case_name, sessionId=str(invoker.session_id),
               mode=invoker.config.semantics.name, allConfirmed=False, reason="initial_query_failed")
        raise ExperimentFailure("初态查询未成功，已停止本例，未发起写操作")

    if case_name in ("baseline", "monitor"):
        if case_name == "baseline":
            steps = (
                ("route", Operation.QUERY_ROUTE, RouteQuery(options.source, options.destination)),
                ("reserve", Operation.RESERVE_SEATS, Reservation(options.flight_id, options.quantity)),
                ("set", Operation.SET_AIRFARE, SetAirfare(options.flight_id, options.new_price)),
                ("increase", Operation.INCREASE_AIRFARE, IncreaseAirfare(options.flight_id, options.delta)),
            )
            for label, operation, body in steps:
                _, ok = call(label, operation, body)
                if not ok:
                    finish_case(False, f"{label} 未成功确认，已停止后续写操作并查询终态")
        outcome, ok = call("monitor", Operation.MONITOR_SEATS,
                           MonitorRegistration(options.flight_id, options.monitor_seconds))
        if not ok:
            finish_case(False, "监控未获成功确认，已查询终态")
        monitor_until_expiry(invoker, accepted_monitor(outcome))
    else:
        if case_name.endswith("reserve"):
            operation, body = Operation.RESERVE_SEATS, Reservation(options.flight_id, options.quantity)
        elif case_name.endswith("increase"):
            operation, body = Operation.INCREASE_AIRFARE, IncreaseAirfare(options.flight_id, options.delta)
        else:
            operation, body = Operation.SET_AIRFARE, SetAirfare(options.flight_id, options.new_price)
        _, ok = call("mutation", operation, body)
        # 即使写操作未知也只查询，不换 ID 再做一次写操作。
    finish_case(ok)
    print("本例调用已结束；ALO/AMO 执行次数、双监控和航班隔离仍需按实验步骤核对。")
