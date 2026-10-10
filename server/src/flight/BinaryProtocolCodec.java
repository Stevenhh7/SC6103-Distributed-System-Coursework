package flight;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.time.DateTimeException;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;

/** A-02: explicit big-endian byte[] protocol. No streams/object serialization/RPC.
 * NIO buffers are used only at the strict UTF-8 charset boundary, not for numeric encoding.
 */
public final class BinaryProtocolCodec implements ProtocolCodec {
    private static void require(boolean condition, String reason) throws ProtocolException {
        if (!condition) throw new ProtocolException(reason);
    }

    @Override
    public Header decodeHeader(byte[] data, int offset, int length) throws ProtocolException {
        Reader r = new Reader(data, offset, length);
        require(length >= 32, "Truncated header");
        int version = r.u8(), kindCode = r.u8(), op = r.u16();
        UUID session = new UUID(r.i64(), r.i64());
        int id = r.i32(), statusCode = r.u16(), modeCode = r.u8(), reserved = r.u8();
        int bodyLength = r.i32();
        require(version == 1 && kindCode >= 1 && kindCode <= 3
                && (session.getMostSignificantBits() != 0L || session.getLeastSignificantBits() != 0L),
                "Unsupported version/type or zero session");
        require(id > 0 && (modeCode == 1 || modeCode == 2), "Invalid request identity or mode");
        MessageType kind = MessageType.fromCode(kindCode);
        Semantics mode = Semantics.fromCode(modeCode);
        // Only a trustworthy REQUEST identity can receive a correlated protocol error.
        Header identity = kind == MessageType.REQUEST
                ? new Header(version, kind, op, session, id, Status.OK, mode, 0) : null;
        try {
            if (length > 1024) throw new ProtocolException("Datagram exceeds 1024 bytes", identity, Status.LIMIT_EXCEEDED);
            require(reserved == 0, "Reserved byte must be zero");
            require(bodyLength >= 0 && bodyLength == length - 32, "Invalid bodyLength");
            require(statusCode <= 9 && (kind == MessageType.REPLY || statusCode == 0), "Invalid status");
            if (kind == MessageType.CALLBACK) require(op == 4 && bodyLength == 12, "Invalid callback header");
            return new Header(version, kind, op, session, id, Status.fromCode(statusCode), mode, bodyLength);
        } catch (ProtocolException ex) {
            if (ex.replyStatus() == Status.LIMIT_EXCEEDED) throw ex;
            throw new ProtocolException(ex.getMessage(), identity, Status.MALFORMED_MESSAGE);
        }
    }

    @Override
    public Request decodeRequest(byte[] data, int offset, int length) throws ProtocolException {
        Header h = decodeHeader(data, offset, length);
        require(h.messageType() == MessageType.REQUEST, "Expected REQUEST");
        try {
            Reader r = new Reader(data, offset + 32, length - 32);
            RequestBody body = switch (h.operation()) {
                case 1 -> new RouteQuery(r.string(128, false), r.string(128, false));
                case 2 -> new FlightQuery(r.i32());
                case 3 -> new Reservation(r.i32(), r.i32());
                case 4 -> new MonitorRegistration(r.i32(), r.i32());
                case 5 -> new SetAirfare(r.i32(), r.f32());
                case 6 -> new IncreaseAirfare(r.i32(), r.f32());
                default -> throw new ProtocolException("Unsupported operation", h, Status.UNSUPPORTED_OPERATION);
            };
            r.finish();
            // Representable but invalid business values deliberately reach B (and AMO history).
            return new Request(h, body);
        } catch (ProtocolException ex) {
            if (ex.replyStatus() == Status.UNSUPPORTED_OPERATION) throw ex;
            throw new ProtocolException(ex.getMessage(), h, Status.MALFORMED_MESSAGE);
        }
    }

