"""B runner 的端口检查及只读就绪探测；不增加生产接口。"""

import argparse
import json
import socket
import sys


def check_ports(ports):
    sockets = []
    try:
        for port in ports:
            if not 1 <= port <= 65535:
                raise ValueError("ports must be 1..65535")
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sockets.append(probe)
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("127.0.0.1", port))
    finally:
        for probe in sockets:
            probe.close()


def wait_ready(port, mode):
    # 使用独立 session 的只读查询；不占用正式用例的 session:1..N。
    from client.config import ClientConfig
    from client.invoker import Invoker
    from client.models import FlightDetails, FlightQuery
    from client.protocol import Semantics, Status
    invoker = Invoker(ClientConfig(port=port, semantics=Semantics[mode.upper()],
                                   timeout_ms=250, max_attempts=20))
    try:
        result = invoker.invoke(2, FlightQuery(1001))
        if result.timed_out or result.reply is None:
            raise ValueError("No matching query reply within 5 seconds; server is not ready")
        body = result.reply.response.body
        if result.reply.header.status != Status.OK or not isinstance(body, FlightDetails):
            raise ValueError("Server readiness query failed")
        if body.availableSeats != 10 or body.airfare != 100:
            raise ValueError("Server seed is not clean: expected 1001 seats=10 fare=100")
        return dict(event="SERVER_READY", sessionId=str(invoker.session_id),
                    requestId=result.request_key.requestId, attempts=result.attempts,
                    flightId=1001, availableSeats=body.availableSeats, airfare=body.airfare)
    finally:
        invoker.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    ports = subparsers.add_parser("ports")
    ports.add_argument("ports", type=int, nargs="+")
    ready = subparsers.add_parser("ready")
    ready.add_argument("--port", type=int, required=True)
    ready.add_argument("--mode", choices=("alo", "amo"), required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "ports":
            check_ports(args.ports)
            print(json.dumps(dict(event="PORTS_AVAILABLE", ports=args.ports)))
        else:
            print(json.dumps(wait_ready(args.port, args.mode)))
    except (OSError, ValueError) as exc:
        print(f"Runtime preflight failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
