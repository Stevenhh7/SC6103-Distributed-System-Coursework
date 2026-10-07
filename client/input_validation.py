"""[C-06] 菜单/实验输入校验；服务端仍独立执行最终业务校验。"""

from .protocol import MAX_LOCATION_UTF8_BYTES, MAX_REQUEST_ID
from .protocol_codec import ProtocolError, to_binary32


def positive_int(value: int, maximum: int = MAX_REQUEST_ID) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise ValueError(f"请输入 1..{maximum} 的整数")
    return value


def location(value: str) -> str:
    # 只去掉 U+0020；不可用无参 strip() 改变协议规定的地点比较。
    trimmed = value.strip(" ")
    try:
        length = len(trimmed.encode("utf-8", errors="strict"))
    except UnicodeError as exc:
        raise ValueError("地点包含无法编码为 UTF-8 的字符") from exc
    if not trimmed or length > MAX_LOCATION_UTF8_BYTES:
        raise ValueError("地点不能为空，且最多 128 个 UTF-8 字节")
    return trimmed


def price(value: float, *, positive: bool = False) -> float:
    rounded = to_binary32(value)
    if rounded < 0 or (positive and rounded <= 0):
        raise ProtocolError("增加金额必须在 float32 转换后大于 0" if positive else "票价不能为负")
    return 0.0 if rounded == 0 else rounded
