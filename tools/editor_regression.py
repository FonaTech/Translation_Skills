#!/usr/bin/env python3
"""Behavior checks for source-style precedence and actual rendered geometry."""
from pathlib import Path
import argparse
import json
import os
import zipfile
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
EDITOR = ROOT / 'skills/document-translation/assets/document-layout-editor.html'


def run(output, browser=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = {'checks': [], 'errors': [], 'pass': False}

    def check(name, value, detail=None):
        result['checks'].append({'name': name, 'pass': bool(value), 'detail': detail})
        if not value:
            result['errors'].append(name)

    fixture = '''<!doctype html><html><head><style>
    [data-layout-doc="D001"]{--page-width:210mm!important;--page-height:297mm!important;--body-size:16pt!important;--body-leading:1.9;--column-count:2;--column-gap:7mm;width:210mm;padding:20mm}
    [data-layout-doc="D001"] .prose{font-size:16pt;line-height:1.9;margin-bottom:9mm}
    [data-layout-doc="D001"] td{padding:7mm;font-size:14pt}
    .flowcols{column-count:2;column-gap:7mm}.prose{color:#213a46}
    </style></head><body><main class="reader"><section class="layout-document" data-layout-doc="D001" style="--body-size:16pt!important;--page-width:210mm!important">
    <h1>版式参数验证 / Layout control verification</h1><div class="flowcols">''' + ''.join(
        '<p class="prose" data-uid="u' + str(i) + '">' +
        ('A measured paragraph must retain its meaning. 这里核对字号、行距、边距和分页是否真正变化。 ' * 3) + '</p>'
        for i in range(10)) + '''</div><table><colgroup><col style="width:25%"><col style="width:75%"></colgroup><caption>表题必须保留 / Caption must survive</caption><thead><tr><th>Item</th><th>Value</th></tr></thead><tbody><tr><td>保留数值</td><td>12.5 V</td></tr></tbody></table><figure><img style="width:25mm;height:15mm" alt="original fixture" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"><figcaption>图注文字 / Figure caption</figcaption></figure></section></main></body></html>'''
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True, **({'executable_path': browser} if browser else {}))
        pg = br.new_page(viewport={'width': 1540, 'height': 1050}, accept_downloads=True)
        page_errors = []
        pg.on('pageerror', lambda e: page_errors.append(str(e)))
        pg.goto(EDITOR.as_uri())
        pg.wait_for_function('()=>window.studioReady', timeout=30000)
        pg.evaluate('(html)=>Studio.importHTML(html,"Cascade regression")', fixture)
        settings = {'pageW': '216', 'pageH': '279', 'marginX': '15', 'marginY': '17', 'columns': '2', 'columnGap': '10', 'bodySize': '12', 'bodyLeading': '1.55', 'paraGap': '2', 'headingGap': '4', 'tableSize': '9', 'cellPadding': '1.5', 'documentFont': 'mono', 'titleSize': '24', 'captionSize': '7.5'}
        for key, value in settings.items():
            if key in {'columns', 'documentFont'}:
                pg.locator('#' + key).select_option(value)
            else:
                pg.locator('#' + key).fill(value)
        pg.locator('#applyLayout').click()
        pg.wait_for_function('()=>Math.abs(Studio.state.sections[0].design.w-216)<.01')
        pg.wait_for_function('()=>document.getElementById("documentFrame").contentDocument.querySelector(".ed-root")')

        def measure(preview=False):
            return pg.evaluate('''(preview)=>{let d=document.getElementById('documentFrame').contentDocument,r=d.querySelector(preview?'.ed-page':'[data-studio-section]'),p=r.querySelector('.prose'),t=d.querySelector(preview?'#edPages td':'.ed-root td'),h=r.querySelector('h1'),cap=d.querySelector(preview?'#edPages figcaption':'.ed-root figcaption');let cs=x=>d.defaultView.getComputedStyle(x);return {width:r.getBoundingClientRect().width,height:r.getBoundingClientRect().height,padding:parseFloat(cs(r).paddingLeft),size:parseFloat(cs(p).fontSize),font:cs(p).fontFamily,leading:parseFloat(cs(p).lineHeight),para:parseFloat(cs(p).marginBottom),columns:cs(r).getPropertyValue('--column-count').trim(),gap:parseFloat(cs(r).getPropertyValue('--column-gap')),title:h?parseFloat(cs(h).fontSize):null,table:t?parseFloat(cs(t).fontSize):null,cell:t?parseFloat(cs(t).paddingLeft):null,caption:cap?parseFloat(cs(cap).fontSize):null}}''', preview)

        edit = measure()
        check('page width beats source CSS', abs(edit['width'] - 216 * 96 / 25.4) < 1, edit)
        check('body size beats imported selector', abs(edit['size'] - 16) < .1, edit)
        check('document monospace font beats source selector', 'monospace' in edit['font'] and 'Courier New' in edit['font'], edit)
        check('line height applied', abs(edit['leading'] - 24.8) < .2, edit)
        check('paragraph gap applied', abs(edit['para'] - 2 * 96 / 25.4) < .2, edit)
        check('page margin applied', abs(edit['padding'] - 15 * 96 / 25.4) < .2, edit)
        check('title applied', abs(edit['title'] - 32) < .2, edit)
        check('table size applied', abs(edit['table'] - 12) < .2, edit)
        check('cell padding applied', abs(edit['cell'] - 1.5 * 96 / 25.4) < .2, edit)
        check('caption size applied', abs(edit['caption'] - 10) < .2, edit)
        report = pg.evaluate('Studio.preview()')
        preview = measure(True)
        columns = pg.evaluate('''()=>{const d=document.getElementById('documentFrame').contentDocument,t=d.querySelector('#edPages table'),cells=[...t.rows[0].cells].map(c=>c.getBoundingClientRect().width);return {groups:t.querySelectorAll('colgroup').length,ratio:cells[0]/cells.reduce((a,b)=>a+b,0)}}''')
        check('pagination preserves source table column widths', columns['groups']==1 and abs(columns['ratio']-.25)<.02, columns)
        check('preview text preserved', report['textPreserved'], report)
        check('preview geometry valid', report['pass'], report)
        check('real table count available to model', sum(p.get('tables', 0) for p in report['pages']) == 1, report)
        check('real image count preserved', sum(p['images'] for p in report['pages']) == 1, report)
        check('preview dimensions applied', abs(preview['width'] - 216 * 96 / 25.4) < 1 and abs(preview['height'] - 279 * 96 / 25.4) < 1, preview)
        check('preview preserves document monospace font', 'monospace' in preview['font'], preview)
        check('preview typography applied', abs(preview['size'] - 16) < .1, preview)
        gap = pg.evaluate("(()=>{let d=document.getElementById('documentFrame').contentDocument,b=d.querySelector('.ed-band');return {gap:parseFloat(d.defaultView.getComputedStyle(b).columnGap),count:d.defaultView.getComputedStyle(b).columnCount,grid:d.defaultView.getComputedStyle(b).gridTemplateColumns}})()")
        check('preview column gap applied', abs(gap['gap'] - 10 * 96 / 25.4) < 1, gap)
        # Applying controls while already in preview must preserve the typed values.
        pg.locator('#cellPadding').fill('0')
        pg.locator('#paraGap').fill('0')
        pg.locator('#applyLayout').click()
        pg.wait_for_function('()=>Studio.state.sections[0].design.cellPad===0 && Studio.state.sections[0].design.para===0')
        pg.wait_for_function('()=>document.getElementById("documentFrame").contentDocument.querySelector(".ed-root")')
        zero = measure()
        check('preview-mode edits retain entered values', zero['cell'] == 0 and zero['para'] == 0, zero)
        zero_report = pg.evaluate('Studio.preview()')
        check('zero spacing survives preview', measure(True)['cell'] == 0 and measure(True)['para'] == 0, zero_report)
        saved = pg.evaluate('JSON.stringify(Studio.state.sections.map(s=>s.design))')
        source_text = pg.evaluate('Studio.state.sections.map(s=>Studio.sanitize(s.html).body.textContent).join("")')
        pg.evaluate('()=>Studio.optimize()')
        check('manual settings survive ML optimization', saved == pg.evaluate('JSON.stringify(Studio.state.sections.map(s=>s.design))'))
        check('ML optimizer preserves all text', source_text == pg.evaluate('Studio.state.sections.map(s=>Studio.sanitize(s.html).body.textContent).join("")'))
        decision = pg.evaluate('Studio.state.decisions.at(-1)')
        check('actual model participates in ranking', decision.get('model',{}).get('id') == 'dom-ranker-1.0.1', decision)
        check('chosen candidate passes hard constraints', any(c['id'] == decision.get('chosen') and c['safe'] for c in decision['candidates']), decision)
        pg.screenshot(path=str(output / 'editor-optimizer.png'))
        for kind in ['html', 'docx']:
            with pg.expect_download() as info:
                pg.evaluate('(kind)=>Studio.exportFile(kind)', kind)
            info.value.save_as(output / ('cascade-export.' + kind))
            check(kind + ' generated', (output / ('cascade-export.' + kind)).stat().st_size > 1500)
        saved_state = pg.evaluate('JSON.parse(JSON.stringify(Studio.state))')
        exported = br.new_page()
        exported.goto((output / 'cascade-export.html').as_uri())
        exported.wait_for_function('()=>window.studioAssetsReady||window.studioAssetsError')
        pooled = exported.evaluate('''async()=>{await Promise.all([...document.images].map(i=>i.decode()));const pool=JSON.parse(document.querySelector('script[data-studio-image-pool]').textContent);return {assets:pool.length,images:document.images.length,decoded:[...document.images].every(i=>i.naturalWidth>0),unique:new Set(pool).size,text:document.querySelector('.ed-root').textContent}}''')
        check('exported HTML resolves one shared image pool from disk', pooled['decoded'] and pooled['assets']==pooled['unique'] and pooled['images']>pooled['assets'], {k:v for k,v in pooled.items() if k!='text'})
        check('pooled standalone HTML keeps all visible text', pooled['text']==source_text, {'characters':len(pooled['text'])})
        exported.close()
        pg.evaluate('(html)=>Studio.importHTML(html,"Round trip")', (output / 'cascade-export.html').read_text())
        restored = pg.evaluate('JSON.parse(JSON.stringify(Studio.state))')
        check('HTML round trip retains current design', saved_state['sections'][0]['design'] == restored['sections'][0]['design'])
        check('HTML round trip retains manual locks', saved_state['sections'][0].get('locks', {}) == restored['sections'][0].get('locks', {}))
        check('HTML round trip retains source design', saved_state['sections'][0].get('sourceDesign') == restored['sections'][0].get('sourceDesign'))
        check('HTML round trip preserves text', source_text == pg.evaluate('Studio.state.sections.map(s=>Studio.sanitize(s.html).body.textContent).join("")'))
        check('HTML round trip preview valid', pg.evaluate('Studio.preview()')['pass'])
        pool_security = pg.evaluate(r'''()=>{const raster='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',pack=a=>'<script type="application/json" data-studio-image-pool>'+JSON.stringify(a)+'</script><main class="ed-root"><img data-studio-src="0"></main>',result={};for(const [name,data] of [['external',['https://example.invalid/private.png']],['active',['data:image/svg+xml;base64,'+btoa('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')]],['missing',[]]]){try{Studio.sanitize(pack(data));result[name]=false}catch{result[name]=true}}const safe=Studio.sanitize(pack([raster])+'<script>window.poolInjected=true</script>');result.safe=safe.querySelector('img').getAttribute('src')===raster;result.scriptsRemoved=!safe.querySelector('script');return result}''')
        check('image-pool import validates assets and drops input scripts', all(pool_security.values()), pool_security)
        preserved_fallback=pg.evaluate('''async()=>{const uri='data:image/svg+xml;base64,'+btoa('<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><rect width="2" height="2" fill="black"/></svg>'),canvas=document.createElement('canvas');canvas.width=2;canvas.height=2;canvas.getContext('2d').fillRect(0,0,2,2);const fallback=canvas.toDataURL('image/png'),root=document.createElement('div'),img=new Image();img.src=uri;img.dataset.rasterFallback=fallback;root.append(img);document.body.append(root);await VectorImages.prepare([root]);await VectorImages.prepare([root]);const same=img.src===uri&&img.dataset.rasterFallback===fallback;root.remove();return same}''')
        check('repeated vector preparation retains source fallback bytes',preserved_fallback)
        ns = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        w = '{' + ns['w'] + '}'
        with zipfile.ZipFile(output / 'cascade-export.docx') as z:
            check('DOCX archive CRC valid', z.testzip() is None)
            doc = ET.fromstring(z.read('word/document.xml'))
            check('DOCX table caption retained', '表题必须保留 / Caption must survive' in ''.join(doc.itertext()))
            page_size = doc.find('.//w:pgSz',ns)
            check('DOCX actual page dimensions', abs(int(page_size.get(w+'w'))-216*56.693)<1 and abs(int(page_size.get(w+'h'))-279*56.693)<1)
            paragraphs = doc.findall('.//w:p',ns)
            prose = next(p for p in paragraphs if 'A measured paragraph' in ''.join(p.itertext()))
            check('DOCX body size follows computed CSS', all(x.get(w+'val')=='24' for x in prose.findall('.//w:sz',ns)))
            check('DOCX uses selected document font', all(x.get(w+'ascii')=='Noto Sans Mono' for x in prose.findall('.//w:rFonts',ns)))
            spacing = prose.find('w:pPr/w:spacing',ns)
            check('DOCX line spacing and zero paragraph gap', spacing.get(w+'line')=='372' and spacing.get(w+'after')=='0',spacing.attrib)
            title = next(p for p in paragraphs if 'Layout control verification' in ''.join(p.itertext()))
            check('DOCX title size follows computed CSS', all(x.get(w+'val')=='48' for x in title.findall('.//w:sz',ns)))
            cell = doc.find('.//w:tc',ns)
            check('DOCX table size and padding follow computed CSS', all(x.get(w+'val')=='18' for x in cell.findall('.//w:sz',ns)) and all(x.get(w+'w')=='0' for x in cell.findall('.//w:tcMar/*',ns)))
            check('DOCX original raster image retained', len([n for n in z.namelist() if n.startswith('word/media/')])==1)
        pg.evaluate('Studio.optimize()')
        check('optimizer respects manually selected document font', pg.evaluate("Studio.state.sections[0].design.font==='mono' && Studio.state.sections[0].locks.font===true"))
        check('optimized pages retain monospace font', 'monospace' in measure(True)['font'])
        pg.evaluate('Studio.render()')
        pg.locator('#documentFont').select_option('sans')
        pg.locator('#applyLayout').click()
        pg.wait_for_function("()=>Studio.state.sections[0].design.font==='sans' && document.getElementById('documentFrame').contentDocument.querySelector('.ed-root .prose')")
        check('manual sans family visibly changes body', 'sans-serif' in measure()['font'] and 'Courier New' not in measure()['font'], measure())
        target = pg.frame_locator('#documentFrame').locator('.prose').first
        target.click()
        pg.keyboard.press('Home')
        pg.locator('#fontSize').fill('18')
        pg.locator('#sizeApply').click()
        check('local paragraph font overrides global control', abs(measure()['size']-24)<.1, measure())
        pg.locator('[data-tab=layout]').click()
        pg.locator('#paragraphLeading').fill('1.8')
        pg.locator('#paragraphGap').fill('4')
        pg.locator('#paragraphApply').click()
        local = measure()
        check('local paragraph leading and gap override global control', abs(local['leading']-43.2)<.2 and abs(local['para']-4*96/25.4)<.2, local)
        pg.evaluate('Studio.preview()')
        check('local paragraph edits survive pagination', abs(measure(True)['size']-24)<.1 and abs(measure(True)['para']-4*96/25.4)<.2, measure(True))
        pg.evaluate('Studio.render()')
        for zoom in ['.65', '.8', '1', '1.25']:
            pg.locator('#zoom').select_option(zoom)
            target = pg.frame_locator('#documentFrame').locator('.prose').nth(3)
            target.scroll_into_view_if_needed()
            target.click()
            pg.keyboard.press('Home')
            pg.keyboard.insert_text('Z' + zoom + ' ')
            check('text edit at zoom ' + zoom, 'Z' + zoom in pg.evaluate("document.getElementById('documentFrame').contentDocument.querySelectorAll('.prose')[3].textContent"))
        check('no browser errors', not page_errors, page_errors)
        pg.screenshot(path=str(output / 'editor-controls.png'))
        # Short paragraphs distinguish explicit boundaries from incidental overflow.
        section = pg.evaluate('({...Studio.state.sections[0],design:Studio.defaultDesign(),overrides:{},locks:{},sourceClass:"",sourceAttrs:{},sourceStyle:""})')
        section['html'] = '<p data-source-page="1" data-uid="one">First source page.</p><p data-source-page="2" data-uid="two">Second continuous source page.</p>'
        pg.evaluate('(s)=>Studio.loadState({title:"Boundaries",sourceCSS:"",sections:[s]})', section)
        boundary = pg.evaluate('Studio.preview()')
        check('continuous source pages reflow', len(boundary['pages']) == 1 and boundary['pages'][0]['source_pages'] == ['1', '2'], boundary)
        section['html'] = section['html'].replace('data-source-page="2"', 'data-source-page="8"')
        pg.evaluate('(s)=>Studio.loadState({title:"Boundaries",sourceCSS:"",sections:[s]})', section)
        boundary = pg.evaluate('Studio.preview()')
        check('noncontiguous source pages retain boundary', len(boundary['pages']) == 2, boundary)
        section['html'] = section['html'].replace('data-source-page="8"', 'data-source-page="2"')
        section['preserveSourcePageBreaks'] = True
        pg.evaluate('(s)=>Studio.loadState({title:"Boundaries",sourceCSS:"",sections:[s]})', section)
        boundary = pg.evaluate('Studio.preview()')
        check('explicit source page breaks honored', len(boundary['pages']) == 2, boundary)
        # A full-width alignment row can leave only a narrow strip below it.
        # The next column figure must use a fresh page before any resizing.
        figure_section = dict(section)
        figure_section.pop('preserveSourcePageBreaks', None)
        figure_section['alignmentLabels'] = ['Source', 'Faithful', 'Interpretive']
        figure_section['design'] = {**section['design'], 'cols': 2}
        figure_section['html'] = '<div class="pair" data-block="row" style="height:175mm"><p data-uid="aligned">Owned alignment row.</p></div><figure data-span="column" data-block="tall-figure"><img alt="Owned tall figure" style="width:50mm;height:80mm;object-fit:contain" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"><figcaption>Keep this caption with its figure.</figcaption></figure>'
        pg.evaluate('(s)=>Studio.loadState({title:"Partial page figure",sourceCSS:"",sections:[s]})', figure_section)
        figure_report = pg.evaluate('Studio.preview()')
        figure_geometry = pg.evaluate('''()=>{const d=document.getElementById('documentFrame').contentDocument,pages=[...d.querySelectorAll('#edPages>.ed-page')],image=d.querySelector('#edPages figure img');return {page:pages.indexOf(image.closest('.ed-page'))+1,height:image.getBoundingClientRect().height,width:image.getBoundingClientRect().width}}''')
        check('figure below alignment row uses fresh page before shrinking', figure_report['pass'] and figure_geometry['page'] == 2 and abs(figure_geometry['height']-80*96/25.4)<1 and abs(figure_geometry['width']-50*96/25.4)<1, {'geometry': figure_geometry, 'report': figure_report})
        # Translated article titles are h2, while the editor demo uses h1.
        pg.evaluate('(html)=>Studio.importHTML(html,"Article title")', '<main><h2 data-title="true">Original article title</h2><p>Original body.</p></main>')
        pg.locator('#titleSize').fill('28')
        pg.locator('#accent').fill('#923456')
        pg.locator('#headerText').fill('Review header')
        pg.locator('#footerText').fill('Review footer')
        pg.locator('#applyLayout').click()
        pg.wait_for_function('()=>Studio.state.sections[0].design.titleSize===28')
        pg.wait_for_function('()=>document.getElementById("documentFrame").contentDocument.querySelector("[data-title]")')
        title_metrics = pg.evaluate('''()=>{const d=document.getElementById('documentFrame').contentDocument,h=d.querySelector('[data-title]'),cs=d.defaultView.getComputedStyle(h);return {size:parseFloat(cs.fontSize),color:cs.color}}''')
        check('actual article title control applied', abs(title_metrics['size'] - 28*96/72) < .2, title_metrics)
        check('manual theme color overrides source', title_metrics['color'] == 'rgb(146, 52, 86)', title_metrics)
        pg.evaluate('Studio.preview()')
        chrome = pg.evaluate('''()=>{const d=document.getElementById('documentFrame').contentDocument;return {header:d.querySelector('.ed-page-header').textContent,footer:d.querySelector('.ed-page-footer').textContent}}''')
        check('manual header and footer reach print pages', 'Review header' in chrome['header'] and 'Review footer' in chrome['footer'], chrome)
        check('candidate search includes 24 distinct settings', pg.evaluate('LayoutAssist.candidates([{design:Studio.defaultDesign()}]).length') == 24)
        model_data=json.loads((ROOT/'skills/document-translation/assets/models/dom-ranker.json').read_text())
        check('model has actual 24-feature network', model_data['architecture']==[24,12,1] and any(abs(v)>0.01 for row in model_data['weights'] for v in row))
        inside=pg.evaluate('(x)=>LayoutModel.predict(x)',model_data['mean'])
        check('in-envelope inference returns finite score', isinstance(inside.get('score'),(int,float)),inside)
        outside=list(model_data['mean']);outside[15]=2
        rejected=pg.evaluate('(x)=>LayoutModel.predict(x)',outside)
        check('out-of-envelope inputs decline learned score', rejected.get('score') is None and rejected.get('reason')=='outside-training-envelope',rejected)
        invalid=pg.evaluate('()=>LayoutModel.predict([NaN])')
        check('invalid features decline learned score',invalid.get('score') is None and invalid.get('reason')=='invalid-features',invalid)
        mixed=pg.evaluate('''()=>{const x=Array(24).fill(0);x[5]=.78;x[7]=.78;return LayoutAssist.rank([{id:'learned',safe:true,model:'dom-ranker-1.0.1',score:200,features:x,changed:0},{id:'fallback',safe:true,model:'deterministic-rule-fallback',score:-300,features:x,changed:1}]);}''')
        check('mixed inference compares one common score scale',mixed[0]['score']==mixed[1]['score'] and all(c['model']=='deterministic-rule-fallback' for c in mixed),mixed)
        # Run planner without the model in a fresh realm: no fake replacement.
        no_model=br.new_page()
        no_model.add_script_tag(content=(ROOT/'skills/document-translation/assets/layout-planner.js').read_text())
        fallback=no_model.evaluate('''()=>{const sections=[{design:{size:11,leading:1.7,para:3,head:5,w:210,mx:20,cols:1,gap:7,titleSize:20,captionSize:8,tableSize:8,cellPad:1}}];return LayoutAssist.evaluate({id:'source',sections,changed:0},{pass:true,textPreserved:true,errors:[],pages:[{chars:100,images:0,tables:0,overflow:0,vertical_fill:.7,column_bands:[]}]},sections,1);}''')
        check('missing model uses real deterministic fallback',fallback['safe'] and fallback['model']=='deterministic-rule-fallback' and fallback['model_fallback']=='model-unavailable',fallback)
        independent=no_model.evaluate('''()=>{const original=[{design:{size:11,leading:1.7,para:3,head:5,w:210,mx:20,cols:1,gap:7,titleSize:20,captionSize:8,tableSize:8,cellPad:1},locks:{font:true},html:'<p>unchanged source</p>',nested:{labels:['source','target']}}],before=LayoutAssist.clone(original),options=LayoutAssist.candidates(original),other=LayoutAssist.clone(options[1].sections);options[0].sections[0].design.size=30;options[0].sections[0].locks.font=false;options[0].sections[0].nested.labels[0]='changed';return {source:LayoutAssist.equal(original,before),sibling:LayoutAssist.equal(options[1].sections,other),strings:options.every(c=>c.sections[0].html===original[0].html),objects:options[0].sections[0]!==original[0]&&options[0].sections[0].nested!==original[0].nested};}''')
        check('candidate metadata mutations leave source and siblings independent',all(independent.values()),independent)
        no_model.close()
        # A genuinely narrow cell differs from a short cell stretched by its row.
        density_section = dict(section)
        density_section.pop('preserveSourcePageBreaks', None)
        density_section['design'] = {**pg.evaluate('Studio.defaultDesign()'), 'cols': 2}
        density_section['html'] = '<div class="table-wrap" data-block="dense-table" data-span="column"><table><tbody><tr><td>' + ('复杂表头保留完整说明' * 3) + '</td>' + '<td>12</td>' * 7 + '</tr></tbody></table></div>'
        pg.evaluate('(s)=>Studio.loadState({title:"Cell readability",sourceCSS:"",sections:[s]})', density_section)
        narrow = pg.evaluate('Studio.preview()')
        diagnostics = narrow.get('readability', {})
        check('painted narrow table cells receive located readability warnings', narrow['pass'] and diagnostics.get('severe',0)>0 and any(i['block']=='dense-table' and i['row']==1 and i['column']==1 for i in diagnostics.get('issues',[])), diagnostics)
        fragmentation = pg.evaluate("()=>{const d=document.getElementById('documentFrame').contentDocument;return [...d.querySelectorAll('#edPages table,#edPages tr')].map(e=>e.getClientRects().length)}")
        check('column balancing does not fragment table rows into neighbouring columns', all(n==1 for n in fragmentation), fragmentation)
        check('stretched short cells are not mistaken for wrapped text', all(c['lines']==1 and not c['narrow'] for c in diagnostics['tables'][0]['cells'][1:]), diagnostics)
        check('explicit column span survives readability diagnosis', diagnostics['tables'][0]['span']=='column' and all(i['manual_span_preserved'] for i in diagnostics['issues']), diagnostics)
        guarded = pg.evaluate("()=>LayoutAssist.rank([{id:'dense',safe:true,score:100,changed:0,report:{readability:{severe:2}}},{id:'readable',safe:true,score:1,changed:1,report:{readability:{severe:0}}}]).map(x=>x.id)")
        check('readable safe candidate precedes severe cell density despite learned score', guarded==['readable','dense'], guarded)
        pg.evaluate('(html)=>Studio.importHTML(html,"Undo independence")','<main><p data-uid="undo-unit">An unchanged source sentence.</p></main>')
        def undo_snapshot():
            return pg.evaluate("""()=>{const s=Studio.state.sections[0],d=document.getElementById('documentFrame').contentDocument,p=d.querySelector('[data-uid="undo-unit"]');return {size:s.design.size,locked:s.locks.size===true,text:p?.textContent,painted:p?parseFloat(d.defaultView.getComputedStyle(p).fontSize):null}}""")
        for size in [13,15]:
            pg.locator('#bodySize').fill(str(size))
            pg.evaluate('document.getElementById("applyLayout").onclick()')
        pg.evaluate('document.querySelector("[data-action=undo]").onclick()')
        undone=undo_snapshot()
        check('undo restores an independent earlier layout snapshot',undone['size']==13 and undone['locked'] and abs(undone['painted']-13*4/3)<.01 and undone['text']=='An unchanged source sentence.',undone)
        pg.evaluate('document.querySelector("[data-action=redo]").onclick()')
        redone=undo_snapshot()
        check('redo retains the later layout snapshot',redone['size']==15 and redone['locked'] and abs(redone['painted']-20)<.01,redone)
        pg.evaluate('document.querySelector("[data-action=undo]").onclick()')
        pg.locator('#bodySize').fill('14')
        pg.evaluate('document.getElementById("applyLayout").onclick()')
        pg.evaluate('document.querySelector("[data-action=redo]").onclick()')
        branched=undo_snapshot()
        check('editing after undo discards only the abandoned redo branch',branched['size']==14 and abs(branched['painted']-14*4/3)<.01 and branched['text']=='An unchanged source sentence.',branched)
        rapid=pg.evaluate("""async()=>{const input=document.getElementById('bodySize'),button=document.getElementById('applyLayout');input.value='16';const first=button.onclick();input.value='18';const second=button.onclick();return await Promise.race([Promise.all([first,second]).then(()=>({settled:true})),new Promise(r=>setTimeout(()=>r({settled:false}),10000))]);}""")
        check('rapid consecutive applications finish every render',rapid['settled'],rapid)
        if not rapid['settled']:
            raise AssertionError('A rapid edit left a render task pending')
        final=undo_snapshot()
        check('rapid applications retain the latest requested and painted size',final['size']==18 and abs(final['painted']-24)<.01,final)
        pg.evaluate('document.querySelector("[data-action=undo]").onclick()')
        previous=undo_snapshot()
        check('rapid applications retain the distinct preceding undo step',previous['size']==16 and abs(previous['painted']-16*4/3)<.01,previous)
        ordered=pg.evaluate("""async()=>{const input=document.getElementById('bodySize');input.value='17';const edited=document.getElementById('applyLayout').onclick(),undo=document.querySelector('[data-action=undo]').onclick();await Promise.all([edited,undo]);return Studio.state.sections[0].design.size;}""")
        check('undo requested during layout application runs afterward',ordered==16,ordered)
        check('queued operations produce no browser exceptions',not page_errors,page_errors)
        result['pass'] = not result['errors']
        br.close()
    (output / 'editor-regression.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'pass':result['pass'], 'errors':result['errors'], 'checks':len(result['checks'])}, ensure_ascii=False))
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--browser', default=os.environ.get('TRANSLATION_BROWSER'))
    args = ap.parse_args()
    raise SystemExit(0 if run(args.output, args.browser)['pass'] else 1)
