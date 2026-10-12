package flight;

/** A-06: JSON Lines on stdout for external capture; never part of the wire protocol.
 * System.out is the console required by the coursework; no I/O stream is instantiated.
 */
final class ServerLog {
    private ServerLog() {}
    static synchronized void event(String event, Object... fields) {
        StringBuilder out = new StringBuilder("{\"event\":").append(quote(event))
                .append(",\"nanoTime\":").append(System.nanoTime());
        for (int i = 0; i < fields.length; i += 2) {
            out.append(',').append(quote(String.valueOf(fields[i]))).append(':');
            Object value = fields[i + 1];
            if (value == null) out.append("null");
            else if (value instanceof Number || value instanceof Boolean) out.append(value);
            else out.append(quote(String.valueOf(value)));
        }
        System.out.println(out.append('}'));
    }
    private static String quote(String s) {
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> { if (c < 32 || Character.isSurrogate(c)) out.append(String.format("\\u%04x", (int)c)); else out.append(c); }
            }
        }
        return out.append('"').toString();
    }
}
