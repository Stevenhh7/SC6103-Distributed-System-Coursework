package flight;

/**
 * [A-01/B-01] 操作 4 请求：时长单位为秒，与成功回复中的毫秒区分。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record MonitorRegistration(int flightId, int durationSeconds) implements RequestBody {
}
