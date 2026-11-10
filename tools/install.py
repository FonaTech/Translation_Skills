#!/usr/bin/env python3
"""Copy portable skill bundles to selected clients. Dry-run unless --apply."""
import argparse,datetime,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
NAME='document-translation'
def destinations(target,project=None,home=None,clouds=None):
 home=Path(home or Path.home());project=Path(project).resolve() if project else None
 paths={'codex':(project/'.agents/skills' if project else home/'.agents/skills'), 'codex-legacy':(project/'.codex/skills' if project else home/'.codex/skills'),'claude':(project/'.claude/skills' if project else home/'.claude/skills'),'opencode':(project/'.opencode/skills' if project else home/'.config/opencode/skills')}
 if target=='clouds':
  if not clouds and not project:raise ValueError('Clouds requires --clouds-root or --project with the active project root.')
  return Path(clouds).resolve()/NAME if clouds else project/'skills/generated'/NAME
 return paths[target]/NAME

def install(target,dest,apply=False):
 source=ROOT/'skills'/NAME;dest=Path(dest).absolute()
 if dest.is_symlink():raise ValueError('Symlink destination preserved; select a real install path.')
 dest=dest.resolve()
 if dest==source or source.is_relative_to(dest) or dest.is_relative_to(source):raise ValueError('Install destination overlaps source.')
 result={'target':target,'destination':str(dest),'action':'copy','applied':False,'backup':None}
 if not apply:return result
 if dest.is_symlink():raise ValueError('Symlink destination preserved; select a real install path.')
 if dest.exists():
  stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=dest.with_name(dest.name+'.backup-'+stamp);dest.rename(backup);result['backup']=str(backup)
 dest.parent.mkdir(parents=True,exist_ok=True)
 try:
  shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store'))
  if target=='clouds':
   import yaml
   skill=dest/'SKILL.md';raw=skill.read_text( encoding='utf-8');_,front,body=raw.split('---',2);meta=yaml.safe_load(front);overlay=json.loads((dest/'agents/clouds-coder.json').read_text( encoding='utf-8'));meta.update(overlay);skill.write_text('---\n'+yaml.safe_dump(meta,allow_unicode=True,sort_keys=False)+'---'+body, encoding='utf-8')
 except Exception:
  if dest.exists():shutil.rmtree(dest)
  if result['backup']:Path(result['backup']).rename(dest)
  raise
 result['applied']=True;return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--targets',nargs='+',choices=['codex','codex-legacy','claude','opencode','clouds'],required=True);p.add_argument('--project');p.add_argument('--home',help='Explicit test/user home root; never changes HOME');p.add_argument('--clouds-root');p.add_argument('--apply',action='store_true');a=p.parse_args()
 print(json.dumps([install(t,destinations(t,a.project,a.home,a.clouds_root),a.apply) for t in a.targets],ensure_ascii=False,indent=2))
if __name__=='__main__':
 from cli_encoding import configure_utf8
 configure_utf8()
 try:main()
 except (ValueError,OSError) as e:print('ERROR: '+str(e),file=sys.stderr);sys.exit(2)
