package flight;

/**
 * [A-01/B-01] 操作 3 请求：quantity 为预订数量，校验先于扣座。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record Reservation(int flightId, int quantity) implements RequestBody {
}
