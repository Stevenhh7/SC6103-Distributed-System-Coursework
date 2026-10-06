package flight;

import java.net.InetSocketAddress;

/**
 * [A-01/B-01] B 生成、A 发送的事件；发送前还需核对原登记有效期。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record CallbackEvent(RegistrationKey registration, InetSocketAddress recipient, int availableSeats, int updateSequence) {
}
