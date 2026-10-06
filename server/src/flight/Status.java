package flight;

/** [A-01] 显式线协议数值；禁止使用 ordinal()。未知数值由 codec 按规范分类处理。 */
public enum Status {
    OK(0),
    ROUTE_NOT_FOUND(1),
    FLIGHT_NOT_FOUND(2),
    INSUFFICIENT_SEATS(3),
    INVALID_ARGUMENT(4),
    MALFORMED_MESSAGE(5),
    UNSUPPORTED_OPERATION(6),
    SEMANTICS_MISMATCH(7),
    REQUEST_ID_REUSE(8),
    LIMIT_EXCEEDED(9);

    private final int code;

    Status(int code) { this.code = code; }

    public int code() { return code; }

    /** 数值转换工具；codec 需将非法数值转换成恰当的协议错误或丢弃处理。 */
    public static Status fromCode(int code) {
        for (Status value : values()) {
            if (value.code == code) return value;
        }
        throw new IllegalArgumentException("Unknown Status code: " + code);
    }
}
