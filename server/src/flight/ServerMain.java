package flight;

import java.io.IOException;
import java.util.Arrays;

/** [A-00] Java 入口。帮助/框架检查可用；业务实现进度见 server/TODO.md。 */
public final class ServerMain {
    private ServerMain() {}

    public static void main(String[] args) {
        int exitCode = execute(args);
        if (exitCode != 0) System.exit(exitCode);
    }

    private static int execute(String[] args) {
        if (Arrays.asList(args).contains("--help") || Arrays.asList(args).contains("-h")) {
            printHelp();
            return 0;
        }
        try {
            ServerConfig config = ServerConfig.fromArgs(args);
            try (UdpServer server = new UdpServer(config)) {
                if (config.checkOnly()) {
                    System.out.println("Server scaffold OK: configuration, DTO classes and component wiring.");
                    System.out.println("UDP, codec, business, history and callbacks are NOT implemented; no port was bound.");
                    return 0;
                }
                server.run();
            }
            return 0;
        } catch (UnsupportedOperationException e) {
            System.err.println("Scaffold only: " + e.getMessage());
            return 2;
        } catch (IllegalArgumentException e) {
            System.err.println("Configuration error: " + e.getMessage());
            return 2;
        } catch (IOException e) {
            System.err.println("Network error: " + e.getMessage());
            return 1;
        }
    }

    private static void printHelp() {
        System.out.println("SC6103 Java server scaffold (network logic pending)");
        System.out.println("  --bind <IPv4>                  default: 0.0.0.0");
        System.out.println("  --port <1..65535>               default: 6789");
        System.out.println("  --semantics <alo|amo>           default: amo");
        System.out.println("  --drop-first-reply <UUID:ID>    configured target; injection pending");
        System.out.println("  --check                        check wiring without opening a socket");
        System.out.println("  --help                         show this help");
    }
}
