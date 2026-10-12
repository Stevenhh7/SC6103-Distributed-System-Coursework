package flight;

import java.io.IOException;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static flight.ProtocolSelfTest.*;

/** Deterministic dispatcher tests include send failures, unlike a UDP send's best-effort return. */
public final class SemanticsSelfTest {
    static final InetSocketAddress PEER=new InetSocketAddress("127.0.0.1",41001);
    static final InetSocketAddress OTHER=new InetSocketAddress("127.0.0.1",41002);
    record Sent(byte[] raw, InetSocketAddress peer) {}
    static final class Harness {
        final InMemoryMonitorService monitors=new InMemoryMonitorService();
        final DefaultFlightService service=new DefaultFlightService(monitors);
        final InMemoryRequestHistory history=new InMemoryRequestHistory();
        final List<Sent> sent=new ArrayList<>();
        final RequestDispatcher dispatcher;
        long now; int executions; boolean failReplies, failFirstCallback; int callbackAttempts;
        Harness(Semantics mode, Optional<RequestKey> target) {
            service.loadSeedData();
            ServerConfig c=new ServerConfig("127.0.0.1",6789,mode,target,false);
            dispatcher=new RequestDispatcher(c,CODEC,history,(r,context)->{executions++;return service.handle(r,context);},
                monitors,new LossSimulator(target),(bytes,peer)->{
                    if(bytes[1]==2 && failReplies)throw new IOException("injected reply send failure");
                    if(bytes[1]==3 && ++callbackAttempts==1 && failFirstCallback)throw new IOException("injected recipient failure");
                    sent.add(new Sent(bytes.clone(),peer));
                },()->now);
        }
        byte[] packet(int op,int id,RequestBody body,Semantics mode) throws Exception {
            int length=op==2?4:8;
            return CODEC.encodeRequest(new Request(new Header(1,MessageType.REQUEST,op,SESSION,id,Status.OK,mode,length),body));
        }
        void send(byte[] bytes) throws Exception { dispatcher.handle(new ReceivedDatagram(bytes,PEER)); }
        Reply last() throws Exception {byte[] b=sent.get(sent.size()-1).raw();return CODEC.decodeReply(b,0,b.length);}
        int seats(){return ((FlightDetails)service.handle(request(2,999,4,new FlightQuery(1001)),new RequestContext(PEER,now)).response().body()).availableSeats();}
        RegistrationKey monitor(UUID session,int id,int seconds){return monitors.register(new RequestKey(session,id),OTHER,1001,seconds,now);}
    }
    public static void main(String[] args) throws Exception {
        test("history_no_overwrite_and_defensive_bytes",()->{
            InMemoryRequestHistory h=new InMemoryRequestHistory();RequestKey key=new RequestKey(SESSION,1);byte[] a={1},b={2};
            HistoryEntry e=new HistoryEntry(PEER,a,new Response(Status.OK,new ReservationResult(1001,9)),b,Optional.empty());h.saveNew(key,e);
            a[0]=7;b[0]=8;byte[] returned=e.encodedReply();returned[0]=9;equal((byte)2,h.find(key).orElseThrow().encodedReply()[0]);
            try{h.saveNew(key,e);throw new AssertionError();}catch(IllegalArgumentException expected){}
            check(h.find(new RequestKey(SESSION,2)).isEmpty());
        });
        test("amo_executes_once_replays_exact_bytes",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());byte[] b=h.packet(3,1,new Reservation(1001,1),Semantics.AMO);
            h.send(b);h.send(b);equal(1,h.executions);equal(9,h.seats());bytes(h.sent.get(0).raw(),h.sent.get(1).raw());
        });
        test("alo_executes_each_delivery_no_history",()->{
            Harness h=new Harness(Semantics.ALO,Optional.empty());byte[] b=h.packet(3,1,new Reservation(1001,1),Semantics.ALO);
            h.send(b);h.send(b);equal(2,h.executions);equal(8,h.seats());check(h.history.find(new RequestKey(SESSION,1)).isEmpty());
        });
        test("business_errors_cached_even_after_state_changes",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());byte[] b=h.packet(3,1,new Reservation(1001,11),Semantics.AMO);
            h.send(b);h.service.loadSeedData();h.send(b);equal(1,h.executions);equal(Status.INSUFFICIENT_SEATS,h.last().response().status());
        });
        test("same_key_different_bytes_or_peer_rejected_preserves_history",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());byte[] b=h.packet(3,1,new Reservation(1001,1),Semantics.AMO);h.send(b);
            h.send(h.packet(3,1,new Reservation(1001,2),Semantics.AMO));equal(Status.REQUEST_ID_REUSE,h.last().response().status());
            h.dispatcher.handle(new ReceivedDatagram(b,OTHER));equal(Status.REQUEST_ID_REUSE,h.last().response().status());
            h.send(b);equal(1,h.executions);equal(9,h.seats());
        });
        test("sessions_isolated_same_request_id",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());byte[] b=h.packet(3,1,new Reservation(1001,1),Semantics.AMO);h.send(b);
            b[4]^=1;h.send(b);equal(2,h.executions);equal(8,h.seats());
        });
        test("mode_checked_before_history_and_echoed",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());byte[] b=h.packet(3,1,new Reservation(1001,1),Semantics.AMO);h.send(b);b[26]=1;h.send(b);
            equal(Status.SEMANTICS_MISMATCH,h.last().response().status());equal(Semantics.ALO,h.last().header().semantics());equal(1,h.executions);
        });
        test("malformed_not_cached_then_correct_request_succeeds",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());byte[] b=h.packet(3,1,new Reservation(1001,1),Semantics.AMO);byte[] bad=b.clone();bad[27]=1;h.send(bad);
            equal(Status.MALFORMED_MESSAGE,h.last().response().status());check(h.history.find(new RequestKey(SESSION,1)).isEmpty());h.send(b);equal(1,h.executions);
        });
        test("untrusted_identity_silently_dropped",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());h.send(new byte[10]);byte[] b=h.packet(2,1,new FlightQuery(1001),Semantics.AMO);b[0]=2;h.send(b);
            equal(0,h.executions);equal(0,h.sent.size());
        });
        test("drop_first_reply_after_history_only_once",()->{
            Harness h=new Harness(Semantics.AMO,Optional.of(new RequestKey(SESSION,1)));byte[] b=h.packet(3,1,new Reservation(1001,1),Semantics.AMO);
            h.send(b);equal(0,h.sent.size());check(h.history.find(new RequestKey(SESSION,1)).isPresent());h.send(b);equal(1,h.sent.size());equal(1,h.executions);
        });
        test("loss_target_does_not_affect_other_request",()->{
            LossSimulator loss=new LossSimulator(Optional.of(new RequestKey(SESSION,2)));
            check(!loss.shouldDropReply(new RequestKey(SESSION,1)));check(loss.shouldDropReply(new RequestKey(SESSION,2)));check(!loss.shouldDropReply(new RequestKey(SESSION,2)));
        });
        test("reply_drop_does_not_drop_callback_or_replay_it",()->{
            Harness h=new Harness(Semantics.AMO,Optional.of(new RequestKey(SESSION,1)));h.monitor(UUID.randomUUID(),7,10);
            byte[] b=h.packet(3,1,new Reservation(1001,1),Semantics.AMO);h.send(b);equal(1,h.callbackAttempts);equal((byte)3,h.sent.get(0).raw()[1]);h.send(b);equal(1,h.callbackAttempts);
        });
        test("reply_send_failure_still_attempts_callbacks",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());h.monitor(UUID.randomUUID(),7,10);h.failReplies=true;
            h.send(h.packet(3,1,new Reservation(1001,1),Semantics.AMO));equal(1,h.callbackAttempts);equal(9,h.seats());check(h.history.find(new RequestKey(SESSION,1)).isPresent());
        });
        test("one_recipient_failure_does_not_block_second",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());h.monitor(UUID.randomUUID(),7,10);h.monitor(UUID.randomUUID(),8,10);h.failFirstCallback=true;
            h.send(h.packet(3,1,new Reservation(1001,1),Semantics.AMO));equal(2,h.callbackAttempts);equal(2,h.sent.size());
        });
        test("expired_callback_filtered_at_send_boundary",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());RegistrationKey key=h.monitor(UUID.randomUUID(),7,1);
            FlightService f=(r,c)->{ServiceResult result=h.service.handle(r,c);h.now=1_000_000_000L;return result;};
            RequestDispatcher d=new RequestDispatcher(new ServerConfig("127.0.0.1",6789,Semantics.AMO,Optional.empty(),false),CODEC,h.history,f,h.monitors,
                new LossSimulator(Optional.empty()),(b,p)->h.sent.add(new Sent(b,p)),()->h.now);
            d.handle(new ReceivedDatagram(h.packet(3,1,new Reservation(1001,1),Semantics.AMO),PEER));equal(1,h.sent.size());check(!h.monitors.isActive(key,h.now));
        });
        test("monitor_replay_reduces_remaining_and_expired_zero",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());byte[] b=h.packet(4,1,new MonitorRegistration(1001,10),Semantics.AMO);
            h.send(b);equal(10000,((MonitorResult)h.last().response().body()).remainingMillis());h.now=2_000_000_000L;h.send(b);
            equal(8000,((MonitorResult)h.last().response().body()).remainingMillis());h.now=10_000_000_000L;h.send(b);equal(0,((MonitorResult)h.last().response().body()).remainingMillis());equal(1,h.executions);
        });
        test("replaced_monitor_replay_does_not_use_new_deadline",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());byte[] old=h.packet(4,1,new MonitorRegistration(1001,10),Semantics.AMO);h.send(old);
            h.send(h.packet(4,2,new MonitorRegistration(1001,20),Semantics.AMO));h.send(old);equal(0,((MonitorResult)h.last().response().body()).remainingMillis());equal(2,h.executions);
        });
        test("first_monitor_reply_refreshed_after_business",()->{
            Harness h=new Harness(Semantics.AMO,Optional.empty());
            FlightService f=(r,c)->{ServiceResult result=h.service.handle(r,c);h.now+=2_000_000_000L;return result;};
            RequestDispatcher d=new RequestDispatcher(new ServerConfig("127.0.0.1",6789,Semantics.AMO,Optional.empty(),false),CODEC,h.history,f,h.monitors,
                new LossSimulator(Optional.empty()),(b,p)->h.sent.add(new Sent(b,p)),()->h.now);
            d.handle(new ReceivedDatagram(h.packet(4,1,new MonitorRegistration(1001,10),Semantics.AMO),PEER));equal(8000,((MonitorResult)h.last().response().body()).remainingMillis());
        });
        test("alo_monitor_reexecutes_and_renews",()->{
            Harness h=new Harness(Semantics.ALO,Optional.empty());byte[] b=h.packet(4,1,new MonitorRegistration(1001,10),Semantics.ALO);h.send(b);h.now=2_000_000_000L;h.send(b);
            equal(10000,((MonitorResult)h.last().response().body()).remainingMillis());equal(2,h.executions);
        });
        test("real_transport_full_oversize_source_timeout_and_close",()->{
            int port;try(DatagramSocket s=new DatagramSocket(0)){port=s.getLocalPort();}
            try(UdpTransport t=new UdpTransport(new ServerConfig("127.0.0.1",port,Semantics.AMO,Optional.empty(),false));DatagramSocket sender=new DatagramSocket(0)){
                t.open();t.open();byte[] oversized=new byte[2048];sender.send(new java.net.DatagramPacket(oversized,oversized.length,PEER.getAddress(),port));
                ReceivedDatagram d=t.receive();equal(2048,d.data().length);equal(sender.getLocalPort(),d.peer().getPort());
                try{t.receive();throw new AssertionError();}catch(java.net.SocketTimeoutException expected){}
                t.close();t.close();
            }
            try(DatagramSocket rebound=new DatagramSocket(port)){check(rebound.isBound());}
        });
        test("server_idle_purges_and_close_unblocks_receive",()->{
            int port;try(DatagramSocket s=new DatagramSocket(0)){port=s.getLocalPort();}
            UdpServer server=new UdpServer(new ServerConfig("127.0.0.1",port,Semantics.AMO,Optional.empty(),false));
            java.lang.reflect.Field field=UdpServer.class.getDeclaredField("monitors");field.setAccessible(true);
            InMemoryMonitorService m=(InMemoryMonitorService)field.get(server);m.register(new RequestKey(SESSION,1),PEER,1001,1,System.nanoTime());
            java.util.concurrent.atomic.AtomicReference<Throwable> failure=new java.util.concurrent.atomic.AtomicReference<>();
            Thread thread=new Thread(()->{try{server.run();}catch(Throwable ex){failure.set(ex);}});thread.start();
            try{Thread.sleep(1350);}finally{server.close();thread.join(1500);}
            check(!thread.isAlive());check(failure.get()==null);
            java.lang.reflect.Field subs=InMemoryMonitorService.class.getDeclaredField("subscriptions");subs.setAccessible(true);equal(0,((java.util.Map<?,?>)subs.get(m)).size());
        });
        System.out.println("SemanticsSelfTest: "+passed+" passed");
    }
}
