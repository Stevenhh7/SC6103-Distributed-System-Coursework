package flight;

import java.net.InetSocketAddress;

/**
 * [A-01/B-01] A 的实际接收数据快照；data 只含该数据报有效字节，保留源端点。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record ReceivedDatagram(byte[] data, InetSocketAddress peer) {
    public ReceivedDatagram {
        data = data.clone();
    }

    @Override
    public byte[] data() { return data.clone(); }
}
