package flight;

/**
 * [A-01/B-01] 操作 3 结果：执行后的余座快照，AMO 重放不能重新查询最新余座。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record ReservationResult(int flightId, int availableSeats) implements ReplyBody {
}
