"""A real-network boundary suite: real Java process and C's production codec/Invoker.
Each test has isolated seed/history/registrations. Evidence is never labelled three-computer.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import unittest
from uuid import uuid4

from client.config import ClientConfig
from client.invoker import Invoker
from client.models import Header, Request, RouteQuery, FlightQuery, Reservation, MonitorRegistration, SetAirfare, IncreaseAirfare, Reply, CallbackMessage
from client.protocol import MessageType, Semantics, Status
from client.protocol_codec import encode_request, decode_message, request_body_length
from .run_suite import ROOT, CLASSES, OwnedProcesses, unused_port, compile_java


class Peer:
    def __init__(self, port, mode=Semantics.AMO, session=None):
        self.mode, self.session, self.id = mode, session or uuid4(), 0
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.sock.bind(('127.0.0.1',0))
        self.server=('127.0.0.1',port)
        self.callbacks=[]

    def packet(self, op, body):
        self.id+=1
        return encode_request(Request(Header(1,MessageType.REQUEST,op,self.session,self.id,Status.OK,self.mode,request_body_length(op,body)),body))

    def receive(self, timeout=1):
        self.sock.settimeout(timeout)
        raw, source=self.sock.recvfrom(65535)
        if source != self.server: raise AssertionError('Wrong server endpoint')
        return decode_message(raw),raw

    def exchange(self, raw):
        self.sock.sendto(raw,self.server)
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            msg,data=self.receive(max(.001,deadline-time.monotonic()))
            if isinstance(msg,CallbackMessage): self.callbacks.append(msg); continue
            return msg,data
        raise AssertionError('No reply')

    def call(self, op, body): return self.exchange(self.packet(op,body))[0]
    def close(self): self.sock.close()


class JavaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compile_java(tests=True)
        cls.folder=Path(os.environ.get('SC6103_EVIDENCE_DIR',str(ROOT/'evidence/a'/('boundaries-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))))).resolve()
        cls.folder.mkdir(parents=True,exist_ok=False)

    @contextmanager
    def server(self, mode='amo', drop=None):
        owner=OwnedProcesses(self.folder/self._testMethodName)
        port=unused_port()
        command=['java','-cp',str(CLASSES),'flight.ServerMain','--bind','127.0.0.1','--port',str(port),'--semantics',mode]
        if drop: command+=['--drop-first-reply',drop]
        try:
            process=owner.start('server',command);owner.ready(process,'server','SERVER_READY')
            self.peers=[]
            yield port
            self.assertIsNone(process.poll(),'Java crashed during request processing')
        finally:
            for peer in getattr(self,'peers',[]): peer.close()
            owner.close()

    def peer(self,port,mode=Semantics.AMO,session=None):
        p=Peer(port,mode,session);self.peers.append(p);return p

    def test_codec_cross_language_both_directions(self):
        data=json.loads((ROOT/'evidence/c/python-request-vectors.json').read_text())
        vectors=[v['hex'] for v in data['vectors']]
        # Generate from current Python encoder rather than trusting only stored outputs.
        from uuid import UUID
        session=UUID(data['sessionId'])
        bodies=[RouteQuery('SIN','PEK'),FlightQuery(1001),Reservation(1001,2),MonitorRegistration(1001,60),SetAirfare(1001,120),IncreaseAirfare(1001,20)]
        generated=[encode_request(Request(Header(1,MessageType.REQUEST,op,session,op,Status.OK,Semantics.AMO,request_body_length(op,b)),b)).hex() for op,b in enumerate(bodies,1)]
        self.assertEqual(vectors,generated)
        actual=subprocess.check_output(['java','-cp',str(CLASSES),'flight.ProtocolVectorTool',*generated],text=True,cwd=ROOT).splitlines()
        self.assertEqual(generated,actual)
        replies=subprocess.check_output(['java','-cp',str(CLASSES),'flight.ProtocolVectorTool'],text=True,cwd=ROOT).splitlines()
        decoded=[decode_message(bytes.fromhex(v)) for v in replies]
        self.assertEqual(16,len(decoded))
        for op,msg in enumerate(decoded[:6],1): self.assertEqual(op,msg.header.operation);self.assertEqual(Status.OK,msg.header.status)
        self.assertEqual([1001,1002],list(decoded[0].response.body.flightIds))
        self.assertEqual(120,decoded[1].response.body.airfare)
        self.assertEqual(8,decoded[2].response.body.availableSeats)
        self.assertEqual(59000,decoded[3].response.body.remainingMillis)
        self.assertEqual(140,decoded[5].response.body.airfare)
        self.assertEqual(list(range(1,10)),[int(m.header.status) for m in decoded[6:15]])
        self.assertIsInstance(decoded[-1],CallbackMessage)
        (self.folder/'cross-language-vectors.json').write_text(json.dumps(dict(python_requests=generated,java_requests=actual,java_replies_and_callback=replies),indent=2))

    def test_chinese_route_and_business_errors(self):
        with self.server() as port:
            p=self.peer(port)
            self.assertEqual((1004,1005),p.call(1,RouteQuery('北京','上海')).response.body.flightIds)
            for op,b,status in [(1,RouteQuery('Nowhere','Beijing'),1),(2,FlightQuery(9999),2),(3,Reservation(1003,1),3),
                    (3,Reservation(1001,0),4),(4,MonitorRegistration(1001,0),4),(5,SetAirfare(1001,-1),4),(6,IncreaseAirfare(1001,-1),4)]:
                self.assertEqual(status,p.call(op,b).header.status)
            d=p.call(2,FlightQuery(1001)).response.body
            self.assertEqual((10,100),(d.availableSeats,d.airfare))

    def test_amo_exact_replay_conflicts_and_session_isolation(self):
        with self.server() as port:
            p=self.peer(port);raw=p.packet(3,Reservation(1001,1));reply,encoded=p.exchange(raw)
            self.assertEqual(encoded,p.exchange(raw)[1])
            changed=bytearray(raw);changed[-1]=2
            self.assertEqual(8,p.exchange(changed)[0].header.status)
            q=self.peer(port,session=p.session)
            self.assertEqual(8,q.exchange(raw)[0].header.status)
            r=self.peer(port);self.assertEqual(8,r.call(3,Reservation(1001,1)).response.body.availableSeats)
            self.assertEqual(8,p.call(2,FlightQuery(1001)).response.body.availableSeats)

    def test_business_error_and_old_query_snapshots_replayed(self):
        with self.server() as port:
            p=self.peer(port);query=p.packet(2,FlightQuery(1001));original=p.exchange(query)[1]
            error=p.packet(3,Reservation(1001,11));failure=p.exchange(error)[1]
            p.call(3,Reservation(1001,1))
            self.assertEqual(original,p.exchange(query)[1]);self.assertEqual(failure,p.exchange(error)[1])
            self.assertEqual(9,p.call(2,FlightQuery(1001)).response.body.availableSeats)

    def test_mode_error_echo_and_server_survives(self):
        with self.server() as port:
            p=self.peer(port,Semantics.ALO);msg=p.call(3,Reservation(1001,1))
            self.assertEqual(7,msg.header.status);self.assertEqual(Semantics.ALO,msg.header.semantics)
            q=self.peer(port);self.assertEqual(10,q.call(2,FlightQuery(1001)).response.body.availableSeats)

    def test_malformed_packets_classification_and_no_side_effect(self):
        with self.server() as port:
            p=self.peer(port)
            for kind,status in [('reserved',5),('status',5),('length',5),('oversized',9),('unknown',6),('tail',5),('negative_string',5),('utf8',5)]:
                raw=bytearray(p.packet(1,RouteQuery('SIN','PEK')))
                if kind=='reserved':raw[27]=1
                if kind=='status':raw[24:26]=b'\xff\xff'
                if kind=='length':raw[28:32]=(-1).to_bytes(4,'big',signed=True)
                if kind=='oversized':raw.extend(bytes(2000));raw[28:32]=(len(raw)-32).to_bytes(4,'big')
                if kind=='unknown':raw[2:4]=b'\xff\xff'
                if kind=='tail':raw.append(0);raw[28:32]=(len(raw)-32).to_bytes(4,'big')
                if kind=='negative_string':raw[32:36]=b'\xff\xff\xff\xff'
                if kind=='utf8':raw[36]=255
                with self.subTest(kind=kind):self.assertEqual(status,p.exchange(raw)[0].header.status)
            raw=bytearray(p.packet(5,SetAirfare(1001,120)));raw[-4:]=bytes.fromhex('7fc00000')
            self.assertEqual(4,p.exchange(raw)[0].header.status)
            self.assertEqual(100,p.call(2,FlightQuery(1001)).response.body.airfare)

    def test_untrusted_or_nonrequest_packets_silently_discarded(self):
        with self.server() as port:
            p=self.peer(port)
            for kind in ('short','version','session','request_id','mode','type','reply'):
                raw=bytearray(p.packet(2,FlightQuery(1001)))
                if kind=='short':raw=raw[:20]
                if kind=='version':raw[0]=2
                if kind=='session':raw[4:20]=bytes(16)
                if kind=='request_id':raw[20:24]=bytes(4)
                if kind=='mode':raw[26]=3
                if kind=='type':raw[1]=9
                if kind=='reply':raw[1]=2
                p.sock.sendto(raw,p.server)
                with self.subTest(kind=kind),self.assertRaises(socket.timeout):p.receive(.08)
            self.assertEqual(10,p.call(2,FlightQuery(1001)).response.body.availableSeats)

    def test_dual_monitor_callback_identity_and_no_duplicate_amo_event(self):
        with self.server() as port:
            a,b,w=self.peer(port),self.peer(port),self.peer(port)
            a.call(4,MonitorRegistration(1001,2));b.call(4,MonitorRegistration(1001,2))
            raw=w.packet(3,Reservation(1001,1));w.exchange(raw)
            for p in (a,b):
                msg,_=p.receive();self.assertIsInstance(msg,CallbackMessage)
                self.assertEqual((p.session,1,1001,9,1),(msg.header.clientSessionId,msg.header.requestId,msg.flightId,msg.availableSeats,msg.updateSequence))
            w.exchange(raw)
            for p in (a,b):
                with self.assertRaises(socket.timeout):p.receive(.1)

    def test_flight_isolation_and_expiry_stops_callback(self):
        with self.server() as port:
            a,b,w=self.peer(port),self.peer(port),self.peer(port)
            a.call(4,MonitorRegistration(1001,1));b.call(4,MonitorRegistration(1002,3))
            w.call(3,Reservation(1001,1));self.assertEqual(9,a.receive()[0].availableSeats)
            with self.assertRaises(socket.timeout):b.receive(.1)
            time.sleep(1.05);w.call(3,Reservation(1001,1))
            with self.assertRaises(socket.timeout):a.receive(.1)

    def test_monitor_remaining_replay_replacement_expiry(self):
        with self.server() as port:
            p=self.peer(port);raw=p.packet(4,MonitorRegistration(1001,2));first=p.exchange(raw)[0].response.body.remainingMillis
            time.sleep(.15);remaining=p.exchange(raw)[0].response.body.remainingMillis
            self.assertLess(remaining,first-80)
            new=p.packet(4,MonitorRegistration(1001,1));p.exchange(new)
            self.assertEqual(0,p.exchange(raw)[0].response.body.remainingMillis)
            time.sleep(1.05);self.assertEqual(0,p.exchange(new)[0].response.body.remainingMillis)

    def test_lost_reservation_reply_still_delivers_callback(self):
        session=uuid4()
        with self.server(drop=str(session)+':1') as port:
            m,w=self.peer(port),self.peer(port,session=session);m.call(4,MonitorRegistration(1001,3))
            raw=w.packet(3,Reservation(1001,1));w.sock.sendto(raw,w.server)
            self.assertEqual(9,m.receive()[0].availableSeats)
            with self.assertRaises(socket.timeout):w.receive(.1)
            self.assertEqual(9,w.exchange(raw)[0].response.body.availableSeats)
            with self.assertRaises(socket.timeout):m.receive(.1)

    def test_real_c_invoker_callback_before_retried_confirmation(self):
        session=uuid4()
        with self.server(drop=str(session)+':1') as port:
            invoker=Invoker(ClientConfig(port=port,session_id=session,timeout_ms=500,max_attempts=5))
            result=[];errors=[]
            def invoke():
                try:result.append(invoker.invoke(4,MonitorRegistration(1001,3)))
                except Exception as exc:errors.append(exc)
            thread=threading.Thread(target=invoke);thread.start()
            try:
                path=self.folder/self._testMethodName/'server.jsonl'
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    if any(e.get('event')=='DROP_REPLY' for e in [json.loads(line) for line in path.read_text().splitlines()]):break
                    time.sleep(.01)
                else:self.fail('Registration reply was not dropped')
                writer=self.peer(port);writer.call(3,Reservation(1001,1))
                thread.join(3);self.assertFalse(thread.is_alive());self.assertFalse(errors)
                outcome=result[0];self.assertFalse(outcome.timed_out);self.assertEqual(2,outcome.attempts)
                self.assertIsNotNone(outcome.pending_callback);self.assertEqual(9,outcome.pending_callback.availableSeats)
                self.assertLess(outcome.reply.response.body.remainingMillis,2700)
            finally:thread.join(3);invoker.close()

if __name__=='__main__': unittest.main()
