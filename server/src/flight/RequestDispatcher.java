package flight;

import java.io.IOException;

/** A 的请求管线；依赖注入保持通信、业务和回调登记的责任边界。 */
public final class RequestDispatcher {
    private final ServerConfig config;
    private final ProtocolCodec codec;
    private final RequestHistory history;
    private final FlightService flights;
    private final MonitorService monitors;
    private final LossSimulator loss;
    private final UdpTransport transport;

    public RequestDispatcher(ServerConfig config, ProtocolCodec codec, RequestHistory history,
                             FlightService flights, MonitorService monitors,
                             LossSimulator loss, UdpTransport transport) {
        this.config = config;
        this.codec = codec;
        this.history = history;
        this.flights = flights;
        this.monitors = monitors;
        this.loss = loss;
        this.transport = transport;
    }

    /**
     * TODO(A-03/A-04/A-05)：严格按规范第 8.1 节实现。
     * 头部/模式检查 -> AMO 去重 -> 解码 -> B.handle -> 缓存 -> 回复 -> callback。
     * 命中缓存不调用 B.handle；监控确认仅通过 remainingMillis 只读刷新。
     * 即使丢回复也要继续尝试发送本次订座的 callback，发送前复查有效期。
     */
    public void handle(ReceivedDatagram datagram) throws IOException {
        throw new UnsupportedOperationException("[A-03] request pipeline is not implemented");
    }
}
