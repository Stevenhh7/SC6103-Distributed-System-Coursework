package flight;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

import static flight.BTestSupport.*;

/** B-01..B-04/B-06：独立业务与数据边界；不宣称网络/AMO 层已经通过。 */
public final class BusinessSelfTest {
    public static void main(String[] args) {
        run("seed.six_valid_flights_and_independent_snapshots", () -> {
            Map<Integer, Flight> a = SeedData.createFlights();
            equal(6, a.size()); truth(a != SeedData.createFlights());
            equal(10, a.get(1001).availableSeats()); equal(100.0f, a.get(1001).airfare());
            truth(a.values().stream().allMatch(f -> f.updateSequence() == 0));
            immutable(() -> a.clear());
        });
        run("seed.duplicate_id_is_rejected", () -> {
            Flight f = sample(7, "Singapore", 100.0f, 10, 0);
            rejects(() -> SeedData.validatedFlights(List.of(f, f)));
        });
        run("seed.100_accepted_101_rejected", () -> {
            List<Flight> entries = new ArrayList<>();
            for (int i = 1; i <= 100; i++) entries.add(sample(i, "Singapore", 1.0f, 1, 0));
            equal(100, SeedData.validatedFlights(entries).size());
            entries.add(sample(101, "Singapore", 1.0f, 1, 0));
            rejects(() -> SeedData.validatedFlights(entries));
        });
        run("seed.invalid_id_seats_sequence_or_null", () -> {
            rejects(() -> SeedData.validatedFlights(List.of(sample(0, "X", 1, 1, 0))));
            rejects(() -> SeedData.validatedFlights(List.of(sample(1, "X", 1, -1, 0))));
            rejects(() -> SeedData.validatedFlights(List.of(sample(1, "X", 1, 1, 1))));
            rejects(() -> SeedData.validatedFlights(Arrays.asList((Flight) null)));
            rejects(() -> SeedData.validatedFlights(null));
        });
        run("seed.invalid_dates_and_year_boundaries", () -> {
            for (FlightTime time : List.of(new FlightTime(0, 1, 1, 0, 0),
                    new FlightTime(10000, 1, 1, 0, 0), new FlightTime(2026, 2, 29, 0, 0),
                    new FlightTime(1900, 2, 29, 0, 0), new FlightTime(2026, 13, 1, 0, 0),
                    new FlightTime(2026, 1, 1, 24, 0), new FlightTime(2026, 1, 1, 0, 60))) {
                rejects(() -> FlightValidation.departure(time));
            }
            rejects(() -> FlightValidation.departure(null));
            FlightValidation.departure(new FlightTime(1, 1, 1, 0, 0));
            FlightValidation.departure(new FlightTime(9999, 12, 31, 23, 59));
            FlightValidation.departure(new FlightTime(2000, 2, 29, 0, 0));
        });
        run("seed.invalid_fares_and_positive_zero", () -> {
            for (float fare : new float[]{-1, Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY}) {
                rejects(() -> SeedData.validatedFlights(List.of(sample(1, "X", fare, 1, 0))));
            }
            equal(0, Float.floatToRawIntBits(SeedData.validatedFlights(
                    List.of(sample(1, "X", -0.0f, 1, 0))).get(1).airfare()));
        });
        run("seed.location_utf8_bounds_and_strict_unicode", () -> {
            equal("x".repeat(128), FlightValidation.location("x".repeat(128)));
            equal("中".repeat(42), FlightValidation.location("中".repeat(42)));
            rejects(() -> FlightValidation.location("x".repeat(129)));
            rejects(() -> FlightValidation.location("中".repeat(43)));
            rejects(() -> FlightValidation.location("\uD800"));
            rejects(() -> FlightValidation.location(null));
            rejects(() -> FlightValidation.location("   "));
            equal("X", SeedData.validatedFlights(List.of(sample(1, " X ", 1, 1, 0))).get(1).source());
        });
        run("route.multiple_matches_sorted_and_immutable", () -> {
            Harness h = new Harness();
            Flight a = h.flights().remove(1001); Flight b = h.flights().remove(1002);
            h.flights().put(1002, b); h.flights().put(1001, a);
            RouteResult result = body(h.call(1, new RouteQuery("Singapore", "Beijing")), RouteResult.class);
            equal(List.of(1001, 1002), result.flightIds()); immutable(() -> result.flightIds().clear());
        });
        run("route.chinese_and_ascii_space_normalization", () -> {
            Harness h = new Harness();
            equal(List.of(1004, 1005), body(h.call(1, new RouteQuery(" 北京 ", "上海")), RouteResult.class).flightIds());
            equal(List.of(1001, 1002), body(h.call(1, new RouteQuery(" Singapore ", " Beijing ")), RouteResult.class).flightIds());
        });
        run("route.case_tabs_nbsp_and_no_unicode_normalization", () -> {
            Harness h = new Harness();
            for (String source : List.of("singapore", "\tSingapore", "\u00A0Singapore", "\t")) {
                error(h.call(1, new RouteQuery(source, "Beijing")), Status.ROUTE_NOT_FOUND);
            }
            Flight original = h.flights().get(1001);
            h.flights().put(1001, new Flight(1001, "é", "Beijing", original.departure(), 100, 10, 0));
            error(h.call(1, new RouteQuery("e\u0301", "Beijing")), Status.ROUTE_NOT_FOUND);
        });
        run("route.missing_blank_null_or_oversized", () -> {
            Harness h = new Harness();
            error(h.call(1, new RouteQuery("Nowhere", "Beijing")), Status.ROUTE_NOT_FOUND);
            for (String source : Arrays.asList("", "   ", null, "中".repeat(43), "\uD800")) {
                error(h.call(1, new RouteQuery(source, "Beijing")), Status.INVALID_ARGUMENT);
            }
            error(h.call(1, new RouteQuery("Singapore", "")), Status.INVALID_ARGUMENT);
        });
        run("details.initial_values_and_missing_or_invalid_id", () -> {
            Harness h = new Harness(); FlightDetails d = h.details(1001);
            equal(new FlightTime(2026, 10, 17, 9, 30), d.departure()); equal(100.0f, d.airfare()); equal(10, d.availableSeats());
            error(h.call(2, new FlightQuery(9999)), Status.FLIGHT_NOT_FOUND);
            error(h.call(2, new FlightQuery(0)), Status.INVALID_ARGUMENT);
        });
        run("reserve.success_and_old_reply_snapshot", () -> {
            Harness h = new Harness(); FlightDetails before = h.details(1001);
            ServiceResult result = h.call(3, new Reservation(1001, 2));
            equal(new ReservationResult(1001, 8), body(result, ReservationResult.class));
            equal(8, h.details(1001).availableSeats()); equal(10, before.availableSeats());
            equal(1, h.flights().get(1001).updateSequence()); equal(0, result.callbacks().size());
        });
        run("reserve.invalid_quantity_has_no_side_effect", () -> {
            Harness h = new Harness(); Flight before = h.flights().get(1001);
            error(h.call(3, new Reservation(1001, 0)), Status.INVALID_ARGUMENT);
            error(h.call(3, new Reservation(1001, -1)), Status.INVALID_ARGUMENT);
            equal(before, h.flights().get(1001));
        });
        run("reserve.insufficient_or_zero_seats_unchanged", () -> {
            Harness h = new Harness(); Flight before = h.flights().get(1001);
            error(h.call(3, new Reservation(1001, 11)), Status.INSUFFICIENT_SEATS);
            error(h.call(3, new Reservation(1003, 1)), Status.INSUFFICIENT_SEATS);
            equal(before, h.flights().get(1001)); equal(0, h.flights().get(1003).updateSequence());
        });
        run("reserve.exact_capacity_and_integer_max_quantity", () -> {
            Harness h = new Harness();
            equal(0, body(h.call(3, new Reservation(1001, 10)), ReservationResult.class).availableSeats());
            h.replace(1002, 180, Integer.MAX_VALUE, 0);
            equal(0, body(h.call(3, new Reservation(1002, Integer.MAX_VALUE)), ReservationResult.class).availableSeats());
        });
        run("reserve.sequence_limit_no_wrap_no_mutation", () -> {
            Harness h = new Harness(); h.replace(1001, 100, 10, Integer.MAX_VALUE);
            Flight before = h.flights().get(1001);
            error(h.call(3, new Reservation(1001, 1)), Status.LIMIT_EXCEEDED);
            equal(before, h.flights().get(1001));
        });
        run("reserve.last_sequence_increment_allowed", () -> {
            Harness h = new Harness(); h.replace(1001, 100, 10, Integer.MAX_VALUE - 1);
            body(h.call(3, new Reservation(1001, 1)), ReservationResult.class);
            equal(Integer.MAX_VALUE, h.flights().get(1001).updateSequence());
            error(h.call(3, new Reservation(1001, 1)), Status.LIMIT_EXCEEDED);
            equal(9, h.details(1001).availableSeats());
        });
        run("reserve.callback_identity_two_sessions_and_flight_isolation", () -> {
            Harness h = new Harness();
            RegistrationKey a = h.call(4, new MonitorRegistration(1001, 10), SESSION, PEER, 0).monitorRegistration().orElseThrow();
            RegistrationKey b = h.call(4, new MonitorRegistration(1001, 10), OTHER_SESSION, OTHER_PEER, 0).monitorRegistration().orElseThrow();
            h.call(4, new MonitorRegistration(1002, 10), SESSION, PEER, 0);
            ServiceResult result = h.call(3, new Reservation(1001, 2), OTHER_SESSION, OTHER_PEER, 1_000_000_000L);
            equal(2, result.callbacks().size());
            equal(List.of(a, b), result.callbacks().stream().map(CallbackEvent::registration).toList());
            equal(List.of(PEER, OTHER_PEER), result.callbacks().stream().map(CallbackEvent::recipient).toList());
            truth(result.callbacks().stream().allMatch(e -> e.availableSeats() == 8 && e.updateSequence() == 1));
            immutable(() -> result.callbacks().clear());
            h.call(3, new Reservation(1001, 1)); equal(8, result.callbacks().get(0).availableSeats());
        });
        run("reserve.failed_operation_emits_no_callbacks", () -> {
            Harness h = new Harness(); h.call(4, new MonitorRegistration(1001, 10));
            error(h.call(3, new Reservation(1001, 11)), Status.INSUFFICIENT_SEATS);
            error(h.call(3, new Reservation(1001, -1)), Status.INVALID_ARGUMENT);
            equal(0, h.flights().get(1001).updateSequence());
        });
        run("business_entry_does_not_implement_amo_deduplication", () -> {
            Harness h = new Harness(); Request same = request(3, new Reservation(1001, 1), SESSION, 77);
            h.service.handle(same, new RequestContext(PEER, 0)); h.service.handle(same, new RequestContext(PEER, 0));
            equal(8, h.details(1001).availableSeats()); // A 必须在业务入口之前处理缓存命中。
        });
        run("set.idempotent_and_preserves_seats_sequence", () -> {
            Harness h = new Harness(); h.call(3, new Reservation(1001, 1));
            h.call(4, new MonitorRegistration(1001, 10));
            ServiceResult first = h.call(5, new SetAirfare(1001, 120));
            ServiceResult second = h.call(5, new SetAirfare(1001, 120));
            equal(new FareResult(1001, 120), body(first, FareResult.class)); equal(first.response(), second.response());
            equal(9, h.details(1001).availableSeats()); equal(1, h.flights().get(1001).updateSequence());
            equal(0, first.callbacks().size()); truth(first.monitorRegistration().isEmpty());
        });
        run("set.nonfinite_negative_rejected_and_no_mutation", () -> {
            Harness h = new Harness(); Flight before = h.flights().get(1001);
            for (float price : new float[]{Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY, -1}) {
                error(h.call(5, new SetAirfare(1001, price)), Status.INVALID_ARGUMENT);
            }
            equal(before, h.flights().get(1001));
        });
        run("set.negative_zero_normalized_and_max_float_allowed", () -> {
            Harness h = new Harness();
            equal(0, Float.floatToRawIntBits(body(h.call(5, new SetAirfare(1001, -0.0f)), FareResult.class).airfare()));
            equal(0, Float.floatToRawIntBits(h.details(1001).airfare()));
            equal(Float.MAX_VALUE, body(h.call(5, new SetAirfare(1001, Float.MAX_VALUE)), FareResult.class).airfare());
        });
        run("increase.nonidempotent_and_prior_reply_immutable", () -> {
            Harness h = new Harness();
            FareResult first = body(h.call(6, new IncreaseAirfare(1001, 20)), FareResult.class);
            equal(140.0f, body(h.call(6, new IncreaseAirfare(1001, 20)), FareResult.class).airfare());
            equal(120.0f, first.airfare()); equal(10, h.details(1001).availableSeats());
            equal(0, h.flights().get(1001).updateSequence());
        });
        run("increase.invalid_delta_no_mutation", () -> {
            Harness h = new Harness(); Flight before = h.flights().get(1001);
            for (float delta : new float[]{0, -0.0f, -1, Float.NaN, Float.POSITIVE_INFINITY, Float.NEGATIVE_INFINITY}) {
                error(h.call(6, new IncreaseAirfare(1001, delta)), Status.INVALID_ARGUMENT);
            }
            equal(before, h.flights().get(1001));
        });
        run("increase.float_overflow_and_round_to_no_change", () -> {
            Harness h = new Harness();
            error(h.call(6, new IncreaseAirfare(1001, Float.MIN_VALUE)), Status.INVALID_ARGUMENT);
            equal(100.0f, h.details(1001).airfare()); h.call(5, new SetAirfare(1001, Float.MAX_VALUE));
            error(h.call(6, new IncreaseAirfare(1001, Float.MAX_VALUE)), Status.INVALID_ARGUMENT);
            equal(Float.MAX_VALUE, h.details(1001).airfare());
        });
        run("increase.subnormal_from_zero_allowed_and_no_callback", () -> {
            Harness h = new Harness(); h.call(4, new MonitorRegistration(1001, 10)); h.call(5, new SetAirfare(1001, 0));
            ServiceResult result = h.call(6, new IncreaseAirfare(1001, Float.MIN_VALUE));
            equal(Float.MIN_VALUE, body(result, FareResult.class).airfare()); equal(0, result.callbacks().size());
        });
        run("all_id_operations.invalid_and_missing_flight", () -> {
            Harness h = new Harness();
            RequestBody[] invalid = {new FlightQuery(-1), new Reservation(-1, 1), new MonitorRegistration(-1, 1),
                    new SetAirfare(-1, 1), new IncreaseAirfare(-1, 1)};
            RequestBody[] missing = {new FlightQuery(9999), new Reservation(9999, 1), new MonitorRegistration(9999, 1),
                    new SetAirfare(9999, 1), new IncreaseAirfare(9999, 1)};
            for (int i = 0; i < invalid.length; i++) {
                error(h.call(i + 2, invalid[i]), Status.INVALID_ARGUMENT);
                error(h.call(i + 2, missing[i]), Status.FLIGHT_NOT_FOUND);
            }
        });
        run("invalid_parameters_checked_before_lookup", () -> {
            Harness h = new Harness();
            error(h.call(3, new Reservation(9999, 0)), Status.INVALID_ARGUMENT);
            error(h.call(4, new MonitorRegistration(9999, 0)), Status.INVALID_ARGUMENT);
            error(h.call(5, new SetAirfare(9999, Float.NaN)), Status.INVALID_ARGUMENT);
            error(h.call(6, new IncreaseAirfare(9999, -1)), Status.INVALID_ARGUMENT);
        });
        run("monitor_confirmation_and_duration_bounds", () -> {
            Harness h = new Harness();
            ServiceResult result = h.call(4, new MonitorRegistration(1001, 3600));
            equal(new MonitorResult(1001, 3_600_000), body(result, MonitorResult.class));
            truth(result.monitorRegistration().isPresent()); equal(0, result.callbacks().size());
            RegistrationKey key = result.monitorRegistration().orElseThrow();
            error(h.call(4, new MonitorRegistration(1001, 0)), Status.INVALID_ARGUMENT);
            error(h.call(4, new MonitorRegistration(1001, 3601)), Status.INVALID_ARGUMENT);
            truth(h.monitors.isActive(key, 0));
        });
        run("monitor.invalid_peer_does_not_replace_existing_registration", () -> {
            Harness h = new Harness(); RegistrationKey old = h.call(4, new MonitorRegistration(1001, 10)).monitorRegistration().orElseThrow();
            error(h.call(4, new MonitorRegistration(1001, 10), SESSION,
                    InetAddressSupport.unresolved(), 0), Status.INVALID_ARGUMENT);
            truth(h.monitors.isActive(old, 0));
        });
        run("dispatch_wrong_body_unknown_and_null_no_side_effect", () -> {
            Harness h = new Harness(); Flight before = h.flights().get(1001);
            error(h.call(3, new FlightQuery(1001)), Status.INVALID_ARGUMENT);
            error(h.call(65535, new FlightQuery(1001)), Status.UNSUPPORTED_OPERATION);
            error(h.service.handle(null, new RequestContext(PEER, 0)), Status.INVALID_ARGUMENT);
            error(h.service.handle(request(2, new FlightQuery(1001), SESSION, 1), null), Status.INVALID_ARGUMENT);
            equal(before, h.flights().get(1001));
        });
        run("load_seed_restores_flights_but_is_not_full_server_reset", () -> {
            Harness h = new Harness(); RegistrationKey key = h.call(4, new MonitorRegistration(1001, 10)).monitorRegistration().orElseThrow();
            h.call(3, new Reservation(1001, 2)); h.call(5, new SetAirfare(1001, 120)); h.service.loadSeedData();
            equal(10, h.details(1001).availableSeats()); equal(100.0f, h.details(1001).airfare());
            equal(0, h.flights().get(1001).updateSequence()); truth(h.monitors.isActive(key, 0));
        });
        finish("BusinessSelfTest");
    }

    private static Flight sample(int id, String source, float fare, int seats, int sequence) {
        return new Flight(id, source, "Beijing", new FlightTime(2026, 10, 17, 9, 30), fare, seats, sequence);
    }

    private static final class InetAddressSupport {
        static java.net.InetSocketAddress unresolved() {
            return java.net.InetSocketAddress.createUnresolved("example.invalid", 41001);
        }
    }
}
