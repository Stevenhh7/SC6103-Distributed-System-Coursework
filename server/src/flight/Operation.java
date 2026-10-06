package flight;

/** [A-01] 显式线协议数值；禁止使用 ordinal()。未知数值由 codec 按规范分类处理。 */
public enum Operation {
    QUERY_ROUTE(1),
    QUERY_FLIGHT(2),
    RESERVE_SEATS(3),
    MONITOR_SEATS(4),
    SET_AIRFARE(5),
    INCREASE_AIRFARE(6);

    private final int code;

    Operation(int code) { this.code = code; }

    public int code() { return code; }

    /** 数值转换工具；codec 需将非法数值转换成恰当的协议错误或丢弃处理。 */
    public static Operation fromCode(int code) {
        for (Operation value : values()) {
            if (value.code == code) return value;
        }
        throw new IllegalArgumentException("Unknown Operation code: " + code);
    }
}
