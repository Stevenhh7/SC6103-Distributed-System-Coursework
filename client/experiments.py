"""[C-08] 实验入口骨架；A/B 负责各自用例和证据，C 组织运行。"""

from .invoker import Invoker


def run_case(invoker: Invoker, case_name: str) -> None:
    """TODO(C-08): 经同一 Invoker 运行指定用例并保存真实结果。

    不另写一套重试逻辑。每例恢复固定状态，分别观察请求丢失、回复丢失、
    全部回复丢失；运行后关闭丢包再查询最终状态，不把预期值写成实际结果。
    """
    raise NotImplementedError("[C-08] experiment runner is not implemented")
