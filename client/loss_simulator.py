"""[C-07] 客户端请求丢失注入；回调接收不受这个开关影响。"""

from typing import Optional

from .models import RequestKey


class LossSimulator:
    """TODO(C-07): 为目标 RequestKey 保存是否已丢弃第一次发送的状态。"""

    def __init__(self, target: Optional[RequestKey]) -> None:
        self.target = target

    def should_drop_request(self, key: RequestKey, attempt: int) -> bool:
        """TODO(C-07): 仅首次目标发送返回 True；attempt 从 1 开始。

        丢弃后仍消耗一次发送尝试，Invoker 应照常等待超时。
        """
        raise NotImplementedError("[C-07] request loss simulation is not implemented")