    @Override
    public byte[] encodeRequest(Request request) throws ProtocolException {
        require(request != null && request.header() != null && request.body() != null, "Missing request");
        Header h = request.header();
        require(h.messageType() == MessageType.REQUEST && h.status() == Status.OK, "Invalid request header");
        Writer w = new Writer();
        RequestBody b = request.body();
        switch (h.operation()) {
            case 1 -> { require(b instanceof RouteQuery, "Wrong request body"); RouteQuery q = (RouteQuery)b;
                w.string(q.source(), 128, false); w.string(q.destination(), 128, false); }
            case 2 -> { require(b instanceof FlightQuery, "Wrong request body"); w.i32(((FlightQuery)b).flightId()); }
            case 3 -> { require(b instanceof Reservation, "Wrong request body"); Reservation q = (Reservation)b;
                w.i32(q.flightId()); w.i32(q.quantity()); }
            case 4 -> { require(b instanceof MonitorRegistration, "Wrong request body"); MonitorRegistration q = (MonitorRegistration)b;
                w.i32(q.flightId()); w.i32(q.durationSeconds()); }
            case 5 -> { require(b instanceof SetAirfare, "Wrong request body"); SetAirfare q = (SetAirfare)b;
                w.i32(q.flightId()); w.f32(q.newPrice()); }
            case 6 -> { require(b instanceof IncreaseAirfare, "Wrong request body"); IncreaseAirfare q = (IncreaseAirfare)b;
                w.i32(q.flightId()); w.f32(q.delta()); }
            default -> throw new ProtocolException("Unsupported operation");
        }
        byte[] body = w.bytes();
        require(h.bodyLength() == body.length, "Request bodyLength mismatch");
        return message(h, MessageType.REQUEST, Status.OK, body);
    }

    @Override
    public byte[] encodeReply(Header requestHeader, Response response) throws ProtocolException {
        require(requestHeader != null && requestHeader.messageType() == MessageType.REQUEST
                && response != null && response.status() != null && response.body() != null, "Invalid reply input");
        Writer w = new Writer();
        ReplyBody b = response.body();
        if (response.status() != Status.OK) {
            require(b instanceof ErrorBody, "Error requires ErrorBody");
            w.string(((ErrorBody)b).message(), 256, true);
        } else {
            switch (requestHeader.operation()) {
                case 1 -> { require(b instanceof RouteResult, "Wrong reply body");
                    List<Integer> ids = ((RouteResult)b).flightIds();
                    require(ids.size() >= 1 && ids.size() <= 100, "Invalid route count");
                    w.i32(ids.size()); int previous = 0;
                    for (Integer id : ids) { require(id != null && id > previous, "Route IDs must ascend"); w.i32(id); previous = id; }
                }
                case 2 -> { require(b instanceof FlightDetails, "Wrong reply body"); FlightDetails d = (FlightDetails)b;
                    validateTime(d.departure()); FlightTime t = d.departure();
                    w.i32(t.year()); w.i32(t.month()); w.i32(t.day()); w.i32(t.hour()); w.i32(t.minute());
                    validFare(d.airfare()); w.f32(d.airfare()); nonnegative(d.availableSeats()); w.i32(d.availableSeats()); }
                case 3 -> { require(b instanceof ReservationResult, "Wrong reply body"); ReservationResult d = (ReservationResult)b;
                    positive(d.flightId()); nonnegative(d.availableSeats()); w.i32(d.flightId()); w.i32(d.availableSeats()); }
                case 4 -> { require(b instanceof MonitorResult, "Wrong reply body"); MonitorResult d = (MonitorResult)b;
                    positive(d.flightId()); require(d.remainingMillis() >= 0 && d.remainingMillis() <= 3600000, "Invalid remaining time");
                    w.i32(d.flightId()); w.i32(d.remainingMillis()); }
                case 5, 6 -> { require(b instanceof FareResult, "Wrong reply body"); FareResult d = (FareResult)b;
                    positive(d.flightId()); validFare(d.airfare()); w.i32(d.flightId()); w.f32(d.airfare()); }
                default -> throw new ProtocolException("Unknown successful operation");
            }
        }
        return message(requestHeader, MessageType.REPLY, response.status(), w.bytes());
    }

