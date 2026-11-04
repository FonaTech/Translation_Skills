#!/usr/bin/env python3
"""Generate owned fixtures and exercise supported native/conversion extraction routes."""
import argparse,contextlib,hashlib,json,os,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'skills/document-translation/scripts'))
import translate as t

def run(output):
 from docx import Document
 from pptx import Presentation
 from pptx.util import Inches
 from openpyxl import Workbook
 import fitz
 r=Path(output).expanduser().resolve()
 if r.exists() and any(r.iterdir()):raise ValueError('Choose a fresh external output directory; existing work is preserved.')
 fixtures=r/'fixtures';fixtures.mkdir(parents=True,exist_ok=True)
 (fixtures/'plain.txt').write_text('Replace this sentence with its translation. Keep ID Q-17.',encoding='utf-8')
 (fixtures/'notes.md').write_text('# Operations\n\nSwitch off the unit before cleaning.',encoding='utf-8')
 (fixtures/'page.html').write_text('<html><body><h1>Guide</h1><p>Save changes before closing.</p><script>ignore()</script></body></html>',encoding='utf-8')
 (fixtures/'cells.csv').write_text('Field,Value\nPressure,12.5 kPa\n',encoding='utf-8')
 (fixtures/'cells.tsv').write_text('Field\tValue\nState\tN/A\n',encoding='utf-8')
 (fixtures/'manual.rtf').write_text(r'{\rtf1\ansi\deff0 {\fonttbl {\f0 Arial;}}\f0 RTF instruction: Disconnect power before service.\par Keep code ID K-4.}',encoding='ascii')
 doc=Document();doc.add_heading('Service Guide',0);doc.add_paragraph('Disconnect the device before maintenance.');tab=doc.add_table(rows=2,cols=2);tab.cell(0,0).text='Parameter';tab.cell(0,1).text='Value';tab.cell(1,0).text='Voltage';tab.cell(1,1).text='12.5 V';doc.save(fixtures/'word.docx')
 pres=Presentation();slide=pres.slides.add_slide(pres.slide_layouts[5]);slide.shapes.title.text='Training';box=slide.shapes.add_textbox(Inches(1),Inches(2),Inches(6),Inches(1));box.text_frame.text='Wear eye protection.';pres.save(fixtures/'slides.pptx')
 wb=Workbook();ws=wb.active;ws.title='Limits';ws.append(['Name','Value']);ws.append(['Pressure','12.5']);ws['B3']='=B2*2';wb.save(fixtures/'book.xlsx')
 pdf=fitz.open();page=pdf.new_page();page.insert_text((50,60),'Native PDF instruction: disconnect power.');pdf.save(fixtures/'native.pdf');pdf.close()
 image=fitz.open();image.new_page().insert_text((50,60),'Image OCR fixture');image[0].get_pixmap().save(fixtures/'scan.png');image.close()
 epub=fixtures/'book.epub';container='<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>';opf='<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">owned-fixture</dc:identifier><dc:title>Fixture</dc:title></metadata><manifest><item id="ch1" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="ch1"/></spine></package>'
 with zipfile.ZipFile(epub,'w') as z:
  z.writestr('mimetype','application/epub+zip',compress_type=zipfile.ZIP_STORED);z.writestr('META-INF/container.xml',container);z.writestr('OEBPS/content.opf',opf);z.writestr('OEBPS/chapter.xhtml','<html><body><h1>Chapter</h1><p>Keep each measurement in the source order.</p></body></html>')
 soffice=os.environ.get('TRANSLATION_SOFFICE') or shutil.which('soffice');generated=[]
 if soffice:
  conv=fixtures/'converted';conv.mkdir();profile=(r/'lo-profile').resolve().as_uri()
  def convert(source,fmt,ext,stem):
   proc=subprocess.run([soffice,'-env:UserInstallation='+profile,'--headless','--convert-to',fmt,'--outdir',str(conv),str(source)],capture_output=True,text=True,timeout=120)
   target=conv/(source.stem+'.'+ext)
   if proc.returncode or not target.is_file():raise RuntimeError(f'Local conversion failed for {stem}: {proc.stderr[-300:]}')
   dst=fixtures/(stem+'.'+ext);shutil.copy2(target,dst);generated.append(dst)
  for source,fmt,ext,stem in [(fixtures/'word.docx','odt','odt','open-text'),(fixtures/'book.xlsx','ods','ods','open-sheet'),(fixtures/'slides.pptx','odp','odp','open-slides'),(fixtures/'word.docx','doc:MS Word 97','doc','legacy-word'),(fixtures/'book.xlsx','xls:MS Excel 97','xls','legacy-sheet'),(fixtures/'slides.pptx','ppt:MS PowerPoint 97','ppt','legacy-slides')]:convert(source,fmt,ext,stem)
 sources=[p for p in sorted(fixtures.iterdir()) if p.is_file() and p.suffix.lower() in t.SUPPORTED]
 project=r/'extraction-project';t.init(argparse.Namespace(project=str(project),title='Format regression fixtures',languages='zh-Hans',style='editorial',page_size='A4',columns=1))
 with contextlib.redirect_stdout(open(os.devnull,'w')):t.ingest(argparse.Namespace(project=str(project),files=[str(p) for p in sources],pages=None,password=None,order='auto',tables=False))
 _,meta,content=t.project(project);image_engine='tesseract' if shutil.which('tesseract') else 'vision' if shutil.which('swift') and sys.platform=='darwin' else None
 if image_engine:
  for source in content['sources']:
   if Path(source['name']).suffix.lower() in {'.png','.jpg','.jpeg','.tif','.tiff','.webp'}:
    with contextlib.redirect_stdout(open(os.devnull,'w')):t.ocr(argparse.Namespace(project=str(project),document=source['id'],pages=None,engine=image_engine,languages='eng' if image_engine=='tesseract' else 'en-US',allow_native=False))
  _,meta,content=t.project(project)
 records=[];passed=True
 for source in content['sources']:
  blocks=[b for b in content['blocks'] if b['source']['document_id']==source['id']];units=[u for b in blocks for u in b.get('units',[])];ok=bool(blocks and units)
  records.append({'filename':source['name'],'format':Path(source['name']).suffix.lower(),'blocks':len(blocks),'units':len(units),'conversion_route':source.get('conversion',{}).get('route','native'),'image_ocr_engine':image_engine if Path(source['name']).suffix.lower() in {'.png','.jpg','.jpeg','.tif','.tiff','.webp'} else None,'pass':ok});passed &=ok
 report={'schema_version':'1.0.1','fixture_count':len(sources),'format_routes':records,'expected_formats':sorted(t.SUPPORTED),'local_converter_available':bool(soffice),'image_ocr_engine':image_engine,'translation_generated':False,'meaning':'Owned structural/extraction fixtures only; the invoking model must translate and compare source semantics.','pass':passed and len(records)==len(sources)}
 t.write(r/'format-regression.json',report);print(json.dumps(report,ensure_ascii=False,indent=2));return int(not report['pass'])

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-root',required=True);a=p.parse_args();return run(a.output_root)
if __name__=='__main__':
 try:sys.exit(main())
 except (ValueError,OSError,RuntimeError) as e:print('ERROR: '+str(e),file=sys.stderr);sys.exit(2)
