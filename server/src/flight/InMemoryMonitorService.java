package flight;

import java.net.InetSocketAddress;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** [B-05] 单线程登记表；业务与 A 的只读视图必须共用此实例。 */
public final class InMemoryMonitorService implements MonitorService {
    private final Map<RegistrationKey, Subscription> subscriptions = new LinkedHashMap<>();

    /** 只有实际执行业务才调用；AMO 缓存命中不得再次登记。 */
    public RegistrationKey register(RequestKey request, InetSocketAddress peer,
                                    int flightId, int durationSeconds, long nowNanos) {
        if (request == null || request.clientSessionId() == null
                || (request.clientSessionId().getMostSignificantBits() == 0L
                    && request.clientSessionId().getLeastSignificantBits() == 0L)
                || request.requestId() <= 0 || flightId <= 0
                || durationSeconds < 1 || durationSeconds > ProtocolConstants.MAX_MONITOR_SECONDS
                || peer == null || !(peer.getAddress() instanceof java.net.Inet4Address)
                || peer.getPort() < 1) {
            throw new IllegalArgumentException("Invalid monitor registration identity, peer or duration");
        }
        RegistrationKey key = new RegistrationKey(request.clientSessionId(), request.requestId(), flightId);
        // nanoTime 可为负或跨越 long 边界；有效期比较使用两个时刻之差。
        Subscription entry = new Subscription(key, peer, nowNanos + durationSeconds * 1_000_000_000L,
                durationSeconds);
        subscriptions.entrySet().removeIf(existing ->
                existing.getKey().clientSessionId().equals(key.clientSessionId())
                        && existing.getKey().flightId() == flightId);
        subscriptions.put(key, entry);
        return key;
    }

    /** 返回所有有效订阅的事件快照；此方法不发送网络消息，也不修改截止时间。 */
    public List<CallbackEvent> eventsFor(int flightId, int availableSeats,
                                        int updateSequence, long nowNanos) {
        if (flightId <= 0 || availableSeats < 0 || updateSequence <= 0) {
            throw new IllegalArgumentException("Invalid seat update");
        }
        List<CallbackEvent> events = new ArrayList<>();
        for (Subscription entry : subscriptions.values()) {
            if (entry.key().flightId() == flightId && active(entry, nowNanos)) {
                events.add(new CallbackEvent(entry.key(), entry.peer(), availableSeats, updateSequence));
            }
        }
        return List.copyOf(events);
    }

    @Override
    public void purgeExpired(long nowNanos) {
        subscriptions.values().removeIf(entry -> !active(entry, nowNanos));
    }

    @Override
    public boolean isActive(RegistrationKey key, long nowNanos) {
        Subscription entry = subscriptions.get(key);
        return entry != null && active(entry, nowNanos);
    }

    @Override
    public int remainingMillis(RegistrationKey key, long nowNanos) {
        Subscription entry = subscriptions.get(key);
        if (entry == null) return 0;
        long remainingNanos = entry.expiryNanos() - nowNanos;
        if (remainingNanos <= 0) return 0;
        return (int) Math.min(remainingNanos / 1_000_000L, entry.durationSeconds() * 1000L);
    }

    private static boolean active(Subscription entry, long nowNanos) {
        return entry.expiryNanos() - nowNanos > 0;
    }
}
