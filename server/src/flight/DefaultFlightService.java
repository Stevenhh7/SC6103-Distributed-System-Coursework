package flight;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/** [B-02..B-05] 单线程航班业务。A 只调用 handle，不直接修改航班或监控表。 */
public final class DefaultFlightService implements FlightService {
    private final Map<Integer, Flight> flights = new LinkedHashMap<>();
    private final InMemoryMonitorService monitors;

    public DefaultFlightService(InMemoryMonitorService monitors) {
        this.monitors = Objects.requireNonNull(monitors, "monitors");
    }

    /** [B-01] 启动加载；仅重置航班，完整实验复位应重启整个服务端。 */
    public void loadSeedData() {
        Map<Integer, Flight> initial = SeedData.createFlights();
        flights.clear();
        flights.putAll(initial);
    }

    @Override
    public ServiceResult handle(Request request, RequestContext context) {
        if (request == null || request.header() == null || request.body() == null || context == null) {
            return error(Status.INVALID_ARGUMENT, "Request and context are required");
        }
        RequestBody body = request.body();
        // 不使用 enum ordinal；以下数值是已冻结的 v1 operation code。
        return switch (request.header().operation()) {
            case 1 -> body instanceof RouteQuery query ? queryRoute(query) : wrongBody();
            case 2 -> body instanceof FlightQuery query ? queryFlight(query) : wrongBody();
            case 3 -> body instanceof Reservation reservation ? reserveSeats(reservation, context) : wrongBody();
            case 4 -> body instanceof MonitorRegistration registration
                    ? registerMonitor(registration,
                        new RequestKey(request.header().clientSessionId(), request.header().requestId()), context)
                    : wrongBody();
            case 5 -> body instanceof SetAirfare assignment ? setAirfare(assignment) : wrongBody();
            case 6 -> body instanceof IncreaseAirfare increase ? increaseAirfare(increase) : wrongBody();
            default -> error(Status.UNSUPPORTED_OPERATION, "Unsupported operation");
        };
    }

    private ServiceResult queryRoute(RouteQuery body) {
        final String source;
        final String destination;
        try {
            source = FlightValidation.location(body.source());
            destination = FlightValidation.location(body.destination());
        } catch (IllegalArgumentException ex) {
            return error(Status.INVALID_ARGUMENT, ex.getMessage());
        }
        List<Integer> ids = flights.values().stream()
                .filter(flight -> flight.source().equals(source) && flight.destination().equals(destination))
                .map(Flight::flightId).sorted().toList();
        return ids.isEmpty() ? error(Status.ROUTE_NOT_FOUND, "No flights match this route")
                : success(new RouteResult(ids));
    }

    private ServiceResult queryFlight(FlightQuery body) {
        if (body.flightId() <= 0) return invalidId();
        Flight flight = flights.get(body.flightId());
        return flight == null ? missingFlight() : success(new FlightDetails(flight.departure(),
                flight.airfare(), flight.availableSeats()));
    }

    private ServiceResult reserveSeats(Reservation body, RequestContext context) {
        if (body.flightId() <= 0) return invalidId();
        if (body.quantity() <= 0) return error(Status.INVALID_ARGUMENT, "Quantity must be positive");
        Flight flight = flights.get(body.flightId());
        if (flight == null) return missingFlight();
        if (body.quantity() > flight.availableSeats()) {
            return error(Status.INSUFFICIENT_SEATS, "Insufficient available seats");
        }
        if (flight.updateSequence() == Integer.MAX_VALUE) {
            return error(Status.LIMIT_EXCEEDED, "Seat update sequence limit reached");
        }
        Flight updated = new Flight(flight.flightId(), flight.source(), flight.destination(),
                flight.departure(), flight.airfare(), flight.availableSeats() - body.quantity(),
                flight.updateSequence() + 1);
        flights.put(updated.flightId(), updated);
        return new ServiceResult(new Response(Status.OK,
                new ReservationResult(updated.flightId(), updated.availableSeats())),
                monitors.eventsFor(updated.flightId(), updated.availableSeats(), updated.updateSequence(),
                        context.nowNanos()), Optional.empty());
    }

    private ServiceResult registerMonitor(MonitorRegistration body, RequestKey key,
                                          RequestContext context) {
        if (body.flightId() <= 0) return invalidId();
        if (body.durationSeconds() < 1 || body.durationSeconds() > ProtocolConstants.MAX_MONITOR_SECONDS) {
            return error(Status.INVALID_ARGUMENT, "Monitor duration must be 1..3600 seconds");
        }
        if (!flights.containsKey(body.flightId())) return missingFlight();
        final RegistrationKey registration;
        try {
            registration = monitors.register(key, context.peer(), body.flightId(), body.durationSeconds(),
                    context.nowNanos());
        } catch (IllegalArgumentException ex) {
            return error(Status.INVALID_ARGUMENT, ex.getMessage());
        }
        return new ServiceResult(new Response(Status.OK, new MonitorResult(body.flightId(),
                monitors.remainingMillis(registration, context.nowNanos()))), List.of(),
                Optional.of(registration));
    }

    private ServiceResult setAirfare(SetAirfare body) {
        if (body.flightId() <= 0) return invalidId();
        final float price;
        try {
            price = FlightValidation.price(body.newPrice());
        } catch (IllegalArgumentException ex) {
            return error(Status.INVALID_ARGUMENT, ex.getMessage());
        }
        Flight flight = flights.get(body.flightId());
        if (flight == null) return missingFlight();
        return saveFare(flight, price);
    }

    private ServiceResult increaseAirfare(IncreaseAirfare body) {
        if (body.flightId() <= 0) return invalidId();
        if (!Float.isFinite(body.delta()) || body.delta() <= 0.0f) {
            return error(Status.INVALID_ARGUMENT, "Airfare delta must be finite and positive");
        }
        Flight flight = flights.get(body.flightId());
        if (flight == null) return missingFlight();
        float total = flight.airfare() + body.delta();
        if (!Float.isFinite(total) || total <= flight.airfare()) {
            return error(Status.INVALID_ARGUMENT, "Airfare increase overflows or rounds to no change");
        }
        return saveFare(flight, total);
    }

    private ServiceResult saveFare(Flight flight, float price) {
        flights.put(flight.flightId(), new Flight(flight.flightId(), flight.source(), flight.destination(),
                flight.departure(), price, flight.availableSeats(), flight.updateSequence()));
        return success(new FareResult(flight.flightId(), price));
    }

    private static ServiceResult success(ReplyBody body) {
        return new ServiceResult(new Response(Status.OK, body), List.of(), Optional.empty());
    }

    private static ServiceResult error(Status status, String message) {
        return new ServiceResult(new Response(status, new ErrorBody(message)), List.of(), Optional.empty());
    }

    private static ServiceResult invalidId() {
        return error(Status.INVALID_ARGUMENT, "Flight ID must be positive");
    }

    private static ServiceResult missingFlight() {
        return error(Status.FLIGHT_NOT_FOUND, "Flight not found");
    }

    private static ServiceResult wrongBody() {
        return error(Status.INVALID_ARGUMENT, "Request body does not match operation");
    }
}
