package flight;

/**
 * [A-01/B-01] 完整回复的逻辑视图；header.status 必须等于 response.status。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record Reply(Header header, Response response) {
}
