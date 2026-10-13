"""Recheck retained 12 October LAN evidence without contacting the flight server."""
from pathlib import Path
import sys,json,hashlib,collections
from dataclasses import asdict

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from client.protocol_codec import decode_message
OUT=ROOT/'evidence/demo/audit-20261013'
OUT.mkdir(exist_ok=True)
files={}; checks=[]
def load(relative):
    p=ROOT/relative
    files[relative]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
    return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
def check(name,condition,detail=None):
    checks.append(dict(check=name,passed=bool(condition),detail=detail))
    if not condition:raise AssertionError(name)
def key(e):return e.get('sessionId'),e.get('requestId')
def select(events,event,identity=None):
    return [e for e in events if e['event']==event and (identity is None or key(e)==identity)]
def server(run):
    e=load(f'evidence/demo/{run}/server.jsonl')
    check(run+' ready',len(select(e,'SERVER_READY'))==1)
    check(run+' no send failures',not any('FAILED' in x['event'] for x in e))
    return e

mapping=[('basic','20261012-03-basic-02','20261012-03-basic-en-01'),
         ('dual','20261012-05-dual-02','20261012-05-dual-en-01'),
         ('isolation','20261012-06-isolation-01','20261012-06-isolation-en-01')]
monitor_results=[];runs={}
for stage,a,b in mapping:
    ae=server(a);be=load(f'evidence/demo/{b}/client-B.jsonl');runs[stage]=ae
    for created in select(be,'REQUEST_CREATED'):
        matches=select(ae,'REQUEST_RECEIVED',key(created))
        check(stage+' B request matches A '+str(key(created)),any(x['encodedHex']==created['encodedHex'] for x in matches))
    for reply in select(be,'REPLY'):
        matches=select(ae,'REPLY_SENT',key(reply))
        check(stage+' B reply matches A '+str(key(reply)),any(json.loads(json.dumps(asdict(decode_message(bytes.fromhex(x['encodedHex'])).response.body)))==reply['body'] for x in matches))
    for cb in select(be,'CALLBACK'):
        matches=select(ae,'CALLBACK_SENT',key(cb))
        check(stage+' B callback matches A '+str(key(cb)),any(all(x[f]==cb[f] for f in ('flightId','availableSeats','sequence')) for x in matches))
    for start in select(be,'MONITOR_START'):
        end=select(be,'MONITOR_END',key(start))
        check(stage+' monitor natural end',len(end)==1 and end[0]['monotonic']>=start['deadline'])
        monitor_results.append(dict(stage=stage,sessionId=start['sessionId'],requestId=start['requestId'],
            start=start['monotonic'],deadline=start['deadline'],end=end[0]['monotonic'],elapsed=end[0]['monotonic']-start['monotonic']))

basic=runs['basic'];reg=('06aa4974-ca5b-43b0-b635-f4fabfb94be8',4);writer='1e4fa4b2-d38b-42cf-8c0a-428986eaea4e'
cb=select(basic,'CALLBACK_SENT',reg)
check('basic exactly one callback',len(cb)==1 and cb[0]['availableSeats']==9 and cb[0]['triggerRequestId']==8)
registration=select(basic,'BUSINESS_EXECUTED',reg)[0]
post=select(basic,'BUSINESS_EXECUTED',(writer,13))[0]
delta=(post['nanoTime']-registration['nanoTime'])/1e9
check('basic post-expiry reservation after 60 seconds',delta>60,delta)
check('basic post-expiry reply 8 seats',post['status']==0 and 'availableSeats=8' in post['response'])
check('basic no callback for post-expiry write',not any(x.get('triggerSessionId')==writer and x.get('triggerRequestId')==13 for x in cb))

dual=select(runs['dual'],'CALLBACK_SENT');check('dual four callbacks',len(dual)==4)
check('dual two recipient computers',len({e['peer'].split(':')[0] for e in dual})==2)
for seq,seats in [(1,9),(2,8)]:
    chosen=[x for x in dual if x['sequence']==seq]
    check('dual sequence '+str(seq),len(chosen)==2 and all(x['flightId']==1001 and x['availableSeats']==seats for x in chosen))
