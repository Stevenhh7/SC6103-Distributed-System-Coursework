"""[C-07] 客户端请求丢失注入；回调接收不受这个开关影响。"""

from typing import Optional

from .models import RequestKey


class LossSimulator:
    """仅丢指定身份的第一次发送；重复调用也不会再次丢弃。"""

    def __init__(self, target: Optional[RequestKey]) -> None:
        self.target = target
        self._dropped = False

    def should_drop_request(self, key: RequestKey, attempt: int) -> bool:
        """仅首次目标发送返回 True；attempt 从 1 开始。

        丢弃后仍消耗一次发送尝试，Invoker 应照常等待超时。
        """
        if attempt < 1:
            raise ValueError("attempt starts at 1")
        if key == self.target and attempt == 1 and not self._dropped:
            self._dropped = True
            return True
        return False
