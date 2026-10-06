package flight;

/**
 * [A-01/B-01] 操作 2 请求：查询指定航班详情。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record FlightQuery(int flightId) implements RequestBody {
}