    @Override
    public Reply decodeReply(byte[] data, int offset, int length) throws ProtocolException {
        Header h = decodeHeader(data, offset, length);
        require(h.messageType() == MessageType.REPLY, "Expected REPLY");
        Reader r = new Reader(data, offset + 32, length - 32);
        ReplyBody b;
        if (h.status() != Status.OK) b = new ErrorBody(r.string(256, true));
        else {
            b = switch (h.operation()) {
                case 1 -> { int count = r.i32(); require(count >= 1 && count <= 100, "Invalid route count");
                    List<Integer> ids = new ArrayList<>(); int previous = 0;
                    for (int i = 0; i < count; i++) { int id = r.i32(); require(id > previous, "Route IDs must ascend"); ids.add(id); previous = id; }
                    yield new RouteResult(ids); }
                case 2 -> { FlightTime t = new FlightTime(r.i32(), r.i32(), r.i32(), r.i32(), r.i32()); validateTime(t);
                    yield new FlightDetails(t, r.fare(), r.nonnegative()); }
                case 3 -> new ReservationResult(r.positive(), r.nonnegative());
                case 4 -> { int id = r.positive(), remaining = r.nonnegative(); require(remaining <= 3600000, "Invalid remaining time");
                    yield new MonitorResult(id, remaining); }
                case 5, 6 -> new FareResult(r.positive(), r.fare());
                default -> throw new ProtocolException("Unknown successful operation");
            };
        }
        r.finish();
        return new Reply(h, new Response(h.status(), b));
    }

    @Override
    public byte[] encodeCallback(CallbackEvent event, Semantics mode) throws ProtocolException {
        require(event != null && event.registration() != null, "Missing callback identity");
        RegistrationKey key = event.registration();
        positive(key.flightId()); nonnegative(event.availableSeats()); positive(event.updateSequence());
        Writer w = new Writer(); w.i32(key.flightId()); w.i32(event.availableSeats()); w.i32(event.updateSequence());
        Header h = new Header(1, MessageType.CALLBACK, 4, key.clientSessionId(), key.registrationRequestId(), Status.OK, mode, 12);
        return message(h, MessageType.CALLBACK, Status.OK, w.bytes());
    }

    @Override
    public CallbackMessage decodeCallback(byte[] data, int offset, int length) throws ProtocolException {
        Header h = decodeHeader(data, offset, length);
        require(h.messageType() == MessageType.CALLBACK, "Expected CALLBACK");
        Reader r = new Reader(data, offset + 32, length - 32);
        CallbackMessage result = new CallbackMessage(h, r.positive(), r.nonnegative(), r.positive());
        r.finish(); return result;
    }

    private static byte[] message(Header h, MessageType kind, Status status, byte[] body) throws ProtocolException {
        require(h != null && h.version() == 1 && h.clientSessionId() != null
                && !h.clientSessionId().equals(new UUID(0, 0)) && h.requestId() > 0 && h.semantics() != null,
                "Invalid outgoing identity");
        require(h.operation() >= 0 && h.operation() <= 65535 && body.length <= 992, "Outgoing message limit");
        Writer w = new Writer();
        w.u8(1); w.u8(kind.code()); w.u16(h.operation());
        w.i64(h.clientSessionId().getMostSignificantBits()); w.i64(h.clientSessionId().getLeastSignificantBits());
        w.i32(h.requestId()); w.u16(status.code()); w.u8(h.semantics().code()); w.u8(0); w.i32(body.length);
        w.raw(body); return w.bytes();
    }

