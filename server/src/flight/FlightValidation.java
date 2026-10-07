package flight;

import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.time.DateTimeException;
import java.time.LocalDateTime;

/** B 内部字段校验；不增加线协议或公共 DTO。 */
final class FlightValidation {
    private FlightValidation() {}

    static String location(String value) {
        if (value == null) throw new IllegalArgumentException("Location is required");
        int start = 0;
        int end = value.length();
        while (start < end && value.charAt(start) == ' ') start++;
        while (end > start && value.charAt(end - 1) == ' ') end--;
        String normalized = value.substring(start, end);
        if (normalized.isEmpty()) throw new IllegalArgumentException("Location must not be empty");
        try {
            int bytes = StandardCharsets.UTF_8.newEncoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
                    .encode(CharBuffer.wrap(normalized)).remaining();
            if (bytes > ProtocolConstants.MAX_LOCATION_UTF8_BYTES) {
                throw new IllegalArgumentException("Location exceeds 128 UTF-8 bytes");
            }
        } catch (CharacterCodingException ex) {
            throw new IllegalArgumentException("Location contains invalid Unicode", ex);
        }
        return normalized;
    }

    static float price(float value) {
        if (!Float.isFinite(value) || value < 0.0f) {
            throw new IllegalArgumentException("Airfare must be finite and nonnegative");
        }
        return value == 0.0f ? 0.0f : value;
    }

    static void departure(FlightTime time) {
        if (time == null || time.year() < 1 || time.year() > 9999) {
            throw new IllegalArgumentException("Departure year must be 1..9999");
        }
        try {
            LocalDateTime.of(time.year(), time.month(), time.day(), time.hour(), time.minute());
        } catch (DateTimeException ex) {
            throw new IllegalArgumentException("Invalid departure date/time", ex);
        }
    }

    static Flight seedFlight(Flight flight) {
        if (flight == null || flight.flightId() <= 0 || flight.availableSeats() < 0
                || flight.updateSequence() != 0) {
            throw new IllegalArgumentException("Invalid initial flight ID, seats or sequence");
        }
        departure(flight.departure());
        return new Flight(flight.flightId(), location(flight.source()), location(flight.destination()),
                flight.departure(), price(flight.airfare()), flight.availableSeats(), 0);
    }
}
