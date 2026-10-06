package flight;

import java.net.InetSocketAddress;
import java.util.Optional;
import java.util.Objects;

/**
 * [A-01/B-01] AMO 历史快照；字节数组必须复制，监控确认只读刷新剩余时间。
 * 结构已定义；业务/协议范围校验由对应 TODO 任务完成，不在 DTO 中伪造结果。
 */
public record HistoryEntry(InetSocketAddress peer, byte[] originalRequest, Response originalResponse, byte[] encodedReply, Optional<RegistrationKey> monitorRegistration) {
    public HistoryEntry {
        originalRequest = originalRequest.clone();
        encodedReply = encodedReply.clone();
        monitorRegistration = Objects.requireNonNull(monitorRegistration);
    }

    @Override
    public byte[] originalRequest() { return originalRequest.clone(); }

    @Override
    public byte[] encodedReply() { return encodedReply.clone(); }
}
