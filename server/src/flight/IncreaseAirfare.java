package flight;

/**
 * [A-01/B-01] 操作 6 请求：非幂等增加票价；delta 必须有限且大于零。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record IncreaseAirfare(int flightId, float delta) implements RequestBody {
}
