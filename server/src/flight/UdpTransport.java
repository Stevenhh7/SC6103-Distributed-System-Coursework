package flight;

import java.io.IOException;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.net.SocketException;

/**
 * [A-03] UDP 传输骨架；IOException 仅为网络异常类型，不使用输入/输出流。
 * 构造不绑定端口；open/receive/send 由 A 实现，close 已提供资源清理。
 */
public final class UdpTransport implements AutoCloseable {
    private final ServerConfig config;
    private DatagramSocket socket;

    public UdpTransport(ServerConfig config) {
        this.config = config;
    }

    public void open() throws SocketException {
        // TODO(A-03)：绑定 UDP/IPv4，接收超时不超过 250ms 以便清理登记。
        throw new UnsupportedOperationException("[A-03] server UDP setup is not implemented");
    }

    public ReceivedDatagram receive() throws IOException {
        // TODO(A-03)：缓冲 65535，保留实际有效字节和源端点，区分超时与错误。
        throw new UnsupportedOperationException("[A-03] server UDP receive is not implemented");
    }

    public void send(byte[] payload, InetSocketAddress target) throws IOException {
        // TODO(A-03)：完整数据报一次发送；callback 也复用此 socket。
        throw new UnsupportedOperationException("[A-03] server UDP send is not implemented");
    }

    @Override
    public void close() {
        if (socket != null) {
            socket.close();
            socket = null;
        }
    }
}
