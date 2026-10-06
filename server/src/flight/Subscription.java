package flight;

import java.net.InetSocketAddress;

/**
 * [A-01/B-01] B 内部监控记录；expiryNanos 仅供服务端使用，绝不写入数据报。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record Subscription(RegistrationKey key, InetSocketAddress peer, long expiryNanos, int durationSeconds) {
}
