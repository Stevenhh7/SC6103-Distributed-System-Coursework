package flight;

/** [A-02] 格式错误异常；业务错误必须使用 Response/ErrorBody，不抛此异常。 */
public final class ProtocolException extends Exception {
    private static final long serialVersionUID = 1L;

    public ProtocolException(String message) {
        super(message);
    }
}
