package flight;

import java.util.UUID;

/**
 * [A-01/B-01] 请求身份；同一逻辑调用重传不得改变 session 或 requestId。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record RequestKey(UUID clientSessionId, int requestId) {
}
