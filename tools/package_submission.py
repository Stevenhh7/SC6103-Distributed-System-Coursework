"""Build a source/evidence submission ZIP, or a complete review archive.

Run from a checkout or unpacked source tree; output defaults outside the project.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]

RUN_INSTRUCTIONS = """SC6103 Distributed Flight Information System

Requirements: JDK 17+ (including javac) and Python 3.10+.
The application and tests require only standard libraries.
Run commands from the extracted project directory.

Build on macOS/Linux:
  sh server/build.sh
Build on Windows PowerShell:
  .\\server\\build.ps1

Server:
  java -cp server/build/classes flight.ServerMain --bind 0.0.0.0 --port 6789 --semantics amo
Client on another computer:
  python -X utf8 -m client --server <server-IPv4> --port 6789 --semantics amo
Use python3 instead of python on macOS/Linux if needed.
Use the same semantics on both sides; replace amo with alo to compare modes.
Restart the server to reset the in-memory flights, subscriptions and history.

Run the retained automated checks and local UDP matrix:
  python -m experiments.verify_all --matrix
Recheck the retained LAN logs:
  python tools/audit_lan_evidence.py

Contents: application sources, build scripts, test sources, experiment tools,
original screenshots and test evidence. PACKAGE_MANIFEST.json records file hashes.
Markdown documents, the lab report, compiled classes, caches and nested archives
are intentionally excluded. Submit the lab report separately.
"""

def source_file(path):
    """Keep runnable/testable code and original evidence, without report materials."""
    relative = path.relative_to(ROOT)
    if path.suffix.lower() == '.md':
        return False
    if relative.parts[0] == 'evidence':
        return True
    if relative.parts[0] in ('server', 'client', 'experiments'):
        return path.suffix.lower() in ('.java', '.py', '.json', '.sh', '.ps1')
    return relative.as_posix() in ('tools/package_submission.py', 'tools/audit_lan_evidence.py')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',choices=('source','review'),default='source')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    default_name = 'SC6103_Source_Code.zip' if args.profile == 'source' else 'SC6103_Group_Project_Review.zip'
    output=(args.output or ROOT.parent/'output'/default_name).resolve()
    if output.is_relative_to(ROOT):parser.error('Choose an output outside the project to avoid recursive packaging.')
    output.parent.mkdir(parents=True,exist_ok=True)
    excluded={'.git','__pycache__','.pytest_cache','.venv','node_modules','work','.DS_Store','PACKAGE_MANIFEST.json'}
    # Published source ZIPs/checksums must not be recursively packaged. Keep
    # superseded rehearsal evidence on disk, outside the final submission archive.
    superseded=[p.parent for p in ROOT.glob('evidence/demo/*/SUPERSEDED.md')]
    files=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and not any(x in excluded for x in p.relative_to(ROOT).parts)
           and not p.relative_to(ROOT).as_posix().startswith(('server/build/','output/source/'))
           and not any(p.is_relative_to(folder) for folder in superseded)
           and p.suffix not in ('.pyc','.class','.zip')]
    if args.profile == 'source':
        files=[p for p in files if source_file(p)]
    manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    if args.profile == 'source':
        manifest['README.txt']=hashlib.sha256(RUN_INSTRUCTIONS.encode('utf-8')).hexdigest()
    with ZipFile(output,'w',compression=ZIP_DEFLATED) as z:
        for p in files:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
        if args.profile == 'source':
            z.writestr(ROOT.name+'/README.txt',RUN_INSTRUCTIONS)
        z.writestr(ROOT.name+'/PACKAGE_MANIFEST.json',json.dumps(manifest,indent=2,ensure_ascii=False))
    print(json.dumps(dict(archive=str(output),profile=args.profile,files=len(manifest),sha256=hashlib.sha256(output.read_bytes()).hexdigest()),indent=2))

if __name__=='__main__':main()
