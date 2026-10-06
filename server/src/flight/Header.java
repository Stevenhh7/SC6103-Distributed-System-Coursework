package flight;

import java.util.UUID;

/**
 * [A-01/B-01] 公共头部 DTO：reserved 由 codec 固定写 0，bodyLength 不包含 32 字节头部。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record Header(int version, MessageType messageType, int operation, UUID clientSessionId, int requestId, Status status, Semantics semantics, int bodyLength) {
}
