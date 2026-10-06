package flight;

/**
 * [A-01/B-01] 解码后的请求；operation 与 body 类型的匹配由 A-02 检查。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record Request(Header header, RequestBody body) {
}
