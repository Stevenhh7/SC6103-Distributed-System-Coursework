package flight;

import java.net.InetSocketAddress;
import java.util.List;
import java.util.UUID;

import static flight.BTestSupport.*;

/** B-05/B-06：传入确定的 nanoTime 值，不使用 sleep 或真实网络。 */
public final class MonitorSelfTest {
    public static void main(String[] args) {
        run("monitor.register_identity_peer_and_milliseconds", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService();
            RegistrationKey key = m.register(new RequestKey(SESSION, 7), PEER, 1001, 10, 0);
            equal(new RegistrationKey(SESSION, 7, 1001), key); equal(10_000, m.remainingMillis(key, 0));
            equal(List.of(new CallbackEvent(key, PEER, 8, 1)), m.eventsFor(1001, 8, 1, 0));
        });
        run("monitor.remaining_floor_zero_before_exact_expiry", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey key = reg(m, 1, 1, 0);
            equal(999, m.remainingMillis(key, 1));
            equal(0, m.remainingMillis(key, 999_999_999L)); truth(m.isActive(key, 999_999_999L));
            truth(!m.isActive(key, 1_000_000_000L)); equal(0, m.remainingMillis(key, 1_000_000_000L));
        });
        run("monitor.expired_without_purge_no_events", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey key = reg(m, 1, 1, 0);
            equal(0, m.eventsFor(1001, 8, 1, 1_000_000_000L).size());
            truth(!m.isActive(key, 1_000_000_001L)); equal(0, m.remainingMillis(key, 1_000_000_001L));
        });
        run("monitor.purge_when_idle_and_keep_other_live_registration", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey a = reg(m, 1, 1, 0);
            RegistrationKey b = m.register(new RequestKey(OTHER_SESSION, 1), OTHER_PEER, 1001, 10, 0);
            equal(2, subscriptionCount(m));
            m.purgeExpired(1_000_000_000L); truth(!m.isActive(a, 1_000_000_000L)); truth(m.isActive(b, 1_000_000_000L));
            equal(1, subscriptionCount(m)); // 验证实际移除，而不只是读取时过滤。
            equal(List.of(b), m.eventsFor(1001, 8, 1, 1_000_000_000L).stream().map(CallbackEvent::registration).toList());
        });
        run("monitor.same_session_flight_replaces_old_identity_and_peer", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey a = reg(m, 1, 10, 0);
            RegistrationKey b = m.register(new RequestKey(SESSION, 2), OTHER_PEER, 1001, 20, 1_000_000_000L);
            truth(!m.isActive(a, 1_000_000_000L)); equal(0, m.remainingMillis(a, 1_000_000_000L));
            equal(20_000, m.remainingMillis(b, 1_000_000_000L));
            equal(List.of(new CallbackEvent(b, OTHER_PEER, 8, 1)), m.eventsFor(1001, 8, 1, 1_000_000_000L));
        });
        run("monitor.sessions_coexist_and_flights_are_isolated", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey a = reg(m, 1, 10, 0);
            RegistrationKey b = m.register(new RequestKey(OTHER_SESSION, 1), OTHER_PEER, 1001, 10, 0);
            RegistrationKey c = m.register(new RequestKey(SESSION, 2), PEER, 1002, 10, 0);
            equal(List.of(a, b), m.eventsFor(1001, 8, 1, 0).stream().map(CallbackEvent::registration).toList());
            equal(List.of(c), m.eventsFor(1002, 19, 1, 0).stream().map(CallbackEvent::registration).toList());
        });
        run("monitor_amo_read_only_replay_does_not_extend", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey key = reg(m, 1, 10, 0);
            equal(8_000, m.remainingMillis(key, 2_000_000_000L));
            equal(8_000, m.remainingMillis(key, 2_000_000_000L));
            equal(0, m.remainingMillis(key, 10_000_000_000L)); truth(!m.isActive(key, 10_000_000_000L));
        });
        run("monitor_alo_actual_reregistration_refreshes_same_key", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey key = reg(m, 1, 10, 0);
            equal(key, reg(m, 1, 10, 2_000_000_000L)); equal(10_000, m.remainingMillis(key, 2_000_000_000L));
            truth(m.isActive(key, 10_000_000_000L)); truth(!m.isActive(key, 12_000_000_000L));
        });
        run("monitor.remaining_unknown_replaced_or_null_zero", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService();
            equal(0, m.remainingMillis(new RegistrationKey(SESSION, 1, 1001), 0));
            equal(0, m.remainingMillis(null, 0)); truth(!m.isActive(null, 0));
        });
        run("monitor_max_duration_and_upper_clamp", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey key = reg(m, 1, 3600, 1_000_000_000L);
            equal(3_600_000, m.remainingMillis(key, 1_000_000_000L));
            equal(3_600_000, m.remainingMillis(key, 0));
            equal(0, m.remainingMillis(key, 3_601_000_000_000L));
        });
        run("monitor_negative_nanoTime_supported", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey key = reg(m, 1, 1, -2_000_000_000L);
            equal(500, m.remainingMillis(key, -1_500_000_000L)); truth(!m.isActive(key, -1_000_000_000L));
        });
        run("monitor_nanoTime_long_wrap_supported", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); long start = Long.MAX_VALUE - 500_000_000L;
            RegistrationKey key = reg(m, 1, 1, start); equal(1000, m.remainingMillis(key, start));
            equal(250, m.remainingMillis(key, start + 750_000_000L));
            truth(!m.isActive(key, start + 1_000_000_000L));
        });
        run("monitor_event_snapshot_survives_replacement_and_purge", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey key = reg(m, 1, 1, 0);
            List<CallbackEvent> old = m.eventsFor(1001, 8, 1, 0); immutable(() -> old.clear());
            reg(m, 2, 1, 0); m.purgeExpired(1_000_000_000L);
            equal(List.of(new CallbackEvent(key, PEER, 8, 1)), old);
            truth(!m.isActive(old.get(0).registration(), 0)); // A 必须在实际发送前复查。
        });
        run("monitor_rejected_registration_preserves_old_entry", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); RegistrationKey old = reg(m, 1, 10, 0);
            for (int duration : new int[]{0, -1, 3601}) {
                rejects(() -> m.register(new RequestKey(SESSION, 2), OTHER_PEER, 1001, duration, 0));
            }
            rejects(() -> m.register(new RequestKey(SESSION, 0), PEER, 1001, 10, 0));
            rejects(() -> m.register(new RequestKey(new UUID(0, 0), 1), PEER, 1001, 10, 0));
            rejects(() -> m.register(new RequestKey(null, 1), PEER, 1001, 10, 0));
            rejects(() -> m.register(null, PEER, 1001, 10, 0));
            rejects(() -> m.register(new RequestKey(SESSION, 2), PEER, 0, 10, 0));
            rejects(() -> m.register(new RequestKey(SESSION, 2), null, 1001, 10, 0));
            rejects(() -> m.register(new RequestKey(SESSION, 2), new InetSocketAddress("127.0.0.1", 0), 1001, 10, 0));
            rejects(() -> m.register(new RequestKey(SESSION, 2), InetSocketAddress.createUnresolved("invalid", 1), 1001, 10, 0));
            truth(m.isActive(old, 0)); equal(List.of(old), m.eventsFor(1001, 8, 1, 0).stream().map(CallbackEvent::registration).toList());
        });
        run("monitor_invalid_event_values_rejected", () -> {
            InMemoryMonitorService m = new InMemoryMonitorService(); reg(m, 1, 10, 0);
            rejects(() -> m.eventsFor(0, 8, 1, 0)); rejects(() -> m.eventsFor(1001, -1, 1, 0));
            rejects(() -> m.eventsFor(1001, 8, 0, 0)); rejects(() -> m.eventsFor(1001, 8, -1, 0));
            equal(1, m.eventsFor(1001, 0, Integer.MAX_VALUE, 0).size());
        });
        finish("MonitorSelfTest");
    }

    private static RegistrationKey reg(InMemoryMonitorService monitors, int id, int seconds, long now) {
        return monitors.register(new RequestKey(SESSION, id), PEER, 1001, seconds, now);
    }
}
