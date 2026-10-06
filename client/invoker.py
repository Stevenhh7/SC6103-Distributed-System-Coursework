"""[C-04] 可靠调用层骨架；由菜单与实验入口共同复用。"""

from uuid import uuid4

from .config import ClientConfig
from .loss_simulator import LossSimulator
from .models import CallOutcome, RequestBody
from .udp_transport import UdpTransport


class Invoker:
    """持有会话、编号、同一个 socket 和丢包器；不在构造时访问网络。"""

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self.session_id = config.session_id or uuid4()
        self.next_request_id = 1
        self.transport = UdpTransport(config)
        self.loss_simulator = LossSimulator(config.drop_first_request)

    def invoke(self, operation: int, body: RequestBody) -> CallOutcome:
        """TODO(C-04): 依规范第 8.2、9 节完成一次逻辑调用。

        1. 分配新 ID、只编码一次；重传不改变 ID/字节/源端口。
        2. 使用绝对等待截止时间，验证来源、会话、ID、操作与模式。
        3. 正常/错误回复结束调用；监控确认前的最新 callback 暂存。
        4. 尝试耗尽返回结果未知；禁止自动换 ID 再次执行业务。
        """
        raise NotImplementedError("[C-04] request/retry/reply matching is not implemented")

    def close(self) -> None:
        """菜单退出或发生异常时释放同一传输对象。"""
        self.transport.close()
