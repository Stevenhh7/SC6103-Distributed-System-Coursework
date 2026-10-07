"""[C-06/C-08] 菜单和实验共用实际结果显示；不把超时解释成业务失败。"""

from .models import (
    CallOutcome, ErrorBody, FareResult, FlightDetails, MonitorResult,
    ReservationResult, RouteResult,
)
from .protocol import Status


def show_outcome(outcome: CallOutcome) -> bool:
    key = outcome.request_key
    print(f"请求 {key.clientSessionId}:{key.requestId}；尝试 {outcome.attempts} 次")
    if outcome.timed_out:
        print("未获得确认，执行结果未知。若为订座或改价，请先查询实际状态，再决定是否发起新操作。")
        return False
    if outcome.reply is None:
        raise ValueError("confirmed outcome requires a reply")
    response = outcome.reply.response
    if response.status != Status.OK:
        message = response.body.message if isinstance(response.body, ErrorBody) else ""
        print(f"服务端错误 {int(response.status)} ({response.status.name})：{message}")
        return False
    body = response.body
    if isinstance(body, RouteResult):
        print("匹配航班：" + ", ".join(map(str, body.flightIds)))
    elif isinstance(body, FlightDetails):
        d = body.departure
        print(f"起飞 {d.year:04d}-{d.month:02d}-{d.day:02d} {d.hour:02d}:{d.minute:02d} UTC+8；"
              f"票价 {body.airfare:.2f} SGD；余座 {body.availableSeats}")
    elif isinstance(body, ReservationResult):
        print(f"订座成功：航班 {body.flightId}，本次执行后余座 {body.availableSeats}")
    elif isinstance(body, FareResult):
        print(f"改价成功：航班 {body.flightId}，总票价 {body.airfare:.2f} SGD")
    elif isinstance(body, MonitorResult):
        print(f"监控已确认：航班 {body.flightId}，剩余 {body.remainingMillis} 毫秒；期间暂停菜单输入。")
    return True
