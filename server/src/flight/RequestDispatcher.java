package flight;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Optional;
import java.util.function.LongSupplier;

/** A-03..06: serialized validate -> deduplicate -> execute -> save -> reply -> callback pipeline. */
public final class RequestDispatcher {
    private final ServerConfig config;
    private final ProtocolCodec codec;
    private final RequestHistory history;
    private final FlightService flights;
    private final MonitorService monitors;
    private final LossSimulator loss;
    private final Sender sender;
    private final LongSupplier clock;

    @FunctionalInterface
    interface Sender { void send(byte[] bytes, InetSocketAddress peer) throws IOException; }

    public RequestDispatcher(ServerConfig config, ProtocolCodec codec, RequestHistory history,
                             FlightService flights, MonitorService monitors,
                             LossSimulator loss, UdpTransport transport) {
        this(config, codec, history, flights, monitors, loss, transport::send, System::nanoTime);
    }

    // Package-private seam for deterministic clock/send failures; public contracts unchanged.
    RequestDispatcher(ServerConfig config, ProtocolCodec codec, RequestHistory history,
                      FlightService flights, MonitorService monitors, LossSimulator loss,
                      Sender sender, LongSupplier clock) {
        this.config = config; this.codec = codec; this.history = history; this.flights = flights;
        this.monitors = monitors; this.loss = loss; this.sender = sender; this.clock = clock;
    }

    public void handle(ReceivedDatagram datagram) throws IOException {
        byte[] raw = datagram.data();
        InetSocketAddress peer = datagram.peer();
        final Header h;
        try { h = codec.decodeHeader(raw, 0, raw.length); }
        catch (ProtocolException ex) {
            if (ex.replyHeader() != null) reject(ex.replyHeader(), peer, ex.replyStatus(), ex.getMessage());
            else ServerLog.event("DROP_MALFORMED", "peer", peer, "bytes", raw.length, "reason", ex.getMessage());
            return;
        }
        if (h.messageType() != MessageType.REQUEST) {
            ServerLog.event("DROP_NON_REQUEST", "peer", peer, "messageType", h.messageType()); return;
        }
        log("REQUEST_RECEIVED", h, peer, "encodedHex", HexFormat.of().formatHex(raw));
        if (h.semantics() != config.semantics()) {
            reject(h, peer, Status.SEMANTICS_MISMATCH, "Server uses " + config.semantics()); return;
        }
        RequestKey key = new RequestKey(h.clientSessionId(), h.requestId());
        if (config.semantics() == Semantics.AMO) {
            Optional<HistoryEntry> found = history.find(key);
            if (found.isPresent()) {
                HistoryEntry old = found.get();
                if (!peer.equals(old.peer()) || !Arrays.equals(raw, old.originalRequest())) {
                    reject(h, peer, Status.REQUEST_ID_REUSE, "Request identity reused with different bytes or endpoint"); return;
                }
                log("CACHE_HIT", h, peer, "cacheHit", true, "businessExecuted", false, "status", old.originalResponse().status().code());
                byte[] bytes = old.monitorRegistration().isPresent()
                        ? encodeReply(h, refreshed(old.originalResponse(), old.monitorRegistration())) : old.encodedReply();
                sendReply(h, peer, key, bytes, true);
                return; // No business execution, no newly generated callback on replay.
            }
        }
        final Request request;
        try { request = codec.decodeRequest(raw, 0, raw.length); }
        catch (ProtocolException ex) { reject(h, peer, ex.replyStatus(), ex.getMessage()); return; }
        ServiceResult result = flights.handle(request, new RequestContext(peer, clock.getAsLong()));
        log("BUSINESS_EXECUTED", h, peer, "cacheHit", false, "businessExecuted", true,
                "status", result.response().status().code(), "request", request.body(), "response", result.response().body());
        byte[] bytes = encodeReply(h, refreshed(result.response(), result.monitorRegistration()));
        if (config.semantics() == Semantics.AMO) {
            history.saveNew(key, new HistoryEntry(peer, raw, result.response(), bytes, result.monitorRegistration()));
            log("HISTORY_SAVED", h, peer, "status", result.response().status().code());
        }
        // Refresh once more at the send boundary; original registration and deadline stay unchanged.
        if (result.monitorRegistration().isPresent()) bytes = encodeReply(h, refreshed(result.response(), result.monitorRegistration()));
        sendReply(h, peer, key, bytes, false);
        for (CallbackEvent event : result.callbacks()) {
            RegistrationKey registration = event.registration();
            if (!monitors.isActive(registration, clock.getAsLong())) {
                ServerLog.event("CALLBACK_EXPIRED", "sessionId", registration.clientSessionId(),
                        "requestId", registration.registrationRequestId(), "flightId", registration.flightId());
                continue;
            }
            try {
                byte[] callback = codec.encodeCallback(event, config.semantics());
                // Encoding must not permit an expired event to cross the send boundary.
                if (!monitors.isActive(registration, clock.getAsLong())) continue;
                sender.send(callback, event.recipient());
                callbackLog("CALLBACK_SENT", event, h, callback, null);
            } catch (IOException | ProtocolException ex) {
                callbackLog("CALLBACK_SEND_FAILED", event, h, null, ex.getMessage());
            }
        }
    }