isolation=select(runs['isolation'],'CALLBACK_SENT')
expected={(1001,'2ce9ff0b-55f9-4f7e-8f9e-26c717a946c9',2,'/10.91.162.52:58119',9,1),
          (1002,'4d1cebe1-a338-41f5-b74a-d9f2b5f5e6b7',2,'/10.91.33.41:53423',19,1)}
check('isolation exact flight/registration/recipient/seat/sequence pairs',len(isolation)==2 and {
    (x['flightId'],x['sessionId'],x['requestId'],x['peer'],x['availableSeats'],x['sequence']) for x in isolation}==expected)

faults=[];fixed='11111111-1111-4111-8111-111111111111'
cases=[('reserve','alo','20261012-07-reserve-alo-01',8,100,3),
       ('reserve','amo','20261012-07-reserve-amo-en-01',9,100,3),
       ('increase','alo','20261012-07-increase-alo-en-01',10,140,6),
       ('increase','amo','20261012-07-increase-amo-en-01',10,120,6),
       ('set','alo','20261012-07-set-alo-en-01',10,120,5),
       ('set','amo','20261012-07-set-amo-en-01',10,120,5)]
for case,mode,run,seats,fare,op in cases:
    e=server(run);target=[x for x in e if key(x)==(fixed,2)];counts=collections.Counter(x['event'] for x in target)
    received=select(target,'REQUEST_RECEIVED')
    check(run+' exact target counts',counts['REQUEST_RECEIVED']==2 and counts['BUSINESS_EXECUTED']==(2 if mode=='alo' else 1) and counts['CACHE_HIT']==(0 if mode=='alo' else 1) and counts['DROP_REPLY']==1 and counts['REPLY_SENT']==1)
    check(run+' stable request bytes and peer',len({x['encodedHex'] for x in received})==1 and len({x['peer'] for x in received})==1)
    check(run+' expected operation/mode',all(x['operation']==op and x['mode']==mode.upper() for x in target))
    before=decode_message(bytes.fromhex(select(e,'REPLY_SENT',(fixed,1))[0]['encodedHex'])).response.body
    after=decode_message(bytes.fromhex(select(e,'REPLY_SENT',(fixed,3))[0]['encodedHex'])).response.body
    check(run+' clean seed',before.availableSeats==10 and before.airfare==100)
    check(run+' final state',after.availableSeats==seats and after.airfare==fare)
    if mode=='amo':
        names=[x['event'] for x in target]
        check(run+' history saved before loss and cache replay',names.index('BUSINESS_EXECUTED')<names.index('HISTORY_SAVED')<names.index('DROP_REPLY')<names.index('CACHE_HIT')<names.index('REPLY_SENT'))
        check(run+' exact cached reply bytes',select(target,'DROP_REPLY')[0]['encodedHex']==select(target,'REPLY_SENT')[0]['encodedHex'])
    faults.append(dict(case=case,mode=mode,server_run=run,sessionId=fixed,requestId=2,operation=op,received=2,
        executions=counts['BUSINESS_EXECUTED'],cache_hits=counts['CACHE_HIT'],dropped_replies=1,final_seats=seats,final_fare=fare))

result=dict(date='2026-10-13',status='PASSED',scope='Read-only audit of original 12 October LAN A server JSON Lines and retained B client JSON Lines. C terminal observations remain original screenshots, not reconstructed raw client logs.',
    implementation_baseline='3241a333b38899ec65fe0ba8e8fcc12001b03967',run_mapping=mapping,monitors=monitor_results,
    basic_post_registration_write_seconds=delta,dual_callbacks=dual,isolation_callbacks=isolation,fault_runs=faults,
    checks=checks,input_files=files)
(OUT/'lan-audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(status=result['status'],checks=len(checks),fault_runs=faults,monitors=monitor_results),indent=2))
