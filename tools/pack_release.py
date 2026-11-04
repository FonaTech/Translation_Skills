#!/usr/bin/env python3
"""Validate, checksum, zip and reopen a clean release without private work files."""
import argparse,hashlib,subprocess,sys,zipfile
from pathlib import Path
R=Path(__file__).resolve().parent.parent
EXCLUDED={'.git','__pycache__','.venv','node_modules','.DS_Store','work','validation','UPLOAD_zh-CN.md'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output).expanduser().resolve()
 if out.is_relative_to(R):raise ValueError('Write release archives outside the repository.')
 if out.exists():raise ValueError('Existing archive preserved; choose a new output path.')
 subprocess.run([sys.executable,str(R/'tools/validate.py')],check=True)
 subprocess.run([sys.executable,str(R/'tools/checksums.py')],check=True)
 out.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for f in sorted(R.rglob('*')):
   rel=f.relative_to(R)
   if f.is_file() and not any(x in EXCLUDED for x in rel.parts) and f.suffix not in {'.pyc','.tmp','.log'}:z.write(f,('Translation_Skills'/rel).as_posix())
 with zipfile.ZipFile(out) as z:
  assert z.testzip() is None,'ZIP CRC failure'
  manifest=z.read('Translation_Skills/SHA256SUMS.txt').decode()
  for line in manifest.splitlines():
   h,rel=line.split('  ',1);assert hashlib.sha256(z.read('Translation_Skills/'+rel)).hexdigest()==h,'Checksum mismatch: '+rel
  for rel in ['.claude-plugin/plugin.json','.github/workflows/validate.yml','README.md','LICENSE','skills/document-translation/SKILL.md']:assert 'Translation_Skills/'+rel in z.namelist(),rel
  count=len(z.namelist())
 digest=hashlib.sha256(out.read_bytes()).hexdigest();out.with_suffix(out.suffix+'.sha256').write_text(digest+'  '+out.name+'\n');print(f'Packaged and reopened {out.name}: {count} files; SHA-256 {digest}')
if __name__=='__main__':main()
