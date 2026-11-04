#!/usr/bin/env python3
import argparse,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
EXCLUDE={'SHA256SUMS.txt','.DS_Store','UPLOAD_zh-CN.md'}
def files():return [p for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name not in EXCLUDE and p.suffix not in {'.pyc','.tmp','.log'} and not any(x in {'.git','__pycache__','.venv','node_modules','work','validation'} for x in p.relative_to(ROOT).parts)]
def main():
 p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();actual=''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.relative_to(ROOT).as_posix()+'\n' for f in files());path=ROOT/'SHA256SUMS.txt'
 if a.write:path.write_text(actual);print('Wrote',len(files()),'checksums');return
 if not path.exists() or path.read_text()!=actual:raise SystemExit('Checksum manifest missing/stale')
 print('All',len(files()),'checksums verified')
if __name__=='__main__':main()
