package flight;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** [B-01] 固定演示数据；时间字段统一解释为 UTC+8，票价为 SGD。 */
public final class SeedData {
    private SeedData() {}

    /** 每次返回独立的不可修改快照；1001 为订座和票价语义实验航班。 */
    public static Map<Integer, Flight> createFlights() {
        return validatedFlights(List.of(
                new Flight(1001, "Singapore", "Beijing", new FlightTime(2026, 10, 17, 9, 30), 100.0f, 10, 0),
                new Flight(1002, "Singapore", "Beijing", new FlightTime(2026, 10, 17, 14, 0), 180.0f, 20, 0),
                new Flight(1003, "Singapore", "Shanghai", new FlightTime(2026, 10, 17, 11, 15), 150.0f, 0, 0),
                new Flight(1004, "北京", "上海", new FlightTime(2026, 10, 18, 8, 45), 80.0f, 5, 0),
                new Flight(1005, "北京", "上海", new FlightTime(2026, 10, 18, 18, 10), 95.0f, 12, 0),
                new Flight(1006, "Beijing", "Singapore", new FlightTime(2026, 10, 19, 16, 20), 130.0f, 8, 0)
        ));
    }

    /** 包内复用/测试入口：先完整校验，再发布数据，不允许重复 ID 覆盖。 */
    static Map<Integer, Flight> validatedFlights(List<Flight> entries) {
        if (entries == null || entries.size() > ProtocolConstants.MAX_FLIGHTS) {
            throw new IllegalArgumentException("At most 100 initial flights are allowed");
        }
        Map<Integer, Flight> result = new LinkedHashMap<>();
        for (Flight entry : entries) {
            Flight validated = FlightValidation.seedFlight(entry);
            if (result.putIfAbsent(validated.flightId(), validated) != null) {
                throw new IllegalArgumentException("Duplicate flight ID: " + validated.flightId());
            }
        }
        return Collections.unmodifiableMap(result);
    }
}
