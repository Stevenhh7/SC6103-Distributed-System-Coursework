"""[C-05] 监控登记与回调接收；所有等待均使用确认时建立的单调时钟截止值。"""

import socket
import time
from typing import TYPE_CHECKING

from .models import AcceptedMonitor, CallbackMessage, CallOutcome, MonitorResult
from .protocol import Operation, Status

if TYPE_CHECKING:
    from .invoker import Invoker


def accepted_monitor(outcome: CallOutcome) -> AcceptedMonitor:
    """不能在菜单打印完成后重新计时，也不能把错误回复当作监控确认。"""
    if (outcome.timed_out or outcome.reply is None or outcome.reply_received_at is None
            or outcome.reply.header.status != Status.OK
            or outcome.reply.header.operation != Operation.MONITOR_SEATS
            or not isinstance(outcome.reply.response.body, MonitorResult)):
        raise ValueError("a successful monitor confirmation is required")
    result = outcome.reply.response.body
    return AcceptedMonitor(outcome.request_key, result.flightId,
                           outcome.reply_received_at + result.remainingMillis / 1000.0,
                           outcome.pending_callback)


def monitor_until_expiry(invoker: "Invoker", accepted: AcceptedMonitor) -> None:
    """只显示更大序号；先到 callback 暂存到确认后，重复确认绝不续期。"""
    largest_sequence = 0

    def display(message: CallbackMessage) -> None:
        nonlocal largest_sequence
        if (invoker.matches_callback(message, accepted.request_key, accepted.flight_id)
                and message.updateSequence > largest_sequence):
            largest_sequence = message.updateSequence
            print(f"座位更新：航班 {message.flightId}，余座 {message.availableSeats}，"
                  f"序号 {message.updateSequence}", flush=True)
            invoker.log("CALLBACK", accepted.request_key, Operation.MONITOR_SEATS,
                        flightId=message.flightId, availableSeats=message.availableSeats,
                        sequence=message.updateSequence)

    invoker.log("MONITOR_START", accepted.request_key, Operation.MONITOR_SEATS,
                flightId=accepted.flight_id, deadline=accepted.deadline_monotonic)
    # remainingMillis=0 或调用前已过期：立即结束，连暂存事件也不再显示。
    if time.monotonic() < accepted.deadline_monotonic and accepted.pending_callback is not None:
        display(accepted.pending_callback)
    while True:
        remaining = accepted.deadline_monotonic - time.monotonic()
        if remaining <= 0:
            break
        try:
            message, received_at = invoker.receive_message(remaining * 1000.0)
        except socket.timeout:
            continue
        except (ConnectionResetError, ConnectionRefusedError):
            continue
        if received_at >= accepted.deadline_monotonic:
            break
        if isinstance(message, CallbackMessage):
            display(message)
        # 所有普通回复（包含重复确认）及旧登记回调都不能改变 deadline。
    print(f"航班 {accepted.flight_id} 的本次监控已结束。", flush=True)
    invoker.log("MONITOR_END", accepted.request_key, Operation.MONITOR_SEATS,
                flightId=accepted.flight_id, lastSequence=largest_sequence)
