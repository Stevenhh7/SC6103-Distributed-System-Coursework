package flight;

import java.io.IOException;

/** [A-03] 单线程服务循环骨架；构造时已把 A/B 模块接入同一个实例图。 */
public final class UdpServer implements AutoCloseable {
    private final UdpTransport transport;
    private final InMemoryMonitorService monitors;
    private final DefaultFlightService flights;
    private final RequestDispatcher dispatcher;

    public UdpServer(ServerConfig config) {
        this.transport = new UdpTransport(config);
        this.monitors = new InMemoryMonitorService();
        this.flights = new DefaultFlightService(monitors);
        this.dispatcher = new RequestDispatcher(config, new BinaryProtocolCodec(),
                new InMemoryRequestHistory(), flights, monitors,
                new LossSimulator(config.dropFirstReply()), transport);
    }

    /**
     * TODO(A-03)：初始化 SeedData -> open -> 循环清理/接收/分派 -> 退出清理。
     * 接收超时后仍要调用 purgeExpired；不为每个请求开线程。
     * 当前明确失败，不能把构造成功当作服务器已开始监听。
     */
    public void run() throws IOException {
        throw new UnsupportedOperationException("[A-03] server event loop is not implemented; see server/TODO.md");
    }

    @Override
    public void close() {
        transport.close();
    }
}
