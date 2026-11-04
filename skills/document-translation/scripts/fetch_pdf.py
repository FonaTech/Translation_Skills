#!/usr/bin/env python3
"""Fetch authorized public HTTP(S) PDF sources with signature/hash/provenance checks."""
import argparse,hashlib,ipaddress,json,socket,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit

def check_url(url,allow_local=False):
 u=urlsplit(url)
 if u.scheme not in {'https','http'} or not u.hostname or u.username or u.password:raise ValueError('Use an HTTP(S) URL without embedded credentials.')
 if not allow_local:
  for x in socket.getaddrinfo(u.hostname,u.port or (443 if u.scheme=='https' else 80)):
   addr=ipaddress.ip_address(x[4][0])
   if not addr.is_global:raise ValueError('Private/local destinations require explicit --allow-local for trusted tests.')
 return u

def fetch(url,output,rights='not-verified',allow_local=False,max_mb=50):
 check_url(url,allow_local);output=Path(output)
 if output.exists():raise ValueError('Existing output preserved: '+str(output))
 output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as td:
  temp=Path(td)/'download';headers=Path(td)/'headers'
  # Redirects handled explicitly so each destination is checked before connection.
  current=url
  for _ in range(6):
   check_url(current,allow_local)
   res=subprocess.run(['curl','--silent','--show-error','--proto','=http,https','--connect-timeout','20','--max-time','90','--max-filesize',str(int(max_mb*1024*1024)),'--dump-header',str(headers),'--output',str(temp),'--write-out','%{http_code}',current],text=True,capture_output=True)
   if res.returncode:raise ValueError('Download failed: '+res.stderr[:500])
   status=int(res.stdout[-3:]);hs=headers.read_text(errors='replace');locations=[x.split(':',1)[1].strip() for x in hs.splitlines() if x.lower().startswith('location:')]
   if status in {301,302,303,307,308} and locations:
    from urllib.parse import urljoin
    current=urljoin(current,locations[-1]);continue
   if status!=200:raise ValueError('HTTP '+str(status))
   break
  else:raise ValueError('Too many redirects')
  if temp.stat().st_size>max_mb*1024*1024:raise ValueError('File exceeds size limit')
  data=temp.read_bytes()
  if b'%PDF-' not in data[:1024]:raise ValueError('Response is not a PDF signature')
  import fitz
  d=fitz.open(temp);count=len(d);d.close();output.write_bytes(data)
 record={'requested_url':url,'final_url':current,'retrieved_at':datetime.now(timezone.utc).isoformat(),'filename':output.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'pages':count,'rights':rights,'note':'Acquisition does not authorize redistribution or establish translation quality.'};output.with_suffix('.provenance.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');return record
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('url');p.add_argument('output');p.add_argument('--rights',default='not-verified');p.add_argument('--allow-local',action='store_true');p.add_argument('--max-mb',type=float,default=50);a=p.parse_args()
 try:print(json.dumps(fetch(a.url,a.output,a.rights,a.allow_local,a.max_mb),ensure_ascii=False,indent=2))
 except (ValueError,OSError) as e:print('ERROR: '+str(e),file=sys.stderr);sys.exit(2)
