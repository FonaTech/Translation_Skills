#!/usr/bin/env python3
"""Check isolated installations; optionally inspect pure Clouds metadata methods."""
import argparse,ast,hashlib,json,sys,tempfile
from pathlib import Path,PurePosixPath
import yaml
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'tools'));import install

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--clouds-source',help='Optional trusted local Clouds_Coder.py snapshot; never imported whole');p.add_argument('--output');a=p.parse_args();namespace=None;source_sha=None
 if a.clouds_source:
  raw=Path(a.clouds_source).read_text();source_sha=hashlib.sha256(raw.encode()).hexdigest();tree=ast.parse(raw);helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_meta_string_list');cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SkillStore');wanted={'_skill_meta_section','_skill_entrypoints','_skill_runtime_contract','_skill_attachment_globs'};methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in wanted];assert len(methods)==4,'Runtime contract changed; inspect adapter'
  module=ast.Module(body=[helper,ast.ClassDef(name='ContractOnly',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[]);namespace={'PurePosixPath':PurePosixPath};exec(compile(ast.fix_missing_locations(module),'<trusted isolated metadata methods>','exec'),namespace)
 results=[]
 with tempfile.TemporaryDirectory() as td:
  for target in ['codex','claude','opencode','clouds']:
   dest=install.destinations(target,Path(td)/'project',Path(td)/'home',None);install.install(target,dest,True);front=yaml.safe_load((dest/'SKILL.md').read_text().split('---',2)[1]);assert front['name']=='document-translation';checked=False
   if target=='clouds' and namespace:
    obj=namespace['ContractOnly']();assert obj._skill_runtime_contract(front);assert all((dest/x).is_file() for x in obj._skill_entrypoints(front));assert obj._skill_attachment_globs(front);checked=True
   results.append({'client':target,'isolated_copy':True,'portable_frontmatter':True,'clouds_metadata_methods':checked,'live_client_session':False})
 report={'tests':results,'inspected_snapshot_sha256':source_sha,'method':'isolated copies; optional AST-selected pure methods from a trusted source, no whole-runtime import','result':'tested install/metadata contract only; not full loader or interactive client execution'}
 if a.output:Path(a.output).write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
