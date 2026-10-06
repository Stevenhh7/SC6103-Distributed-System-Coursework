package flight;

/** [A-01] 协议 v1.0 的单位与边界；A/C 必须同步修改两端和规范。 */
public final class ProtocolConstants {
    public static final int VERSION = 1;
    public static final int HEADER_BYTES = 32;
    public static final int MAX_MESSAGE_BYTES = 1024;
    public static final int MAX_BODY_BYTES = MAX_MESSAGE_BYTES - HEADER_BYTES;
    public static final int RECEIVE_BUFFER_BYTES = 65535;
    public static final int CALLBACK_BODY_BYTES = 12;
    public static final int MAX_LOCATION_UTF8_BYTES = 128;
    public static final int MAX_ERROR_UTF8_BYTES = 256;
    public static final int MAX_FLIGHTS = 100;
    public static final int MAX_MONITOR_SECONDS = 3600;
    public static final int MAX_REQUEST_ID = Integer.MAX_VALUE;
    public static final int DEFAULT_PORT = 6789;
    public static final int DEFAULT_TIMEOUT_MS = 1000;
    public static final int DEFAULT_MAX_ATTEMPTS = 5;
    public static final int MAINTENANCE_INTERVAL_MS = 250;

    private ProtocolConstants() {}
}
