package flight;

/**
 * [A-01/B-01] UTC+8 起飞时间，线上为五个 i32；日期合法性由 B-01 校验。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record FlightTime(int year, int month, int day, int hour, int minute) {
}
