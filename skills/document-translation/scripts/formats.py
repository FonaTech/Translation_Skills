"""Read common container formats without executing macros, formulas, links or scripts.
Native layouts are described separately; extraction warnings must be reviewed.
"""
from pathlib import Path
import os,posixpath,re,shutil,subprocess,xml.etree.ElementTree as ET,zipfile
from translate import add_block,split_text,sha,StaticHTML
A='http://schemas.openxmlformats.org/drawingml/2006/main'
P='http://schemas.openxmlformats.org/presentationml/2006/main'
X='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
OD={'o':'urn:oasis:names:tc:opendocument:xmlns:office:1.0','t':'urn:oasis:names:tc:opendocument:xmlns:text:1.0','a':'urn:oasis:names:tc:opendocument:xmlns:table:1.0','d':'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0','s':'urn:oasis:names:tc:opendocument:xmlns:style:1.0','f':'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0'}
def archive(path):
 z=zipfile.ZipFile(path)
 if sum(x.file_size for x in z.infolist())>256_000_000 or len(z.infolist())>20000:raise ValueError('Container exceeds bounded extraction limit; select/conversion required.')
 for x in z.infolist():
  if x.filename.startswith('/') or '..' in Path(x.filename).parts:raise ValueError('Unsafe archive entry')
 return z

def table(c,did,locator,rows,header=1,cellmeta=None):
 b=add_block(c,did,'table',{'element':locator},[],rows=[],header_rows=header)
 for ri,row in enumerate(rows):
  ids=[]
  for ci,t in enumerate(row):
   uid=f'{b["id"]}-R{ri+1:04d}C{ci+1:03d}';u={'id':uid,'source':str(t),'translations':{},'notes':[]}
   if cellmeta and (ri,ci) in cellmeta:u['protected']=cellmeta[(ri,ci)]
   b['units'].append(u);ids.append(uid)
  b['rows'].append(ids)
 return b

def pptx(r,c,did,p,warnings):
 with archive(p) as z:
  root=ET.fromstring(z.read('ppt/presentation.xml'));rels={e.get('Id'):e.get('Target') for e in ET.fromstring(z.read('ppt/_rels/presentation.xml.rels')) if e.get('TargetMode')!='External'}
  order=[posixpath.normpath(posixpath.join('ppt',rels[e.get('{'+R+'}id')])) for e in root.findall('.//{'+P+'}sldId')]
  for pn,name in enumerate(order,1):
   slide=ET.fromstring(z.read(name));ns={'p':P,'a':A}
   for si,sp in enumerate(slide.findall('.//p:spTree/*',ns),1):
    for ti,tab in enumerate(sp.findall('.//a:tbl',ns)):
     rows=[['\n'.join(''.join(e.text or '' for e in par.findall('.//a:t',ns)) for par in cell.findall('a:txBody/a:p',ns)) for cell in row.findall('a:tc',ns)] for row in tab.findall('a:tr',ns)]
     table(c,did,f'slide/{pn}/shape/{si}/table/{ti+1}',rows)
    if sp.find('.//a:tbl',ns) is not None:continue
    ph=sp.find('.//p:ph',ns);heading=ph is not None and ph.get('type') in {'title','ctrTitle'}
    for pi,par in enumerate(sp.findall('.//a:p',ns),1):
     text=''.join(e.text or '' for e in par.findall('.//a:t',ns))
     if text.strip():add_block(c,did,'heading' if heading else 'paragraph',{'page':pn,'element':f'slide/{pn}/shape/{si}/p/{pi}'},split_text(text),level=1 if heading else 2)
   relname=posixpath.dirname(name)+'/_rels/'+posixpath.basename(name)+'.rels'
   if relname in z.namelist():
    for link in ET.fromstring(z.read(relname)):
     if link.get('TargetMode')=='External':continue
     target=posixpath.normpath(posixpath.join(posixpath.dirname(name),link.get('Target','')))
     if target not in z.namelist():continue
     if link.get('Type','').endswith('/image'):
      ext=Path(target).suffix.lower()
      if ext in {'.png','.jpg','.jpeg','.gif','.webp'}:
       dest=r/'assets'/f'{did}-slide{pn}-{Path(target).name}';dest.write_bytes(z.read(target));add_block(c,did,'image',{'page':pn,'element':target},[],asset=dest.relative_to(r).as_posix(),width_mm=130,label_policy='unreviewed')
     if link.get('Type','').endswith('/notesSlide'):
      for ni,sp in enumerate(ET.fromstring(z.read(target)).findall('.//p:sp',ns)):
       ph=sp.find('.//p:ph',ns)
       if ph is not None and ph.get('type') in {'sldNum','hdr','ftr','dt','sldImg'}:continue
       text='\n'.join(''.join(x.text or '' for x in par.findall('.//a:t',ns)) for par in sp.findall('.//a:p',ns))
       if text.strip():add_block(c,did,'paragraph',{'page':pn,'element':f'slide/{pn}/notes/{ni+1}'},split_text(text))
  next(s for s in c['sources'] if s['id']==did)['page_count']=len(order)
 warnings.append({'code':'pptx-native-review','message':'Slide text, tables, notes and raster media extracted. Verify grouped shape order, charts, equations, SmartArt and visible media labels against slides; animations are not reproduced.'})

