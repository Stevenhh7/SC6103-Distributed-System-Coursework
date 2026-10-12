"""Build a source/report review ZIP without Git metadata or generated runtime caches.

Run from a checkout or unpacked source tree; output defaults outside the project.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT.parent/'output/SC6103_Group_Project_Review.zip')
    args=parser.parse_args();output=args.output.resolve()
    if output.is_relative_to(ROOT):parser.error('Choose an output outside the project to avoid recursive packaging.')
    output.parent.mkdir(parents=True,exist_ok=True)
    excluded={'.git','__pycache__','.pytest_cache','.venv','node_modules','work','.DS_Store','PACKAGE_MANIFEST.json'}
    files=[p for p in sorted(ROOT.rglob('*')) if p.is_file() and not any(x in excluded for x in p.relative_to(ROOT).parts)
           and not p.relative_to(ROOT).as_posix().startswith('server/build/') and p.suffix not in ('.pyc','.class','.zip')]
    manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with ZipFile(output,'w',compression=ZIP_DEFLATED) as z:
        for p in files:z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
        z.writestr(ROOT.name+'/PACKAGE_MANIFEST.json',json.dumps(manifest,indent=2,ensure_ascii=False))
    print(json.dumps(dict(archive=str(output),files=len(files),sha256=hashlib.sha256(output.read_bytes()).hexdigest()),indent=2))

if __name__=='__main__':main()
