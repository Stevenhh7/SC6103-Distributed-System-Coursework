package flight;

import java.net.InetSocketAddress;
import java.util.HexFormat;
import java.util.List;

/** Test-only bridge: Python supplies its real encoder output; Java emits independent replies. */
public final class ProtocolVectorTool {
    public static void main(String[] args) throws Exception {
        BinaryProtocolCodec codec=new BinaryProtocolCodec();
        if(args.length>0){
            for(String arg:args){byte[] raw=HexFormat.of().parseHex(arg);Request q=codec.decodeRequest(raw,0,raw.length);
                System.out.println(HexFormat.of().formatHex(codec.encodeRequest(q)));}
            return;
        }
        ReplyBody[] bodies={new RouteResult(List.of(1001,1002)),new FlightDetails(new FlightTime(2026,10,17,14,30),120,10),
            new ReservationResult(1001,8),new MonitorResult(1001,59000),new FareResult(1001,120),new FareResult(1001,140)};
        for(int op=1;op<=6;op++)System.out.println(HexFormat.of().formatHex(codec.encodeReply(ProtocolSelfTest.header(op,op,0),new Response(Status.OK,bodies[op-1]))));
        for(Status status:Status.values())if(status!=Status.OK)System.out.println(HexFormat.of().formatHex(codec.encodeReply(ProtocolSelfTest.header(2,100+status.code(),4),new Response(status,new ErrorBody("错误 "+status.name())))));
        System.out.println(HexFormat.of().formatHex(codec.encodeCallback(new CallbackEvent(new RegistrationKey(ProtocolSelfTest.SESSION,4,1001),new InetSocketAddress("127.0.0.1",1234),8,1),Semantics.AMO)));
    }
}
