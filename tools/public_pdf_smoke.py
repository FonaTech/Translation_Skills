#!/usr/bin/env python3
"""Reproduce three explicitly scoped public-PDF tests in an external directory."""
import argparse,json,sys
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'skills/document-translation/scripts'))
import translate as t,publishing,fetch_pdf
SOURCES=[('w3c-dummy','https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf'),('irs-w9','https://www.irs.gov/pub/irs-pdf/fw9.pdf'),('bill-of-rights','https://www.archives.gov/files/founding-docs/bill-of-rights.pdf')]
EXCERPTS=[('Give form to the requester. Do not send to the IRS.','将此表交给索取表格的一方。不要寄送给美国国税局（IRS）。','这份表应交给向你索取表格的人或机构；不要把它寄给 IRS。'),('Print or type.','请用印刷体书写或打字填写。','填写时，请使用印刷体书写，或打字输入。'),('See Specific Instructions on page 3.','请参阅第 3 页的具体说明。','具体填写要求见第 3 页。'),('Business name/disregarded entity name, if different from above.','企业名称／税务上不被视为独立实体的实体名称（如与上文不同）。','如果企业或税务上不被视为独立实体的实体，其名称与上文填写的名称不同，请填写该名称。'),('Requester’s name and address (optional)','索取表格一方的姓名或名称及地址（选填）','可选择填写索取表格的人或机构的姓名或名称及地址。'),('List account number(s) here (optional)','在此列出账户号码（选填）','如需填写账户号码，可列在这里；此项为选填。')]
def run(root,browser=None,vision=False):
 import fitz
 root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True);results=[]
 for name,url in SOURCES:
  file=root/'downloads'/(name+'.pdf');rec={'name':name,'url':url}
  try:
   rec['provenance']=fetch_pdf.fetch(url,file,'Provider rights apply; acquisition test, not relicensing')
   work=root/name;t.init(argparse.Namespace(project=str(work),title=name+' · limited validation fixture',languages='zh-Hans',style='editorial',page_size='A4',columns=1))
   t.ingest(argparse.Namespace(project=str(work),files=[str(file)],pages=None,password=None,order='auto',tables=False));r,m,c=t.project(work)
   if name=='bill-of-rights':
    if vision:t.ocr(argparse.Namespace(project=str(work),document='D001',pages=None,engine='vision',languages='en-US',allow_native=False))
    rec['status']='OCR review required; translation not released';results.append(rec);continue
   if name=='w3c-dummy':
    assert ' '.join(' '.join(u['source'] for b,u in t.units(c)).split())=='Dummy PDF file','Source fixture changed; inspect before applying fixed demonstration text'
    for b,u in t.units(c):u['translations']={'zh-Hans':{'faithful':'PDF 示例文件','interpretive':'用于测试的 PDF 文件'}}
    for x in c['issues']:x['status']='resolved';x['resolution']='Expected short fixture; exact source phrase checked.'
   else:
    d=fitz.open(file);txt=' '.join(d[0].get_text().split());c['blocks']=[];c['issues']=[];c['sources'][0]['next_block_index']=1;c['sources'][0]['selection_scope']={'pages':[1],'scope':'six selected instruction excerpts only; not full tax form'}
    for en,f,i in EXCERPTS:
     assert en in txt,'Source revision changed; fixed excerpt not found: '+en
     b=t.add_block(c,'D001','paragraph',{'page':1,'element':'selected exact excerpt'},[en]);b['units'][0]['translations']={'zh-Hans':{'faithful':f,'interpretive':i}}
   t.write(r/'content.json',c);publishing.build(r);publishing.render(r,browser);rec['status']='Both scoped demo editions and alignment rendered; no automatic semantic certification'
  except Exception as e:rec['status']='failed';rec['error']=str(e)
  results.append(rec)
 t.write(root/'results.json',results);print(json.dumps(results,ensure_ascii=False,indent=2));return 1 if any(x['status']=='failed' for x in results) else 0
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-root',required=True);p.add_argument('--browser');p.add_argument('--vision',action='store_true',help='Optional local macOS OCR attempt, still unreviewed');a=p.parse_args();sys.exit(run(a.output_root,a.browser,a.vision))
