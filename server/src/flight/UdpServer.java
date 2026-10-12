package flight;

import java.io.IOException;

/** [A-03] 单线程服务循环；构造时已把 A/B 模块接入同一个实例图。 */
public final class UdpServer implements AutoCloseable {
    private final UdpTransport transport;
    private volatile boolean stopped;
    private final ServerConfig config;
    private final InMemoryMonitorService monitors;
    private final DefaultFlightService flights;
    private final RequestDispatcher dispatcher;

    public UdpServer(ServerConfig config) {
        this.config = config;
        this.transport = new UdpTransport(config);
        this.monitors = new InMemoryMonitorService();
        this.flights = new DefaultFlightService(monitors);
        this.dispatcher = new RequestDispatcher(config, new BinaryProtocolCodec(),
                new InMemoryRequestHistory(), flights, monitors,
                new LossSimulator(config.dropFirstReply()), transport);
    }

    /**
     * [A-03]：初始化 SeedData -> open -> 循环清理/接收/分派 -> 退出清理。
     * 接收超时后仍要调用 purgeExpired；不为每个请求开线程。
     * 构造与 --check 不绑定端口；SERVER_READY 才表示初始化完成。
     */
    public void run() throws IOException {
        flights.loadSeedData();
        transport.open();
        ServerLog.event("SERVER_READY", "bind", config.bindAddress(), "port", config.port(), "mode", config.semantics());
        try {
            while (!stopped && !Thread.currentThread().isInterrupted()) {
                monitors.purgeExpired(System.nanoTime());
                try { dispatcher.handle(transport.receive()); }
                catch (java.net.SocketTimeoutException timeout) { /* Maintenance proceeds even while idle. */ }
                catch (java.net.SocketException ex) { if (!stopped) throw ex; }
            }
        } finally { close(); }
    }

    @Override
    public void close() {
        stopped = true;
        transport.close();
    }
}
