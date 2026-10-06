package flight;

/**
 * [A-01/B-01] 操作 5 请求：幂等设置票价；线上必须是 binary32。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record SetAirfare(int flightId, float newPrice) implements RequestBody {
}
