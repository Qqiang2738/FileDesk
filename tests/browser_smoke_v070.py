"""Offline Chromium preview UX contract, isolated from loopback network access.

PDF raster and document validation are separately tested against FastAPI in
pytest. This test exercises the actual UI and on-wire merge order.
"""
from pathlib import Path
from io import BytesIO
import json
import re

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
from pypdf import PdfWriter

ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'web/index.html').read_text()
css=(ROOT/'web/styles.css').read_text()
js=(ROOT/'web/app.js').read_text()
markup=html.replace('<link rel="stylesheet" href="/assets/styles.css?v=1.0.0" />',f'<style>{css}</style>')
markup=markup.replace('<script defer src="/assets/app.js?v=1.0.0"></script>',f'<script>{js}</script>')
writer=PdfWriter();writer.add_blank_page(width=612,height=792)
blob=BytesIO();writer.write(blob);pdf_data=blob.getvalue()


def raster(idx=0):
    image=Image.new('RGB',(500,680),(255,255,255))
    draw=ImageDraw.Draw(image)
    draw.rectangle((45,55,455,620),outline=(190,209,197),width=3)
    draw.rectangle((45,55,455,112),fill=(230,241,232))
    draw.text((70,76),f'PDF Preview - Page {idx+1}',fill=(38,81,51))
    for y in range(150,580,40):
        draw.line((80,y,420,y),fill=(210,220,214),width=3)
    out=BytesIO();image.save(out,'JPEG');return out.getvalue()


from base64 import b64encode
snapshot='data:image/jpeg;base64,'+b64encode(raster()).decode()
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1390,'height':900},accept_downloads=True)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(markup)
    page.evaluate("""imageData => {
      window.qa={previewCount:0,deleted:0,order:[],downloads:[]};
      const src=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');
      Object.defineProperty(HTMLImageElement.prototype,'src',{
        configurable:true,
        get(){return src.get.call(this)},
        set(value){return src.set.call(this,String(value).startsWith('/api/preview/')?imageData:value)}
      });
      window.fetch=async (uri,opts={}) => {
        if(uri==='/api/preview/pdf'&&opts.method==='POST'){
          window.qa.previewCount++;
          return new Response(JSON.stringify({id:String(window.qa.previewCount).padStart(32,'0'),pages:3}),{status:200});
        }
        if(uri.startsWith('/api/preview/')&&opts.method==='DELETE'){
          window.qa.deleted++;return new Response('{"ok":true}',{status:200});
        }
        if(uri==='/api/jobs'&&opts.method==='POST'){
          window.qa.order=opts.body.getAll('files').map(f=>f.name);
          return new Response(JSON.stringify({id:'0'.repeat(32),status:'queued'}),{status:202});
        }
        if(uri==='/api/jobs/'+'0'.repeat(32)){
          return new Response(JSON.stringify({status:'completed',result_id:'f'.repeat(32),filename:'合并结果.pdf'}),{status:200});
        }
        return new Response('{}',{status:404});
      };
      document.addEventListener('click',ev=>{
        const a=ev.target.closest('a[href*="/api/history/"]');
        if(a){window.qa.downloads.push(a.getAttribute('href'));ev.preventDefault();}
      },true);
    }""",snapshot)
    assert page.locator('.version').inner_text()=='V1.0.0'
    samples=[{'name':name,'mimeType':'application/pdf','buffer':pdf_data} for name in ['A-合同.pdf','B-附件.pdf','C-发票.pdf']]
    page.locator('#file-input').set_input_files(samples)
    assert page.locator('#file-list .file-row').count()==3
    assert page.locator('#execute').inner_text().startswith('合并')
    page.locator('.preview-open').first.click()
    assert page.locator('#preview-modal').is_visible()
    page.locator('.preview-large').wait_for(state='visible',timeout=7000)
    page.wait_for_function("document.querySelector('.preview-large')?.naturalWidth > 0",timeout=7000)
    assert page.locator('.preview-file-entry').count()==3
    page.locator('#preview-next').click()
    assert '2 / 3' in page.locator('#preview-page-label').inner_text()
    page.locator('.preview-file-choice').nth(1).click()
    assert 'B-附件.pdf' in page.locator('#preview-subtitle').inner_text()
    page.locator('.preview-order-button[aria-label="B-附件.pdf 上移"]').click()
    assert 'B-附件.pdf' in page.locator('.preview-file-entry').first.inner_text()
    page.screenshot(path=str(ROOT/'docs/04-PDF合并预览.png'),full_page=True)
    page.locator('#preview-done').click()
    assert page.locator('#preview-modal').is_hidden()
    assert 'B-附件.pdf' in page.locator('#file-list .file-name').first.inner_text()
    page.wait_for_function('window.qa.deleted>=3',timeout=5000)
    page.locator('#execute').click()
    page.wait_for_function('window.qa.downloads.length===1',timeout=7000)
    assert page.evaluate('window.qa.order')==['B-附件.pdf','A-合同.pdf','C-发票.pdf']
    # Image preview uses a short-lived browser blob URL, no upload to the backend.
    raw=BytesIO()
    Image.new('RGB',(320,200),(123,155,136)).save(raw,format='PNG')
    page.locator('#file-input').set_input_files({'name':'test-picture.png','mimeType':'image/png','buffer':raw.getvalue()})
    page.locator('.preview-open').first.click()
    assert page.locator('#preview-modal').is_visible()
    page.wait_for_function("document.querySelector('.preview-large')?.naturalWidth===320",timeout=5000)
    assert page.locator('#preview-pages').is_hidden()
    page.wait_for_function("document.querySelector('.preview-large')?.getAttribute('src')?.startsWith('blob:')",timeout=5000)
    page.screenshot(path=str(ROOT/'docs/05-图片预览.png'),full_page=True)
    page.keyboard.press('Escape')
    assert page.locator('#preview-modal').is_hidden()
    assert not errors,errors
    print('PASS preview: pages, thumbnail list, reorder, cleanup, merge request order')
    browser.close()
