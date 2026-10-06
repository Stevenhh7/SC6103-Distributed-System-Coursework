package flight;

import java.net.InetSocketAddress;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** TODO(B-05)：B 的登记表，FlightService 和 A 的只读视图必须共用此实例。 */
public final class InMemoryMonitorService implements MonitorService {
    private final Map<RegistrationKey, Subscription> subscriptions = new HashMap<>();

    /** TODO(B-05)：同 session/flight 替换旧登记；用 nowNanos 建立本机截止值。 */
    public RegistrationKey register(RequestKey request, InetSocketAddress peer,
                                    int flightId, int durationSeconds, long nowNanos) {
        throw new UnsupportedOperationException("[B-05] monitor registration is not implemented");
    }

    /** TODO(B-05)：返回所有有效订阅的事件快照；此方法不发送网络消息。 */
    public List<CallbackEvent> eventsFor(int flightId, int availableSeats,
                                        int updateSequence, long nowNanos) {
        throw new UnsupportedOperationException("[B-05] callback collection is not implemented");
    }

    @Override
    public void purgeExpired(long nowNanos) {
        throw new UnsupportedOperationException("[B-05] expiry cleanup is not implemented");
    }

    @Override
    public boolean isActive(RegistrationKey key, long nowNanos) {
        throw new UnsupportedOperationException("[B-05] subscription check is not implemented");
    }

    @Override
    public int remainingMillis(RegistrationKey key, long nowNanos) {
        throw new UnsupportedOperationException("[B-05] remaining lease calculation is not implemented");
    }
}
