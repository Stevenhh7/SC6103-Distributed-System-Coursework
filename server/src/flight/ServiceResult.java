package flight;

import java.util.List;
import java.util.Optional;
import java.util.Objects;

/**
 * [A-01/B-01] B 的单次执行结果；失败无事件，只有成功监控登记带 monitorRegistration。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record ServiceResult(Response response, List<CallbackEvent> callbacks, Optional<RegistrationKey> monitorRegistration) {
    public ServiceResult {
        callbacks = List.copyOf(callbacks);
        monitorRegistration = Objects.requireNonNull(monitorRegistration);
    }
}
