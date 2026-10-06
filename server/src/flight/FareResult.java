package flight;

/**
 * [A-01/B-01] 操作 5/6 共用结果；airfare 是总票价而非本次增量。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record FareResult(int flightId, float airfare) implements ReplyBody {
}
