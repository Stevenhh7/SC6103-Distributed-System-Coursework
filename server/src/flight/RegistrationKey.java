package flight;

import java.util.UUID;

/**
 * [A-01/B-01] 监控登记身份；registrationRequestId 不能换成触发更新的订座 ID。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record RegistrationKey(UUID clientSessionId, int registrationRequestId, int flightId) {
}
