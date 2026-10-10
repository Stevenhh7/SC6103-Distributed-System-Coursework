package flight;

/** Structural error, optionally carrying a safely decoded REQUEST identity.
 * This metadata is local only; it does not alter the v1 header or public codec signatures.
 */
public final class ProtocolException extends Exception {
    private static final long serialVersionUID = 1L;
    private final Header replyHeader;
    private final Status replyStatus;

    public ProtocolException(String message) { this(message, null, Status.MALFORMED_MESSAGE); }
    public ProtocolException(String message, Header replyHeader, Status replyStatus) {
        super(message); this.replyHeader = replyHeader; this.replyStatus = replyStatus;
    }
    public Header replyHeader() { return replyHeader; }
    public Status replyStatus() { return replyStatus; }
}
