package flight;

import java.net.InetSocketAddress;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

/** Independent normative bytes and malformed boundaries; no external test framework. */
public final class ProtocolSelfTest {
    static final BinaryProtocolCodec CODEC = new BinaryProtocolCodec();
    static final UUID SESSION = UUID.fromString("00112233-4455-4677-8899-aabbccddeeff");
    static final String PREFIX = "00112233445546778899aabbccddeeff";
    static int passed;
    interface Test { void run() throws Exception; }
    static void test(String name, Test task) throws Exception { task.run(); passed++; System.out.println("PASS " + name); }
    static void check(boolean b) { if (!b) throw new AssertionError(); }
    static void equal(Object a, Object b) { if (!java.util.Objects.equals(a,b)) throw new AssertionError(a + " != " + b); }
    static void bytes(byte[] a, byte[] b) { check(Arrays.equals(a,b)); }
    static byte[] hex(String h) { return HexFormat.of().parseHex(h); }
    static Header header(int op, int id, int length) { return new Header(1, MessageType.REQUEST, op, SESSION, id, Status.OK, Semantics.AMO, length); }
    static Request request(int op, int id, int length, RequestBody b) { return new Request(header(op,id,length), b); }
    static void rejects(Test task) throws Exception { try { task.run(); } catch (ProtocolException expected) { return; } throw new AssertionError("Expected protocol error"); }
    static byte[] route() { return hex("01010001"+PREFIX+"00000001000002000000000e0000000353494e0000000350454b"); }
    static byte[] detail() { return hex("01020002"+PREFIX+"00000002000002000000001c000007ea0000000a000000110000000e0000001e42f000000000000a"); }

