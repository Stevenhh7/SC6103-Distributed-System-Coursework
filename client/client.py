"""[C-00/C-06] 控制台入口：参数与框架检查可用，菜单业务由 C 接手。"""

import argparse
import sys
from typing import Optional, Sequence
from uuid import UUID

from .config import ClientConfig, parse_request_selector
from .invoker import Invoker
from .protocol import DEFAULT_MAX_ATTEMPTS, DEFAULT_PORT, DEFAULT_TIMEOUT_MS, Semantics


def build_parser() -> argparse.ArgumentParser:
    """建立已约定的启动参数；check 只检查装配，不尝试连接服务器。"""
    parser = argparse.ArgumentParser(description="SC6103 Python client scaffold (network logic pending)")
    parser.add_argument("--server", default="127.0.0.1", help="server IPv4 address/hostname")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--semantics", choices=("alo", "amo"), default="amo")
    parser.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS, help="includes first send")
    parser.add_argument("--session-id", type=UUID, help="optional fixed UUID for experiments")
    parser.add_argument("--drop-first-request", type=parse_request_selector, metavar="UUID:REQUEST_ID")
    parser.add_argument("--check", action="store_true", help="check scaffold wiring without opening a socket")
    return parser


def run_menu(invoker: Invoker) -> None:
    """TODO(C-06): 六操作及退出菜单，输入校验后构造 models 中的请求体。

    查询/订座/监控/设置票价/增加票价都通过 invoke；错误用 status 显示。
    成功监控转入 monitor_until_expiry，结束后再显示菜单。
    """
    raise NotImplementedError("[C-06] menu and business commands are not implemented; see client/TODO.md")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """帮助与 --check 已可用；正常运行碰到待办时明确返回退出码 2。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = ClientConfig(
            server=args.server,
            port=args.port,
            semantics=Semantics.ALO if args.semantics == "alo" else Semantics.AMO,
            timeout_ms=args.timeout_ms,
            max_attempts=args.max_attempts,
            session_id=args.session_id,
            drop_first_request=args.drop_first_request,
        )
    except ValueError as exc:
        parser.error(str(exc))

    invoker = Invoker(config)
    try:
        if args.check:
            print("Client scaffold OK: configuration, DTO imports and component wiring.")
            print("UDP, codec, retries, menu and callbacks are NOT implemented; no socket was opened.")
            return 0
        run_menu(invoker)
    except NotImplementedError as exc:
        print(f"Scaffold only: {exc}", file=sys.stderr)
        return 2
    finally:
        invoker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