    private Response refreshed(Response response, Optional<RegistrationKey> registration) {
        if (registration.isEmpty()) return response;
        MonitorResult original = (MonitorResult)response.body();
        return new Response(response.status(), new MonitorResult(original.flightId(),
                monitors.remainingMillis(registration.get(), clock.getAsLong())));
    }

    private byte[] encodeReply(Header h, Response response) throws IOException {
        try { return codec.encodeReply(h, response); }
        catch (ProtocolException ex) { throw new IOException("Invalid internal business reply: " + ex.getMessage(), ex); }
    }

    private void reject(Header h, InetSocketAddress peer, Status status, String reason) throws IOException {
        log("REQUEST_REJECTED", h, peer, "status", status.code(), "businessExecuted", false, "reason", reason);
        // Pre-business rejection never consumes the deterministic business-reply loss selector.
        byte[] bytes = encodeReply(h, new Response(status, new ErrorBody(reason)));
        try { sender.send(bytes, peer); log("REPLY_SENT", h, peer, "cacheHit", false, "encodedHex", HexFormat.of().formatHex(bytes)); }
        catch (IOException ex) { log("REPLY_SEND_FAILED", h, peer, "reason", ex.getMessage()); }
    }

    private void sendReply(Header h, InetSocketAddress peer, RequestKey key, byte[] bytes, boolean cached) {
        if (loss.shouldDropReply(key)) {
            log("DROP_REPLY", h, peer, "cacheHit", cached, "encodedHex", HexFormat.of().formatHex(bytes)); return;
        }
        try { sender.send(bytes, peer); log("REPLY_SENT", h, peer, "cacheHit", cached, "encodedHex", HexFormat.of().formatHex(bytes)); }
        catch (IOException ex) { log("REPLY_SEND_FAILED", h, peer, "cacheHit", cached, "reason", ex.getMessage()); }
    }

    private void log(String event, Header h, InetSocketAddress peer, Object... extra) {
        Object[] all = new Object[10 + extra.length];
        Object[] base = {"mode", config.semantics(), "sessionId", h.clientSessionId(), "requestId", h.requestId(),
                         "operation", h.operation(), "peer", peer};
        System.arraycopy(base, 0, all, 0, base.length); System.arraycopy(extra, 0, all, base.length, extra.length);
        ServerLog.event(event, all);
    }

    private void callbackLog(String event, CallbackEvent c, Header trigger, byte[] bytes, String reason) {
        ServerLog.event(event, "mode", config.semantics(), "sessionId", c.registration().clientSessionId(),
                "requestId", c.registration().registrationRequestId(), "operation", 4, "peer", c.recipient(),
                "flightId", c.registration().flightId(), "availableSeats", c.availableSeats(), "sequence", c.updateSequence(),
                "triggerSessionId", trigger.clientSessionId(), "triggerRequestId", trigger.requestId(),
                "encodedHex", bytes == null ? null : HexFormat.of().formatHex(bytes), "reason", reason);
    }
}
