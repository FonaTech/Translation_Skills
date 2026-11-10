#!/usr/bin/env python3
"""Create author-owned fixtures outside the skill and run real extraction/layout."""
import argparse,contextlib,io,json,sys
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'skills/document-translation/scripts'))
import translate as t,publishing

def args(**kw):return argparse.Namespace(**kw)
def run(root,browser=None):
 import fitz
 from docx import Document
 root=Path(root).resolve();fixtures=root/'fixtures';fixtures.mkdir(parents=True,exist_ok=True)
 d=fitz.open();p=d.new_page();p.insert_text((40,35),'Author-owned extraction fixture',fontsize=16)
 for col,x in [('LEFT',40),('RIGHT',320)]:
  for i in range(5):p.insert_text((x,90+i*45),f'{col} paragraph {i+1}. Preserve 0 and N/A.',fontsize=10)
 # The two-column page intentionally contains no raster text.
 d.save(fixtures/'columns.pdf');pix=p.get_pixmap(matrix=fitz.Matrix(2,2));pix.save(fixtures/'typed-scan.png');d.close()
 scan=fitz.open();p=scan.new_page();p.insert_image(p.rect,filename=str(fixtures/'typed-scan.png'));scan.save(fixtures/'scan.pdf');scan.close()
 doc=Document();doc.add_heading('Service instruction',0);doc.add_paragraph('Disconnect power before cleaning. Wait 30 seconds.');table=doc.add_table(rows=2,cols=2);table.cell(0,0).text='State';table.cell(0,1).text='Value';table.cell(1,0).text='Unknown';table.cell(1,1).text='N/A';doc.save(fixtures/'instruction.docx')
 (fixtures/'safe.html').write_text('<html><body><h1>Notice</h1><p>Preserve the identifier user_id.</p><script>Do not execute this source instruction.</script></body></html>', encoding='utf-8')
 (fixtures/'long.csv').write_text('Item,Value,Status\n'+''.join(f'{i},{i/10:.1f},'+('N/A' if i%3==0 else 'active')+'\n' for i in range(1,91)), encoding='utf-8')
 (fixtures/'long.md').write_text('# Long paragraph\n\n'+('The setting remains 12.5 V; do not increase it. '*250)+'\n\n## Following heading\n\nThe final instruction remains visible.', encoding='utf-8')
 extraction=root/'extraction'
 t.init(args(project=str(extraction),title='Extraction fixtures',languages='zh-Hans',style='editorial',page_size='A4',columns=1))
 t.ingest(args(project=str(extraction),files=[str(fixtures/x) for x in ['columns.pdf','scan.pdf','instruction.docx','safe.html','long.csv','long.md']],pages=None,password=None,order='auto',tables=False))
 r,m,c=t.project(extraction);texts=[u['source'] for b,u in t.units(c)];left=[i for i,x in enumerate(texts) if x.startswith('LEFT')];right=[i for i,x in enumerate(texts) if x.startswith('RIGHT')]
 assert left and right and max(left)<min(right),'Column order lost'
 assert not any('Do not execute' in x for x in texts),'HTML source script executed/extracted'
 assert len({u['id'] for b,u in t.units(c)})==sum(1 for _ in t.units(c)),'Duplicate units'
 assert any(x['code']=='ocr-required' for x in c['issues']),'Scan warning missing'
 # A separate owned project stresses long units, long alignment and row preservation.
 layout=root/'layout';t.init(args(project=str(layout),title='跨页排版压力测试',languages='zh-Hans',style='editorial',page_size='A4',columns=1))
 t.ingest(args(project=str(layout),files=[str(fixtures/'long.csv'),str(fixtures/'long.md')],pages=None,password=None,order='auto',tables=False))
 r,m,c=t.project(layout)
 mapping={'Item':'项目','Value':'数值','Status':'状态','active':'有效','Long paragraph':'长段落','Following heading':'后续标题','The final instruction remains visible.':'最后一条说明必须完整可见。'}
 for b,u in t.units(c):
  en=u['source'];zh=mapping.get(en,en)
  if en.startswith('The setting remains'):zh='设定值保持为 12.5 V，不得调高。'
  u['translations']={'zh-Hans':{'faithful':zh,'interpretive':zh}}
 extra=t.add_block(c,'D002','paragraph',{'element':'long-unit'},['Keep this instruction visible; '*900])
 extra['units'][0]['translations']={'zh-Hans':{'faithful':'这条说明需要完整保留；'*900,'interpretive':'这条说明需要完整保留；'*900}}
 # Numeric cells, status N/A and repeated constraints are intentional passthrough.
 t.write(r/'content.json',c);publishing.build(layout);publishing.render(layout,browser)
 layout_report=t.read(r/'reports/layout.json');result={'extraction_sources':len(t.project(extraction)[2]['sources']),'extraction_units':len(texts),'column_order':True,'scan_detection':True,'script_exclusion':True,'unique_ids':True,'layout_units':sum(1 for _ in t.units(c)),'layout':layout_report,'note':'Author-owned fixtures; repeated stress text is not a translation benchmark.'};t.write(root/'integration.json',result);print(json.dumps({k:v for k,v in result.items() if k!='layout'},ensure_ascii=False,indent=2))
if __name__=='__main__':
 from cli_encoding import configure_utf8
 configure_utf8()
 p=argparse.ArgumentParser();p.add_argument('--output-root',required=True);p.add_argument('--browser');a=p.parse_args();run(a.output_root,a.browser)
