package flight;

/**
 * [A-01/B-01] 完整回调逻辑视图；线上 type=3、op=4，消息体固定 12 字节。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record CallbackMessage(Header header, int flightId, int availableSeats, int updateSequence) {
}
