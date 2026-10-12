package flight;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.SocketException;
import java.net.UnknownHostException;
import java.util.Arrays;

/** A-03: one unconnected UDP socket for requests, replies and callbacks. */
public final class UdpTransport implements AutoCloseable {
    private final ServerConfig config;
    private volatile DatagramSocket socket;

    public UdpTransport(ServerConfig config) { this.config = config; }

    public synchronized void open() throws SocketException {
        if (socket != null) return;
        InetAddress address;
        try {
            address = Arrays.stream(InetAddress.getAllByName(config.bindAddress()))
                    .filter(a -> a instanceof Inet4Address).findFirst()
                    .orElseThrow(() -> new SocketException("Bind address must resolve to IPv4"));
        } catch (UnknownHostException ex) {
            throw new SocketException("Cannot resolve bind address: " + config.bindAddress());
        }
        DatagramSocket created = new DatagramSocket(null);
        try {
            created.setReuseAddress(false);
            created.bind(new InetSocketAddress(address, config.port()));
            created.setSoTimeout(ProtocolConstants.MAINTENANCE_INTERVAL_MS);
            socket = created;
        } catch (SocketException ex) { created.close(); throw ex; }
    }

    public ReceivedDatagram receive() throws IOException {
        byte[] buffer = new byte[ProtocolConstants.RECEIVE_BUFFER_BYTES];
        DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
        current().receive(packet);
        return new ReceivedDatagram(Arrays.copyOfRange(packet.getData(), packet.getOffset(),
                packet.getOffset() + packet.getLength()), (InetSocketAddress)packet.getSocketAddress());
    }

    public void send(byte[] payload, InetSocketAddress target) throws IOException {
        if (payload == null || payload.length < 32 || payload.length > ProtocolConstants.MAX_MESSAGE_BYTES) {
            throw new IOException("Outgoing application datagram size must be 32..1024");
        }
        if (target == null || !(target.getAddress() instanceof Inet4Address) || target.getPort() < 1) {
            throw new IOException("Target must be a resolved IPv4 endpoint");
        }
        current().send(new DatagramPacket(payload, payload.length, target));
    }

    private DatagramSocket current() throws SocketException {
        DatagramSocket result = socket;
        if (result == null || result.isClosed()) throw new SocketException("Transport is closed");
        return result;
    }

    @Override
    public synchronized void close() {
        if (socket != null) { socket.close(); socket = null; }
    }
}
