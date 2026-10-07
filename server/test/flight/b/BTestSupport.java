package flight;

import java.lang.reflect.Field;
import java.net.InetSocketAddress;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

/** 无外部测试库；通过公开入口验证业务，反射仅用于极端状态与过期项清理验证。 */
final class BTestSupport {
    static final UUID SESSION = UUID.fromString("11111111-1111-4111-8111-111111111111");
    static final UUID OTHER_SESSION = UUID.fromString("22222222-2222-4222-8222-222222222222");
    static final InetSocketAddress PEER = new InetSocketAddress("127.0.0.1", 41001);
    static final InetSocketAddress OTHER_PEER = new InetSocketAddress("127.0.0.1", 41002);
    private static int passed;
    private static int failed;

    private BTestSupport() {}

    static void run(String name, Runnable test) {
        try {
            test.run();
            passed++;
            System.out.println("PASS " + name);
        } catch (Throwable ex) {
            failed++;
            System.out.println("FAIL " + name + ": " + ex);
            ex.printStackTrace(System.out);
        }
    }

    static void finish(String suite) {
        System.out.printf("%s: %d passed, %d failed%n", suite, passed, failed);
        if (failed != 0) throw new AssertionError("B tests failed");
    }

    static void equal(Object expected, Object actual) {
        if (!Objects.equals(expected, actual)) {
            throw new AssertionError("Expected " + expected + ", got " + actual);
        }
    }

    static void truth(boolean value) {
        if (!value) throw new AssertionError("Expected true");
    }

    static void rejects(Runnable action) {
        try {
            action.run();
        } catch (IllegalArgumentException expected) {
            return;
        }
        throw new AssertionError("Expected IllegalArgumentException");
    }

    static void immutable(Runnable action) {
        try {
            action.run();
        } catch (UnsupportedOperationException expected) {
            return;
        }
        throw new AssertionError("Expected immutable snapshot");
    }

    static <T extends ReplyBody> T body(ServiceResult result, Class<T> type) {
        equal(Status.OK, result.response().status());
        if (!type.isInstance(result.response().body())) throw new AssertionError("Unexpected reply body");
        return type.cast(result.response().body());
    }

    static void error(ServiceResult result, Status status) {
        equal(status, result.response().status());
        equal(0, result.callbacks().size());
        truth(result.monitorRegistration().isEmpty());
        truth(result.response().body() instanceof ErrorBody);
        String message = ((ErrorBody) result.response().body()).message();
        int bytes = message.getBytes(java.nio.charset.StandardCharsets.UTF_8).length;
        truth(bytes >= 1 && bytes <= ProtocolConstants.MAX_ERROR_UTF8_BYTES);
    }

    static Request request(int operation, RequestBody body, UUID session, int requestId) {
        // 直接业务测试不经过 codec，bodyLength 在此不作为网络消息发送。
        return new Request(new Header(ProtocolConstants.VERSION, MessageType.REQUEST, operation,
                session, requestId, Status.OK, Semantics.AMO, 0), body);
    }

    static int subscriptionCount(InMemoryMonitorService monitors) {
        try {
            Field field = InMemoryMonitorService.class.getDeclaredField("subscriptions");
            field.setAccessible(true);
            return ((Map<?, ?>) field.get(monitors)).size();
        } catch (ReflectiveOperationException ex) {
            throw new AssertionError(ex);
        }
    }

    static final class Harness {
        final InMemoryMonitorService monitors = new InMemoryMonitorService();
        final DefaultFlightService service = new DefaultFlightService(monitors);
        int requestId = 1;

        Harness() { service.loadSeedData(); }

        ServiceResult call(int operation, RequestBody body) {
            return call(operation, body, SESSION, PEER, 0L);
        }

        ServiceResult call(int operation, RequestBody body, UUID session, InetSocketAddress peer, long now) {
            return service.handle(request(operation, body, session, requestId++), new RequestContext(peer, now));
        }

        FlightDetails details(int id) { return body(call(2, new FlightQuery(id)), FlightDetails.class); }

        @SuppressWarnings("unchecked")
        Map<Integer, Flight> flights() {
            try {
                Field field = DefaultFlightService.class.getDeclaredField("flights");
                field.setAccessible(true);
                return (Map<Integer, Flight>) field.get(service);
            } catch (ReflectiveOperationException ex) {
                throw new AssertionError(ex);
            }
        }

        void replace(int id, float fare, int seats, int sequence) {
            Flight original = flights().get(id);
            flights().put(id, new Flight(id, original.source(), original.destination(), original.departure(),
                    fare, seats, sequence));
        }
    }
}
