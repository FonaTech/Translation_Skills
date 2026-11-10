#!/usr/bin/env python3
"""Advisory, transparent glossary checks; no automatic text replacement."""
import argparse,json,re
from pathlib import Path
from translate import project,units,read,write

def check(root,glossary):
 r,m,c=project(root);g=read(glossary);findings=[]
 for b,u in units(c):
  for term in g.get('terms',[]):
   src=term['source'];pattern=re.escape(src)
   if term.get('whole_word',False):pattern=r'(?<!\w)'+pattern+r'(?!\w)'
   if not re.search(pattern,u['source'],0 if term.get('case_sensitive') else re.I):continue
   for lang,allowed in term.get('targets',{}).items():
    if lang not in m['target_languages']:continue
    for edition in m['editions']:
     target=u.get('translations',{}).get(lang,{}).get(edition,'')
     if not any(t in target for t in allowed):findings.append({'id':u['id'],'source_term':src,'language':lang,'edition':edition,'expected_any':allowed,'severity':term.get('severity','review'),'locator':b['source']})
 return {'findings':findings,'automatic_replacement':False,'note':'Context, morphology and legitimate alternatives need semantic review; zero findings does not prove consistent terminology.'}
if __name__=='__main__':
 from runtime_encoding import configure_utf8
 configure_utf8()
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('glossary');p.add_argument('--output');a=p.parse_args();result=check(a.project,a.glossary)
 if a.output:write(a.output,result)
 print(json.dumps(result,ensure_ascii=False,indent=2))
