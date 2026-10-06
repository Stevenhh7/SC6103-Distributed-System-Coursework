package flight;

/**
 * [A-01/B-01] 操作 2 的 28 字节成功体，不额外编码 flightId。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record FlightDetails(FlightTime departure, float airfare, int availableSeats) implements ReplyBody {
}
