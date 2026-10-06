package flight;

/**
 * [A-01/B-01] B 的不可变航班快照；更新时替换记录，不能直接序列化整个对象。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record Flight(int flightId, String source, String destination, FlightTime departure, float airfare, int availableSeats, int updateSequence) {
}
