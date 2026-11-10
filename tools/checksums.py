#!/usr/bin/env python3
import argparse,hashlib,sys
from pathlib import Path
from release_policy import public_files
ROOT=Path(__file__).resolve().parent.parent
def files():return public_files(ROOT,include_manifest=False)
def main():
 p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');a=p.parse_args();actual=''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.relative_to(ROOT).as_posix()+'\n' for f in files());path=ROOT/'SHA256SUMS.txt'
 if a.write:path.write_text(actual, encoding='utf-8');print('Wrote',len(files()),'checksums');return
 if not path.exists() or path.read_text( encoding='utf-8')!=actual:raise SystemExit('Checksum manifest missing/stale')
 print('All',len(files()),'checksums verified')
if __name__=='__main__':
    from cli_encoding import configure_utf8
    configure_utf8()
    main()
