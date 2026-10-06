package flight;

/**
 * [A-01/B-01] 操作 4 结果：发送时的剩余毫秒；0 表示原登记已无有效时间。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record MonitorResult(int flightId, int remainingMillis) implements ReplyBody {
}