    public static void main(String[] args) throws Exception {
        test("normative_route_request", () -> bytes(route(), CODEC.encodeRequest(request(1,1,14,new RouteQuery("SIN","PEK")))));
        test("normative_route_reply", () -> bytes(hex("01020001"+PREFIX+"00000001000002000000000c00000002000003e9000003ea"),
                CODEC.encodeReply(header(1,1,14),new Response(Status.OK,new RouteResult(List.of(1001,1002))))));
        test("normative_detail_reply", () -> {
            Response d = new Response(Status.OK,new FlightDetails(new FlightTime(2026,10,17,14,30),120,10));
            bytes(detail(), CODEC.encodeReply(header(2,2,4),d)); equal(d,CODEC.decodeReply(detail(),0,60).response());
        });
        test("normative_error_reply", () -> bytes(hex("01020002"+PREFIX+"00000003000202000000001400000010466c69676874206e6f7420666f756e64"),
                CODEC.encodeReply(header(2,3,4),new Response(Status.FLIGHT_NOT_FOUND,new ErrorBody("Flight not found")))));
        test("normative_monitor", () -> {
            bytes(hex("01010004"+PREFIX+"000000040000020000000008000003e90000003c"),CODEC.encodeRequest(request(4,4,8,new MonitorRegistration(1001,60))));
            bytes(hex("01020004"+PREFIX+"000000040000020000000008000003e90000e678"),CODEC.encodeReply(header(4,4,8),new Response(Status.OK,new MonitorResult(1001,59000))));
        });
        test("normative_callback", () -> {
            byte[] raw=hex("01030004"+PREFIX+"00000004000002000000000c000003e90000000800000001");
            bytes(raw,CODEC.encodeCallback(new CallbackEvent(new RegistrationKey(SESSION,4,1001),new InetSocketAddress("127.0.0.1",1234),8,1),Semantics.AMO));
            equal(1,CODEC.decodeCallback(raw,0,raw.length).updateSequence());
        });
        test("normative_mode_error_echo", () -> bytes(hex("01020002"+PREFIX+"0000000500070200000000130000000f536572766572207573657320414c4f"),
                CODEC.encodeReply(header(2,5,4),new Response(Status.SEMANTICS_MISMATCH,new ErrorBody("Server uses ALO")))));
        test("all_six_requests_and_signed_business_values", () -> {
            Request[] requests={request(1,1,20,new RouteQuery("北京","上海")),request(2,2,4,new FlightQuery(-1)),
                request(3,3,8,new Reservation(1001,Integer.MIN_VALUE)),request(4,4,8,new MonitorRegistration(1001,0)),
                request(5,5,8,new SetAirfare(1001,Float.NaN)),request(6,6,8,new IncreaseAirfare(1001,Float.POSITIVE_INFINITY))};
            for(Request q:requests){byte[] b=CODEC.encodeRequest(q);equal(q,CODEC.decodeRequest(b,0,b.length));}
        });
        test("strict_utf8_and_byte_length", () -> {
            byte[] b=CODEC.encodeRequest(request(1,1,14,new RouteQuery("北京",""))); equal(6,b[35]&255);
            b[36]=(byte)0xff; rejects(()->CODEC.decodeRequest(b,0,b.length));
            rejects(()->CODEC.encodeRequest(request(1,1,8,new RouteQuery("\uD800",""))));
            rejects(()->CODEC.encodeRequest(request(1,1,137,new RouteQuery("x".repeat(129),""))));
        });
        test("every_truncation_rejected", () -> {byte[] b=route();for(int n=0;n<b.length;n++){final int length=n;rejects(()->CODEC.decodeRequest(b,0,length));}});
        test("offset_length_not_entire_buffer", () -> {
            byte[] b=new byte[200];Arrays.fill(b,(byte)0x55);System.arraycopy(route(),0,b,7,route().length);
            equal(new RouteQuery("SIN","PEK"),CODEC.decodeRequest(b,7,route().length).body());
            rejects(()->CODEC.decodeRequest(b,-1,1));rejects(()->CODEC.decodeRequest(b,1,Integer.MAX_VALUE));rejects(()->CODEC.decodeRequest(null,0,32));
        });
        test("identity_errors_cannot_reply", () -> {
            for(int pos:new int[]{0,1,20,26}){byte[] b=route(); b[pos]=(byte)255;
                try{CODEC.decodeRequest(b,0,b.length);throw new AssertionError();}catch(ProtocolException e){check(e.replyHeader()==null);}}
            byte[] b=route();Arrays.fill(b,4,20,(byte)0);try{CODEC.decodeRequest(b,0,b.length);throw new AssertionError();}catch(ProtocolException e){check(e.replyHeader()==null);}
        });
        test("trusted_bad_header_correlates_error", () -> {
            for(int pos:new int[]{24,27,28,31}){byte[] b=route(); b[pos]=(byte)255;
                try{CODEC.decodeRequest(b,0,b.length);throw new AssertionError();}catch(ProtocolException e){check(e.replyHeader()!=null);equal(Status.MALFORMED_MESSAGE,e.replyStatus());}}
        });
        test("oversize_limit_before_body", () -> {
            byte[] b=Arrays.copyOf(route(),2048);try{CODEC.decodeRequest(b,0,b.length);throw new AssertionError();}
            catch(ProtocolException e){equal(Status.LIMIT_EXCEEDED,e.replyStatus());check(e.replyHeader()!=null);}
        });
        test("negative_string_length_and_body_trailing_bytes", () -> {
            byte[] b=route();Arrays.fill(b,32,36,(byte)255);rejects(()->CODEC.decodeRequest(b,0,b.length));
            byte[] tail=Arrays.copyOf(route(),47);tail[31]=15;rejects(()->CODEC.decodeRequest(tail,0,tail.length));
        });
        test("unknown_operation_and_error_decode", () -> {
            byte[] b=route();b[2]=(byte)255;b[3]=(byte)255;
            try{CODEC.decodeRequest(b,0,b.length);throw new AssertionError();}catch(ProtocolException e){equal(Status.UNSUPPORTED_OPERATION,e.replyStatus());}
            byte[] error=CODEC.encodeReply(header(65535,1,0),new Response(Status.UNSUPPORTED_OPERATION,new ErrorBody("Unknown")));
            equal(65535,CODEC.decodeReply(error,0,error.length).header().operation());
        });
        test("success_body_validation", () -> {
            for(float f:new float[]{-1,-0.0f,Float.NaN,Float.POSITIVE_INFINITY}) rejects(()->CODEC.encodeReply(header(5,1,8),new Response(Status.OK,new FareResult(1001,f))));
            rejects(()->CODEC.encodeReply(header(1,1,0),new Response(Status.OK,new RouteResult(List.of(2,1)))));
            rejects(()->CODEC.encodeReply(header(4,1,8),new Response(Status.OK,new MonitorResult(1001,3600001))));
            rejects(()->CODEC.encodeReply(header(2,1,4),new Response(Status.OK,new FlightDetails(new FlightTime(2026,2,29,0,0),1,1))));
            rejects(()->CODEC.encodeReply(header(2,1,4),new Response(Status.OK,new FareResult(1,1))));
        });
        test("invalid_reply_date_fare_counts_and_callback", () -> {
            byte[] badDate=detail();badDate[43]=32;rejects(()->CODEC.decodeReply(badDate,0,badDate.length));
            byte[] b=detail();b[52]=(byte)0x80;b[53]=0;final byte[] negative=b;rejects(()->CODEC.decodeReply(negative,0,negative.length));
            byte[] bad=hex("01030004"+PREFIX+"00000004000002000000000c000003e90000000800000000");rejects(()->CODEC.decodeCallback(bad,0,bad.length));
        });
        test("outgoing_identity_bodylength_and_error_text", () -> {
            rejects(()->CODEC.encodeRequest(request(2,1,8,new FlightQuery(1001))));
            rejects(()->CODEC.encodeRequest(request(3,1,8,new FlightQuery(1001))));
            rejects(()->CODEC.encodeReply(header(2,1,4),new Response(Status.FLIGHT_NOT_FOUND,new ErrorBody(""))));
            rejects(()->CODEC.encodeReply(header(2,1,4),new Response(Status.FLIGHT_NOT_FOUND,new ErrorBody("x".repeat(257)))));
        });
        System.out.println("ProtocolSelfTest: "+passed+" passed");
    }
}
