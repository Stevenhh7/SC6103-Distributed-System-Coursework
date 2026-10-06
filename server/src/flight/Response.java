package flight;

/**
 * [A-01/B-01] B 返回的业务响应；非 OK 时 body 必须为 ErrorBody。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record Response(Status status, ReplyBody body) {
}
