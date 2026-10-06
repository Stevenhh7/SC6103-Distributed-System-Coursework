"""[C-05] 监控接收骨架；共享 Invoker 的 socket，不额外开启端口。"""

from typing import TYPE_CHECKING

from .models import AcceptedMonitor

if TYPE_CHECKING:
    from .invoker import Invoker


def monitor_until_expiry(invoker: "Invoker", accepted: AcceptedMonitor) -> None:
    """TODO(C-05): 按规范第 6 节过滤回调并在本地截止时间返回。

    检查服务器端点、session、监控 requestId、flightId 和递增序号；处理暂存事件。
    截止时间在收到确认时已确定，进入此函数或收到重复确认时都不能重新计时。
    无事件也要结束，接收超时不能超过剩余时间。
    """
    raise NotImplementedError("[C-05] callback monitoring is not implemented")
