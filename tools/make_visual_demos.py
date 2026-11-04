#!/usr/bin/env python3
"""Build owned scan/label-preservation fixtures in an external work directory."""
import argparse,sys,json
from pathlib import Path
R=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(R/'skills/document-translation/scripts'))
import translate as t,publishing

def project(root,title):
 t.init(argparse.Namespace(project=str(root),title=title,languages='zh-Hans',style='editorial',page_size='A4',columns=1));return t.project(root)
def main():
 import fitz
 from PIL import Image,ImageDraw,ImageFont
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-root',required=True);ap.add_argument('--font',required=True,help='Locally licensed font with Latin and Chinese glyphs');a=ap.parse_args();base=Path(a.output_root).resolve();font=ImageFont.truetype(a.font,33);small=ImageFont.truetype(a.font,25)
 r,m,c=project(base/'figure-demo','图表标注翻译与数据保留示例');points=[(0,20),(10,22),(20,23),(30,26)]
 def draw(lang,path):
  im=Image.new('RGB',(1500,880),'white');d=ImageDraw.Draw(im);d.line([(180,110),(180,700),(1390,700)],fill='#243f52',width=4)
  for x in [0,10,20,30]:
   xx=180+x/30*1150;d.line([(xx,700),(xx,710)],fill='#243f52',width=3);d.text((xx-12,725),str(x),font=small,fill='#243f52')
  for y in [20,22,24,26]:
   yy=700-(y-20)/6*540;d.line([(180,yy),(1330,yy)],fill='#d7e4eb',width=2);d.text((105,yy-14),str(y),font=small,fill='#243f52')
  xy=[(180+x/30*1150,700-(y-20)/6*540) for x,y in points];d.line(xy,fill='#246f93',width=7)
  for x,y in xy:d.ellipse((x-9,y-9,x+9,y+9),fill='#246f93')
  d.text((180,28),'Temperature (°C)' if lang=='en' else '温度（°C）',font=font,fill='#243f52');d.text((600,795),'Time (min)' if lang=='en' else '时间（min）',font=font,fill='#243f52');im.save(path)
 draw('en',r/'assets/source-plot.png');draw('zh',r/'assets/translated-plot.png');en='Temperature increased from 20 to 26 degrees C over 30 minutes; this record does not show the cause.'
 pdf=fitz.open();pg=pdf.new_page();pg.insert_text((40,45),'Author-owned measurement record',fontsize=17);pg.insert_image(fitz.Rect(35,95,560,403),filename=str(r/'assets/source-plot.png'));pg.insert_textbox(fitz.Rect(40,450,550,520),en,fontsize=12);pdf.save(r/'sources/record.pdf');pdf.close()
 c['sources']=[{'id':'D001','name':'Author-owned measurement record','file':'sources/record.pdf','sha256':t.sha(r/'sources/record.pdf'),'media_type':'application/pdf','page_count':1,'selection_scope':'figure and complete caption; title represented by project title','rights':'Copyright 2026 Yufeng Zhan; MIT'}]
 b=t.add_block(c,'D001','image',{'page':1,'bbox':[35,95,560,403]},[en],asset='assets/translated-plot.png',width_mm=165,label_policy='translated');b['units'][0]['translations']={'zh-Hans':{'faithful':'温度在 30 分钟内从 20 °C 上升至 26 °C；这一记录没有说明原因。','interpretive':'在这段 30 分钟的记录中，温度由 20 °C 升至 26 °C。记录本身并未说明温度上升的原因。'}}
 c['corrections']=[{'scope':b['id'],'note':'Label-only replacement; source and translated image use the same original points, coordinate mapping and drawing routine.','source_asset':'assets/source-plot.png','label_mapping':{'Temperature (°C)':'温度（°C）','Time (min)':'时间（min）'}}];t.write(r/'assets/data-and-labels.json',{'points':points,'coordinate_mapping':'x=180+t/30*1150; y=700-(temperature-20)/6*540','label_only_change':True});m['author_credit']='Yufeng Zhan · Author-owned plot · MIT';t.write(r/'project.json',m);t.write(r/'content.json',c);publishing.build(r)
 # Typed scan has known ground truth, unlike the historical manuscript failure case.
 r,m,c=project(base/'typed-scan-demo','扫描版操作记录 · 双栏来源重建');pdf=fitz.open();pg=pdf.new_page();pg.insert_text((40,35),'Author-owned extraction fixture',fontsize=16)
 for col,x in [('LEFT',40),('RIGHT',320)]:
  for i in range(1,6):pg.insert_text((x,90+(i-1)*45),f'{col} paragraph {i}. Preserve 0 and N/A.',fontsize=10)
 pix=pg.get_pixmap(matrix=fitz.Matrix(2,2));pix.save(r/'assets/typed-source.png');pdf.close();pdf=fitz.open();pg=pdf.new_page();pg.insert_image(pg.rect,filename=str(r/'assets/typed-source.png'));pdf.save(r/'sources/typed-scan.pdf');pdf.close()
 c['sources']=[{'id':'D001','name':'Author-owned typed two-column scan','file':'sources/typed-scan.pdf','sha256':t.sha(r/'sources/typed-scan.pdf'),'media_type':'application/pdf','page_count':1,'selection_scope':'all visible typed text','rights':'Copyright 2026 Yufeng Zhan; MIT'}]
 texts=['Author-owned extraction fixture']+[f'{col} paragraph {i}. Preserve 0 and N/A.' for col in ['LEFT','RIGHT'] for i in range(1,6)]
 for i,en in enumerate(texts):
  b=t.add_block(c,'D001','heading' if i==0 else 'paragraph',{'page':1,'element':'verified ground-truth transcription reading order'},[en],level=1)
  if i==0:f=it='作者自有提取测试材料'
  else:
   col='左栏' if en.startswith('LEFT') else '右栏';n=en.split()[2].rstrip('.');f=f'{col}第 {n} 段。保留 0 和 N/A。';it=f'{col}第 {n} 段：0 与 N/A 必须原样保留。'
  b['units'][0]['translations']={'zh-Hans':{'faithful':f,'interpretive':it}}
 c['corrections']=[{'scope':'source page 1','reason':'Known ground truth is ordered down the left column then down the right. OCR candidates, if run separately, must be compared before substitution. No OCR is silently asserted by this generator.'}];m['author_credit']='Yufeng Zhan · Author-owned scan · MIT';t.write(r/'project.json',m);t.write(r/'content.json',c);publishing.build(r)
 print('Built two external visual-demo projects; render and inspect before recording review.')
if __name__=='__main__':main()