    private static void positive(int n) throws ProtocolException { require(n > 0, "Expected positive integer"); }
    private static void nonnegative(int n) throws ProtocolException { require(n >= 0, "Expected nonnegative integer"); }
    private static void validFare(float n) throws ProtocolException {
        require(Float.isFinite(n) && n >= 0 && Float.floatToRawIntBits(n) != 0x80000000, "Invalid successful airfare");
    }
    private static void validateTime(FlightTime t) throws ProtocolException {
        require(t != null && t.year() >= 1 && t.year() <= 9999, "Invalid departure year");
        try { LocalDateTime.of(t.year(), t.month(), t.day(), t.hour(), t.minute()); }
        catch (DateTimeException ex) { throw new ProtocolException("Invalid departure time"); }
    }

    private static final class Reader {
        final byte[] data; final int end; int p;
        Reader(byte[] data, int offset, int length) throws ProtocolException {
            require(data != null && offset >= 0 && length >= 0 && offset <= data.length && length <= data.length - offset,
                    "Invalid byte range");
            this.data = data; this.p = offset; this.end = offset + length;
        }
        void need(int n) throws ProtocolException { require(n >= 0 && n <= end - p, "Truncated field"); }
        int u8() throws ProtocolException { need(1); return data[p++] & 255; }
        int u16() throws ProtocolException { return (u8() << 8) | u8(); }
        int i32() throws ProtocolException { return (u8() << 24) | (u8() << 16) | (u8() << 8) | u8(); }
        long i64() throws ProtocolException { return ((long)i32() << 32) | (i32() & 0xffffffffL); }
        float f32() throws ProtocolException { return Float.intBitsToFloat(i32()); }
        int positive() throws ProtocolException { int v = i32(); BinaryProtocolCodec.positive(v); return v; }
        int nonnegative() throws ProtocolException { int v = i32(); BinaryProtocolCodec.nonnegative(v); return v; }
        float fare() throws ProtocolException { float v = f32(); validFare(v); return v; }
        String string(int max, boolean nonempty) throws ProtocolException {
            int n = i32(); require(n >= (nonempty ? 1 : 0) && n <= max, "String length outside limit"); need(n);
            try {
                String result = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(data, p, n)).toString();
                p += n; return result;
            } catch (CharacterCodingException ex) { throw new ProtocolException("Invalid UTF-8"); }
        }
        void finish() throws ProtocolException { require(p == end, "Unexpected trailing bytes"); }
    }

    private static final class Writer {
        final byte[] data = new byte[1024]; int p;
        void u8(int n) throws ProtocolException { require(p < data.length, "Message exceeds limit"); data[p++] = (byte)n; }
        void u16(int n) throws ProtocolException { u8(n >>> 8); u8(n); }
        void i32(int n) throws ProtocolException { u8(n >>> 24); u8(n >>> 16); u8(n >>> 8); u8(n); }
        void i64(long n) throws ProtocolException { i32((int)(n >>> 32)); i32((int)n); }
        void f32(float n) throws ProtocolException { i32(Float.floatToIntBits(n)); }
        void raw(byte[] b) throws ProtocolException { require(b.length <= data.length - p, "Message exceeds limit");
            System.arraycopy(b, 0, data, p, b.length); p += b.length; }
        void string(String s, int max, boolean nonempty) throws ProtocolException {
            require(s != null, "Null string");
            try {
                ByteBuffer encoded = StandardCharsets.UTF_8.newEncoder().onMalformedInput(CodingErrorAction.REPORT)
                        .onUnmappableCharacter(CodingErrorAction.REPORT).encode(CharBuffer.wrap(s));
                int n = encoded.remaining(); require(n >= (nonempty ? 1 : 0) && n <= max, "String length outside limit");
                byte[] raw = new byte[n]; encoded.get(raw); i32(n); raw(raw);
            } catch (CharacterCodingException ex) { throw new ProtocolException("Invalid Unicode string"); }
        }
        byte[] bytes() { return Arrays.copyOf(data, p); }
    }
}
