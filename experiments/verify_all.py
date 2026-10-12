"""Reproduce module and real Java integration checks, optionally the 16-case matrix."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from .run_suite import ROOT, CLASSES, compile_java, repository_metadata


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    folder=(args.output or ROOT/'evidence/a'/('verification-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
    folder.mkdir(parents=True,exist_ok=False)
    compile_java(tests=True)
    commands=[('a-protocol',['java','-cp',str(CLASSES),'flight.ProtocolSelfTest']),
        ('a-semantics',['java','-cp',str(CLASSES),'flight.SemanticsSelfTest']),
        ('b-business',['java','-cp',str(CLASSES),'flight.BusinessSelfTest']),
        ('b-monitor',['java','-cp',str(CLASSES),'flight.MonitorSelfTest']),
        ('c-client',[sys.executable,'-m','unittest','discover','-s','client/tests','-v']),
        ('experiment-tools',[sys.executable,'-m','unittest','experiments.test_analyze_results','experiments.test_runtime_check',
            'experiments.test_udp_loss_proxy','experiments.test_monitor_evidence','experiments.test_server_evidence','-v']),
        ('java-integration',[sys.executable,'-m','unittest','experiments.test_java_integration','-v'])]
    if args.matrix:commands.append(('udp-matrix',[sys.executable,'-m','experiments.run_suite','--output',str(folder/'matrix')]))
    environment=dict(os.environ,SC6103_EVIDENCE_DIR=str(folder/'network'))
    metadata=dict(platform=platform.platform(),python=sys.version,java=subprocess.run(['java','-version'],capture_output=True,text=True).stderr,
        javac=subprocess.run(['javac','-version'],capture_output=True,text=True).stdout,**repository_metadata(),
        source_state='working tree; see source-manifest.json for exact tested source hashes', scope='Local computer, real UDP processes; not three physical computers')
    import hashlib
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for pattern in ('server/**/*.java','client/**/*.py','experiments/*.py') for p in ROOT.glob(pattern)}
    (folder/'source-manifest.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
    (folder/'environment.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    results=[]
    for name,command in commands:
        with (folder/(name+'.txt')).open('w',encoding='utf-8') as log:
            process=subprocess.run(command,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        results.append(dict(name=name,command=command,exit_code=process.returncode))
        (folder/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(name,'PASS' if process.returncode==0 else 'FAIL',flush=True)
        if process.returncode:raise SystemExit(f'Failed: {folder/(name+".txt")}')
    print('All selected checks passed; evidence:',folder,flush=True)

if __name__=='__main__':main()