def xlsx(r,c,did,p,warnings):
 with archive(p) as z:
  ns={'x':X};shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():shared=[''.join(t.text or '' for t in e.findall('.//x:t',ns)) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('x:si',ns)]
  rels={e.get('Id'):e.get('Target') for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')) if e.get('TargetMode')!='External'}
  book=ET.fromstring(z.read('xl/workbook.xml'))
  for sn,sheet in enumerate(book.findall('x:sheets/x:sheet',ns),1):
   name=sheet.get('name','Sheet');target=rels.get(sheet.get('{'+R+'}id'),'');target=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('xl',target))
   sh=ET.fromstring(z.read(target));add_block(c,did,'heading',{'element':f'sheet/{sn}/name'},[name],level=1)
   rows=[];meta={};total=0
   for row in sh.findall('x:sheetData/x:row',ns):
    cells=row.findall('x:c',ns)
    if not cells:continue
    vals=[]
    for cell in cells:
     addr=cell.get('r','');m=re.match('([A-Z]+)',addr);col=0
     if m:
      for ch in m[1]:col=col*26+ord(ch)-64
     if col>256:raise ValueError('Spreadsheet extends beyond 256 columns; select a bounded region explicitly.')
     while len(vals)<max(0,col-1):vals.append('')
     typ=cell.get('t');v=cell.find('x:v',ns);f=cell.find('x:f',ns);raw=v.text if v is not None and v.text is not None else ''
     if f is not None:value='='+str(f.text or '');protect={'kind':'formula','cell':addr,'cached_value':raw,'execution':'never executed'}
     elif typ=='s':value=shared[int(raw)];protect=None
     elif typ=='inlineStr':value=''.join(e.text or '' for e in cell.findall('.//x:t',ns));protect=None
     elif typ=='b':value=raw;protect={'kind':'boolean','cell':addr}
     elif typ=='e':value=raw;protect={'kind':'source-error','cell':addr}
     else:value=raw;protect={'kind':'numeric-or-date-serial','cell':addr,'style_index':cell.get('s')} if typ not in {'str'} else None
     ci=len(vals);vals.append(value)
     if protect:meta[(len(rows),ci)]=protect
    rows.append(vals);total+=len(vals)
    if total>100000:raise ValueError('Spreadsheet exceeds 100000 selected cells; select a bounded region.')
   width=max(map(len,rows),default=0);rows=[row+['']*(width-len(row)) for row in rows]
   if rows:table(c,did,f'sheet/{sn}/{name}',rows,0,meta)
   for merge in sh.findall('x:mergeCells/x:mergeCell',ns):warnings.append({'code':'xlsx-merged-cell','message':f'Sheet {sn}: merged range {merge.get("ref")}; first cell retained, visual span needs review.'})
   if sheet.get('state') in {'hidden','veryHidden'}:warnings.append({'code':'hidden-sheet','message':f'Sheet {sn} is hidden in source; extracted and explicitly requires inclusion decision.'})
 warnings.append({'code':'xlsx-review','message':'Text and numeric/formula source tokens extracted by sheet. Formulas are protected text, never evaluated; dates use source serial/style metadata. Charts, comments, drawings, headers and print areas require review. Output is a translated reading edition, not a recalculated workbook.'})

def od_text(e):
 out=[]
 def visit(x):
  if x.text:out.append(x.text)
  for ch in x:
   if ch.tag=='{'+OD['t']+'}s':out.append(' '*min(int(ch.get('{'+OD['t']+'}c','1')),10000))
   elif ch.tag=='{'+OD['t']+'}tab':out.append('\t')
   elif ch.tag=='{'+OD['t']+'}line-break':out.append('\n')
   else:visit(ch)
   if ch.tail:out.append(ch.tail)
 visit(e);return ''.join(out)

