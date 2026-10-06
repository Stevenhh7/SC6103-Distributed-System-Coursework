package flight;

/** [A-01] 显式线协议数值；禁止使用 ordinal()。未知数值由 codec 按规范分类处理。 */
public enum MessageType {
    REQUEST(1),
    REPLY(2),
    CALLBACK(3);

    private final int code;

    MessageType(int code) { this.code = code; }

    public int code() { return code; }

    /** 数值转换工具；codec 需将非法数值转换成恰当的协议错误或丢弃处理。 */
    public static MessageType fromCode(int code) {
        for (MessageType value : values()) {
            if (value.code == code) return value;
        }
        throw new IllegalArgumentException("Unknown MessageType code: " + code);
    }
}
