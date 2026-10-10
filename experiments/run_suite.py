"""Portable real Java/Python UDP matrix with owned processes and verified A server logs.
Run from repository root: python3 -m experiments.run_suite --case all --mode all
No simulated business responders. Each case starts a fresh Java process and UUID.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import time
from uuid import uuid4

from .analyze_results import CASES, EvidenceError, analyze, load_events, require
from .runtime_check import check_ports

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ROOT / 'server/build/classes'


def repository_metadata():
    """Source archives must remain runnable without Git or a .git directory."""
    if not (ROOT / '.git').exists():
        return dict(baseline=None, working_tree='source archive; no Git metadata')
    try:
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        state = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
    except (OSError, subprocess.CalledProcessError):
        return dict(baseline=None, working_tree='Git metadata unavailable')
    return dict(baseline=revision, working_tree=state)


def compile_java(tests=False):
    sources = sorted((ROOT / 'server/src').rglob('*.java'))
    if tests: sources += sorted((ROOT / 'server/test').rglob('*.java'))
    if CLASSES.exists(): shutil.rmtree(CLASSES)
    CLASSES.mkdir(parents=True, exist_ok=True)
    subprocess.run(['javac', '--release', '17', '-encoding', 'UTF-8', '-d', str(CLASSES), *map(str, sources)], check=True, cwd=ROOT)


def unused_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class OwnedProcesses:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.processes = []
        self.files = []
        self.commands = []

    def start(self, name, command):
        stdout = (self.folder / (name + '.jsonl')).open('w', encoding='utf-8')
        stderr = (self.folder / (name + '.stderr.txt')).open('w', encoding='utf-8')
        self.files.extend((stdout, stderr))
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr)
        self.processes.append(process)
        self.commands.append(dict(name=name, command=command))
        return process

    def ready(self, process, name, event):
        deadline = time.monotonic() + 5
        path = self.folder / (name + '.jsonl')
        while time.monotonic() < deadline:
            if process.poll() is not None: raise RuntimeError(f'{name} exited before readiness; see {self.folder}')
            if path.exists():
                complete = [line for line in path.read_text(encoding='utf-8').splitlines(keepends=True) if line.endswith('\n')]
                if any(json.loads(line).get('event') == event for line in complete): return
            time.sleep(.025)
        raise RuntimeError(f'{name} did not become ready')

    def close(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for stream in self.files: stream.close()
        (self.folder / 'commands.json').write_text(json.dumps(self.commands, indent=2), encoding='utf-8')


def audit_server(events, case, mode, session, client_events):
    """Compare actual per-request execution/cache events, not inferred attempt counts."""
    related = [e for e in events if e.get('sessionId') == session]
    require(not any(e['event'] in ('REPLY_SEND_FAILED','CALLBACK_SEND_FAILED','REQUEST_REJECTED') for e in related), 'Unexpected server failure')
    requests = [e for e in client_events if e['event'] == 'REQUEST_CREATED']
    evidence = []
    for request in requests:
        rid, op = request['requestId'], request['operation']
        group = [e for e in related if e.get('requestId') == rid]
        executions = [e for e in group if e['event'] == 'BUSINESS_EXECUTED']
        hits = [e for e in group if e['event'] == 'CACHE_HIT']
        expected_exec, expected_hits = 1, 0
        if rid == 2 and case == 'all_request_loss': expected_exec = 0
        if rid == 2 and case in ('reply_loss_reserve','reply_loss_set','reply_loss_increase','all_reply_loss'):
            deliveries = 5 if case == 'all_reply_loss' else 2
            expected_exec, expected_hits = (deliveries,0) if mode == 'alo' else (1,deliveries-1)
        require(len(executions) == expected_exec and len(hits) == expected_hits, f'A log counts incorrect for request {rid}')
        require(all(e.get('operation') == op and e.get('mode') == mode.upper() and e.get('status') == 0 for e in executions + hits), 'Wrong A log identity/status')
        received = [e for e in group if e['event'] == 'REQUEST_RECEIVED']
        require(len(received) == expected_exec + expected_hits, 'Missing receive records')
        require(all(e.get('encodedHex') == request['encodedHex'] for e in received), 'Retransmission bytes changed')
        drops = [e for e in group if e['event'] == 'DROP_REPLY']
        expected_drop = 1 if rid == 2 and case.startswith('reply_loss_') else 0
        require(len(drops) == expected_drop, 'First reply injection not proven')
        if mode == 'amo':
            saves = [i for i,e in enumerate(group) if e['event'] == 'HISTORY_SAVED']
            require(len(saves) == expected_exec, 'Missing AMO history save')
            if saves:
                sends = [i for i,e in enumerate(group) if e['event'] in ('REPLY_SENT','DROP_REPLY')]
                require(bool(sends) and saves[0] < sends[0], 'Reply sent before history save')
        evidence.append(dict(requestId=rid, operation=op, businessExecutions=len(executions), cacheHits=len(hits), dropReplies=len(drops)))
    return evidence


def run_case(case, mode, folder):
    session = str(uuid4())
    port = unused_port()
    unknown = case in ('all_request_loss','all_reply_loss')
    proxy_port = unused_port() if unknown else port
    while unknown and proxy_port == port: proxy_port = unused_port()
    owner = OwnedProcesses(folder)
    row = dict(case=case, mode=mode, session=session, flight_id=1001, result='FAILED_OR_INCOMPLETE', evidence=os.path.relpath(Path(folder).resolve(), ROOT))
    try:
        check_ports([port, proxy_port] if unknown else [port])
        command = ['java','-cp',str(CLASSES),'flight.ServerMain','--bind','127.0.0.1','--port',str(port),'--semantics',mode]
        if case.startswith('reply_loss_'): command += ['--drop-first-reply', session + ':2']
        server = owner.start('server', command)
        owner.ready(server,'server','SERVER_READY')
        ready = subprocess.run([sys.executable,'-m','experiments.runtime_check','ready','--port',str(port),'--mode',mode], cwd=ROOT, capture_output=True,text=True,timeout=8)
        (Path(folder)/'readiness.txt').write_text(ready.stdout+ready.stderr,encoding='utf-8')
        require(ready.returncode == 0,'Server readiness query failed')
        if unknown:
            proxy=owner.start('proxy',[sys.executable,'-u','-m','experiments.udp_loss_proxy','--listen-port',str(proxy_port),
                '--server-port',str(port),'--session-id',session,'--request-id','2','--drop','requests' if case=='all_request_loss' else 'replies'])
            owner.ready(proxy,'proxy','PROXY_READY')
        client_log=Path(folder)/'client.jsonl'
        command=[sys.executable,'-m','client','--port',str(proxy_port),'--semantics',mode,'--session-id',session,
            '--case','reply_loss_reserve' if unknown else case,'--flight-id','1001','--source','Singapore','--destination','Beijing',
            '--quantity','1','--new-price','120','--delta','20','--monitor-seconds','2','--timeout-ms','1000','--max-attempts','5','--log-file',str(client_log)]
        owner.commands.append(dict(name='client',command=command))
        client=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=25)
        (Path(folder)/'client.console.txt').write_text(client.stdout+client.stderr,encoding='utf-8')
        owner.close()
        events=load_events(client_log)
        result=analyze(events,case,mode,session,client.returncode,load_events(Path(folder)/'proxy.jsonl') if unknown else ())
        audited=audit_server(load_events(Path(folder)/'server.jsonl'),case,mode,session,events)
        (Path(folder)/'server-audit.json').write_text(json.dumps(audited,indent=2),encoding='utf-8')
        row.update(result)
        target=next((item for item in audited if item['requestId']==2),None)
        row.update(result='PASSED_LOCAL_UDP',business_executions=target['businessExecutions'] if case not in ('baseline','monitor') else '',
            cache_hits=target['cacheHits'] if case not in ('baseline','monitor') else '',notes='Actual Java/Python loopback UDP; A server logs verified. Not a three-computer result.')
        return row
    except Exception as exc:
        row['notes']=str(exc)
        raise
    finally:
        owner.close()
        (Path(folder)/'result.json').write_text(json.dumps(row,indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('all',*CASES),default='all')
    parser.add_argument('--mode',choices=('all','alo','amo'),default='all')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    compile_java()
    folder=args.output or ROOT/'evidence/a'/('udp-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    folder = folder.resolve()
    folder.mkdir(parents=True,exist_ok=False)
    environment=dict(platform=platform.platform(),python=sys.version,java=subprocess.run(['java','-version'],capture_output=True,text=True).stderr,
        **repository_metadata(), scope='Real loopback UDP, not multiple computers')
    (folder/'environment.json').write_text(json.dumps(environment,indent=2),encoding='utf-8')
    rows=[]
    for case in CASES if args.case=='all' else (args.case,):
        for mode in ('alo','amo') if args.mode=='all' else (args.mode,):
            rows.append(run_case(case,mode,folder/(case+'-'+mode)))
            print(case,mode,rows[-1]['result'],flush=True)
            with (folder/'results.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('Evidence:',folder,flush=True)

if __name__=='__main__': main()
