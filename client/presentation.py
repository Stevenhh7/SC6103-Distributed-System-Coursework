"""[C-06/C-08] 菜单和实验共用实际结果显示；不把超时解释成业务失败。"""

from .models import (
    CallOutcome, ErrorBody, FareResult, FlightDetails, MonitorResult,
    ReservationResult, RouteResult,
)
from .protocol import Status


def show_outcome(outcome: CallOutcome) -> bool:
    key = outcome.request_key
    print(f"Request {key.clientSessionId}:{key.requestId}; attempts: {outcome.attempts}")
    if outcome.timed_out:
        print("No confirmation received; execution result is unknown. For a reservation or fare change, "
              "query the current state before deciding whether to submit a new operation.")
        return False
    if outcome.reply is None:
        raise ValueError("confirmed outcome requires a reply")
    response = outcome.reply.response
    if response.status != Status.OK:
        message = response.body.message if isinstance(response.body, ErrorBody) else ""
        print(f"Server error {int(response.status)} ({response.status.name}): {message}")
        return False
    body = response.body
    if isinstance(body, RouteResult):
        print("Matching flights: " + ", ".join(map(str, body.flightIds)))
    elif isinstance(body, FlightDetails):
        d = body.departure
        print(f"Departure {d.year:04d}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d} UTC+8; "
              f"airfare {body.airfare:.2f} SGD; available seats {body.availableSeats}")
    elif isinstance(body, ReservationResult):
        print(f"Reservation successful: flight {body.flightId}, "
              f"available seats after this execution: {body.availableSeats}")
    elif isinstance(body, FareResult):
        print(f"Airfare updated: flight {body.flightId}, total airfare: {body.airfare:.2f} SGD")
    elif isinstance(body, MonitorResult):
        print(f"Monitor confirmed: flight {body.flightId}, remaining {body.remainingMillis} ms; "
              "menu input is paused during monitoring.")
    return True