def odf(r,c,did,p,warnings):
 with archive(p) as z:
  root=ET.fromstring(z.read('content.xml'));body=root.find('o:body',OD)
  def walk(el,path):
   local=el.tag.split('}')[-1]
   if el.tag=='{'+OD['a']+'}table':
    rows=[]
    for row in el.findall('.//a:table-row',OD):
     nr=min(int(row.get('{'+OD['a']+'}number-rows-repeated','1')),10001);vals=[]
     for cell in row:
      if cell.tag not in {'{'+OD['a']+'}table-cell','{'+OD['a']+'}covered-table-cell'}:continue
      nt=min(int(cell.get('{'+OD['a']+'}number-columns-repeated','1')),257);t='\n'.join(od_text(x) for x in cell.findall('t:p',OD));formula=cell.get('{'+OD['a']+'}formula');val=t if t else cell.get('{'+OD['o']+'}value',cell.get('{'+OD['o']+'}string-value',''))
      if formula:val=formula
      if nt>256 and val:raise ValueError('ODF repeated nonempty columns exceed bounded extraction')
      if nt<=256:vals.extend([val]*nt)
     if nr>10000 and any(vals):raise ValueError('ODF repeated nonempty rows exceed bounded extraction')
     if any(vals):rows.extend([list(vals) for _ in range(nr)])
     if len(rows)>10000:raise ValueError('ODF table exceeds row limit')
    if rows:table(c,did,path,rows,0)
    return
   if el.tag in {'{'+OD['t']+'}p','{'+OD['t']+'}h'}:
    text=od_text(el)
    if text.strip():add_block(c,did,'heading' if local=='h' else 'paragraph',{'element':path},split_text(text),level=int(el.get('{'+OD['t']+'}outline-level','2')))
    return
   for i,ch in enumerate(el):walk(ch,path+'/'+ch.tag.split('}')[-1]+str(i+1))
  walk(body,'body')
  for name in z.namelist():
   if name.startswith('Pictures/') and Path(name).suffix.lower() in {'.png','.jpg','.jpeg','.gif','.webp'}:
    dst=r/'assets'/f'{did}-{Path(name).name}';dst.write_bytes(z.read(name));add_block(c,did,'image',{'element':name},[],asset=dst.relative_to(r).as_posix(),label_policy='unreviewed',width_mm=140)
 warnings.append({'code':'odf-review','message':'ODF text, tables and raster media extracted; repeated cells bounded. Check footnotes, lists, merged cells, embedded objects, formula tokens and image anchors against native source.'})

def epub(r,c,did,p,warnings):
 with archive(p) as z:
  container=ET.fromstring(z.read('META-INF/container.xml'));opf=next(e.get('full-path') for e in container.iter() if e.tag.endswith('}rootfile'));root=ET.fromstring(z.read(opf));manifest={e.get('id'):e.get('href') for e in root.iter() if e.tag.endswith('}item')};spine=[e.get('idref') for e in root.iter() if e.tag.endswith('}itemref')]
  for ci,ref in enumerate(spine,1):
   target=posixpath.normpath(posixpath.join(posixpath.dirname(opf),manifest[ref].split('#')[0]));parser=StaticHTML();parser.feed(z.read(target).decode('utf-8-sig'));parser.flush()
   for i,(typ,t,lev) in enumerate(parser.blocks,1):add_block(c,did,typ,{'element':f'spine/{ci}/{target}/block/{i}'},split_text(t),level=lev)
 warnings.append({'code':'epub-review','message':'Spine-order XHTML text extracted without running scripts. Navigation, images, SVG, notes and out-of-spine resources require explicit source review.'})

def convert(r,c,did,p,warnings):
 ext=p.suffix.lower();dest=r/'sources'/f'{did}-conversion';dest.mkdir(exist_ok=True)
 if ext=='.rtf' and shutil.which('textutil'):
  target=dest/(p.stem+'.docx');subprocess.run(['textutil','-convert','docx','-output',str(target),str(p)],check=True,capture_output=True,timeout=90)
 else:
  binary=os.environ.get('TRANSLATION_SOFFICE') or shutil.which('soffice')
  if not binary:raise ValueError('Legacy format needs local LibreOffice/soffice; do not claim native support without conversion.')
  fmt={'.rtf':'docx','.doc':'docx','.ppt':'pptx','.xls':'xlsx'}[ext];target=dest/(p.stem+'.'+fmt)
  profile=(dest/'lo-profile').resolve().as_uri();subprocess.run([binary,'-env:UserInstallation='+profile,'--headless','--convert-to',fmt,'--outdir',str(dest),str(p)],check=True,capture_output=True,timeout=120)
 if not target.is_file():raise ValueError('Conversion did not create expected intermediate')
 source=next(s for s in c['sources'] if s['id']==did);source['conversion']={'file':target.relative_to(r).as_posix(),'sha256':sha(target),'route':'local conversion','original_sha256':sha(p)}
 if target.suffix=='.docx':
  ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
  with archive(target) as z:
   root=ET.fromstring(z.read('word/document.xml'))
   for i,e in enumerate(root.find('w:body',ns),1):
    if e.tag.endswith('}tbl'):
     rows=[[' '.join(x.text or '' for x in cell.findall('.//w:t',ns)) for cell in row.findall('w:tc',ns)] for row in e.findall('w:tr',ns)];table(c,did,f'converted/body/{i}',rows)
    elif e.tag.endswith('}p'):
     text=''.join(x.text or '' for x in e.findall('.//w:t',ns))
     if text.strip():add_block(c,did,'paragraph',{'element':f'converted/body/{i}'},split_text(text))
 else:ingest_format(r,c,did,target,warnings)
 warnings.append({'code':'conversion-review','message':'Local conversion intermediate is hashed. Verify converted text, headers, figures, fields and reading order against original; conversion alone is not completeness proof.'})

def ingest_format(r,c,did,p,warnings):
 ext=p.suffix.lower()
 if ext=='.pptx':pptx(r,c,did,p,warnings)
 elif ext=='.xlsx':xlsx(r,c,did,p,warnings)
 elif ext in {'.odt','.ods','.odp'}:odf(r,c,did,p,warnings)
 elif ext=='.epub':epub(r,c,did,p,warnings)
 else:convert(r,c,did,p,warnings)
