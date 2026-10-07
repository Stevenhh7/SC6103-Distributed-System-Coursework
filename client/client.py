"""[C-00/C-06] 六操作控制台与实验入口；业务请求统一通过 Invoker。"""

import argparse
import logging
from pathlib import Path
import sys
from typing import Optional, Sequence
from uuid import UUID

from .config import ClientConfig, ExperimentConfig, parse_request_selector
from .event_log import LOGGER, record
from .experiments import CASE_NAMES, ExperimentFailure, run_case
from .input_validation import location, positive_int, price
from .invoker import Invoker, SessionExhaustedError
from .models import FlightQuery, IncreaseAirfare, MonitorRegistration, Reservation, RouteQuery, SetAirfare
from .monitor import accepted_monitor, monitor_until_expiry
from .presentation import show_outcome
from .protocol import DEFAULT_MAX_ATTEMPTS, DEFAULT_PORT, DEFAULT_TIMEOUT_MS, Operation, Semantics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SC6103 Python UDP flight client")
    parser.add_argument("--server", default="127.0.0.1", help="server IPv4 address/hostname")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--semantics", choices=("alo", "amo"), default="amo")
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS, help="includes first send")
    parser.add_argument("--session-id", type=UUID, help="optional nonzero UUID for experiments")
    parser.add_argument("--drop-first-request", type=parse_request_selector, metavar="UUID:REQUEST_ID")
    parser.add_argument("--check", action="store_true", help="check configuration without opening a socket")
    parser.add_argument("--case", choices=CASE_NAMES, help="run a client experiment instead of the menu")
    parser.add_argument("--flight-id", type=int, help="actual experiment flight ID published by B")
    parser.add_argument("--source", help="baseline route source")
    parser.add_argument("--destination", help="baseline route destination")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--new-price", type=float, default=120.0)
    parser.add_argument("--delta", type=float, default=10.0)
    parser.add_argument("--monitor-seconds", type=int, default=5)
    parser.add_argument("--log-file", type=Path, help="append local JSON Lines evidence (UTF-8)")
    parser.add_argument("--verbose", action="store_true", help="show detailed event logs on stderr")
    return parser


def run_menu(invoker: Invoker) -> None:
    """监控接收期间阻塞菜单；输入错误返回菜单，EOF/Ctrl+C 交 main 清理。"""
    print(f"SC6103 航班客户端；模式 {invoker.config.semantics.name}；session={invoker.session_id}")
    while True:
        print("\n1 航线查询  2 航班详情  3 订座  4 监控余座  5 设置票价  6 增加票价  0 退出")
        choice = input("请选择：").strip()
        if choice == "0":
            return
        try:
            operation = Operation(int(choice))
            if operation == Operation.QUERY_ROUTE:
                body = RouteQuery(location(input("出发地：")), location(input("目的地：")))
            else:
                flight_id = positive_int(int(input("航班 ID：")))
                if operation == Operation.QUERY_FLIGHT:
                    body = FlightQuery(flight_id)
                elif operation == Operation.RESERVE_SEATS:
                    body = Reservation(flight_id, positive_int(int(input("订座数量："))))
                elif operation == Operation.MONITOR_SEATS:
                    body = MonitorRegistration(flight_id, positive_int(int(input("监控秒数 (1..3600)：")), 3600))
                elif operation == Operation.SET_AIRFARE:
                    body = SetAirfare(flight_id, price(float(input("新票价 (SGD)："))))
                else:
                    body = IncreaseAirfare(flight_id, price(float(input("增加金额 (SGD)：")), positive=True))
            outcome = invoker.invoke(operation, body)
        except ValueError as exc:
            print(f"输入错误：{exc}")
            continue
        if show_outcome(outcome) and operation == Operation.MONITOR_SEATS:
            monitor_until_expiry(invoker, accepted_monitor(outcome))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        experiment = None
        if args.case:
            if args.flight_id is None:
                raise ValueError("--case requires --flight-id")
            experiment = ExperimentConfig(args.flight_id, args.source, args.destination,
                                          args.quantity, args.new_price, args.delta, args.monitor_seconds)
            if args.case == "baseline" and (experiment.source is None or experiment.destination is None):
                raise ValueError("baseline requires --source and --destination")
        config = ClientConfig(server=args.server, port=args.port,
                              semantics=Semantics.ALO if args.semantics == "alo" else Semantics.AMO,
                              timeout_ms=args.timeout_ms, max_attempts=args.max_attempts,
                              session_id=args.session_id, drop_first_request=args.drop_first_request,
                              experiment=experiment)
        if config.drop_first_request and config.drop_first_request.clientSessionId != config.session_id:
            raise ValueError("--drop-first-request requires the same explicit --session-id")
    except ValueError as exc:
        parser.error(str(exc))

    invoker = Invoker(config)
    handlers: list[logging.Handler] = []
    old_level, old_propagate = LOGGER.level, LOGGER.propagate
    try:
        LOGGER.setLevel(logging.INFO)
        LOGGER.propagate = False
        if args.verbose:
            handlers.append(logging.StreamHandler())
        if args.log_file:
            args.log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(args.log_file, encoding="utf-8"))
        if not handlers:
            handlers.append(logging.NullHandler())
        for handler in handlers:
            handler.setFormatter(logging.Formatter("%(message)s"))
            LOGGER.addHandler(handler)
        if args.check:
            print("Client configuration and component wiring OK; no socket was opened.")
            print("Use python -m unittest discover -s client/tests -v to verify behavior.")
            return 0
        record("CLIENT_START", sessionId=str(invoker.session_id), mode=config.semantics.name,
               server=config.server, port=config.port)
        if args.case:
            run_case(invoker, args.case)
        else:
            run_menu(invoker)
        return 0
    except EOFError:
        print("\n输入结束，客户端已退出。")
        return 0
    except KeyboardInterrupt:
        print("\n已中断；已发送但未确认的操作可能已执行，请查询状态。")
        return 130
    except (OSError, SessionExhaustedError, ExperimentFailure, ValueError) as exc:
        print(f"客户端结束：{exc}。已发送但未确认的操作结果可能未知。", file=sys.stderr)
        record("CLIENT_ERROR", reason=str(exc))
        return 1
    finally:
        invoker.close()
        for handler in handlers:
            LOGGER.removeHandler(handler)
            handler.close()
        LOGGER.setLevel(old_level)
        LOGGER.propagate = old_propagate


if __name__ == "__main__":
    raise SystemExit(main())
