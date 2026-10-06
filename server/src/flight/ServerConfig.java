package flight;

import java.util.Optional;
import java.util.UUID;

/** [A-00] 启动参数已实现；checkOnly 只检查框架，不打开 socket。 */
public record ServerConfig(String bindAddress, int port, Semantics semantics,
                           Optional<RequestKey> dropFirstReply, boolean checkOnly) {
    public ServerConfig {
        if (bindAddress == null || bindAddress.isBlank()) {
            throw new IllegalArgumentException("bind address cannot be empty");
        }
        if (port < 1 || port > 65535) {
            throw new IllegalArgumentException("port must be in 1..65535");
        }
    }

    /** 支持分离的 --option value；故障选择器两端统一为 UUID:requestId。 */
    public static ServerConfig fromArgs(String[] args) {
        String bind = "0.0.0.0";
        int port = ProtocolConstants.DEFAULT_PORT;
        Semantics mode = Semantics.AMO;
        Optional<RequestKey> target = Optional.empty();
        boolean check = false;
        for (int i = 0; i < args.length; i++) {
            String option = args[i];
            switch (option) {
                case "--bind" -> bind = value(args, ++i, option);
                case "--port" -> port = Integer.parseInt(value(args, ++i, option));
                case "--semantics" -> mode = switch (value(args, ++i, option)) {
                    case "alo" -> Semantics.ALO;
                    case "amo" -> Semantics.AMO;
                    default -> throw new IllegalArgumentException("semantics must be alo or amo");
                };
                case "--drop-first-reply" -> target = Optional.of(parseSelector(value(args, ++i, option)));
                case "--check" -> check = true;
                default -> throw new IllegalArgumentException("unknown argument: " + option);
            }
        }
        return new ServerConfig(bind, port, mode, target, check);
    }

    private static String value(String[] args, int index, String option) {
        if (index >= args.length) throw new IllegalArgumentException("missing value for " + option);
        return args[index];
    }

    private static RequestKey parseSelector(String selector) {
        int separator = selector.lastIndexOf(':');
        if (separator < 1) throw new IllegalArgumentException("selector must be UUID:requestId");
        UUID session = UUID.fromString(selector.substring(0, separator));
        int id = Integer.parseInt(selector.substring(separator + 1));
        if (session.equals(new UUID(0L, 0L)) || id < 1) {
            throw new IllegalArgumentException("selector requires nonzero UUID and positive i32 ID");
        }
        return new RequestKey(session, id);
    }
}
