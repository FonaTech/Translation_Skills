#!/usr/bin/env python3
"""Validate portable structure, local reference links and platform metadata."""
from pathlib import Path
import ast,json,re,sys
import yaml
R=Path(__file__).resolve().parent.parent;S=R/'skills/document-translation'
def validate():
 errors=[];checks=[]
 raw=(S/'SKILL.md').read_text();front=yaml.safe_load(raw.split('---',2)[1]);assert front['name']==S.name;assert isinstance(front['description'],str);assert len(front['name'])<64
 checks.append('portable frontmatter')
 for p in R.rglob('*.md'):
  for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
   if '://' in target or target.startswith('#'):continue
   target=target.split('#')[0]
   if target and not (p.parent/target).exists():errors.append(f'Broken local link: {p.relative_to(R)} -> {target}')
 checks.append('local Markdown links')
 for p in R.rglob('*.json'):
  try:json.loads(p.read_text())
  except (ValueError,UnicodeError) as e:errors.append(f'Invalid JSON: {p.relative_to(R)}: {e}')
 for p in R.rglob('*.py'):
  try:ast.parse(p.read_text())
  except SyntaxError as e:errors.append(f'Invalid Python: {p.relative_to(R)}: {e}')
 overlay=json.loads((S/'agents/clouds-coder.json').read_text());assert overlay['clouds_coder']['runtime_contract']
 for rel in overlay['entrypoints']:
  if not (S/rel).is_file():errors.append('Missing Clouds entrypoint: '+rel)
 assert yaml.safe_load((S/'agents/openai.yaml').read_text())['interface']['default_prompt'].find('$document-translation')>=0
 for base in ['.claude-plugin','claude-plugin']:
  plugin=json.loads((R/base/'plugin.json').read_text());assert plugin['skills']=='./skills/';assert plugin['author']['name']=='Yufeng Zhan'
  market=json.loads((R/base/'marketplace.json').read_text());assert market['plugins'][0]['source']=='./'
 checks.extend(['JSON/Python syntax','Clouds resource entrypoints','Codex UI metadata','Claude plugin manifests'])
 version=(R/'VERSION').read_text().strip()
 assert version=='1.0.2',f'Unexpected release version: {version}'
 for base in ['.claude-plugin','claude-plugin']:
  assert json.loads((R/base/'plugin.json').read_text())['version']==version
  assert json.loads((R/base/'marketplace.json').read_text())['plugins'][0]['version']==version
 for rel in ['README.md','README_zh-CN.md','CHANGELOG.md']:
  if version not in (R/rel).read_text():errors.append(f'Missing current version metadata: {rel}')
 checks.append('release version consistency')
 for p in R.rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts:continue
  if p.suffix in {'.py','.md','.json','.yaml','.html','.css','.js','.txt','.yml'}:
   text=p.read_text(errors='replace')
   if re.search(r'/(?:Users|home)/[^/\s]+/',text):errors.append(f'Absolute private home path in {p.relative_to(R)}')
 checks.append('private absolute-path scan; domain neutrality reviewed separately')
 print(json.dumps({'checks':checks,'errors':errors,'pass':not errors},indent=2));return 1 if errors else 0
if __name__=='__main__':sys.exit(validate())
