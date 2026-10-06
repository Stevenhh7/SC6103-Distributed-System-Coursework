package flight;

/** [A-01] 显式线协议数值；禁止使用 ordinal()。未知数值由 codec 按规范分类处理。 */
public enum Semantics {
    ALO(1),
    AMO(2);

    private final int code;

    Semantics(int code) { this.code = code; }

    public int code() { return code; }

    /** 数值转换工具；codec 需将非法数值转换成恰当的协议错误或丢弃处理。 */
    public static Semantics fromCode(int code) {
        for (Semantics value : values()) {
            if (value.code == code) return value;
        }
        throw new IllegalArgumentException("Unknown Semantics code: " + code);
    }
}
