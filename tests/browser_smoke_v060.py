"""Offline browser interaction contract for the V1.0.0 workspace.

Actual HTTP uploads, conversion and history are covered by pytest. Chromium's
sandbox in some execution environments blocks loopback network access, so this
smoke validates the browser UI with predictable local API responses.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'web/index.html').read_text(encoding='utf-8')
css=(ROOT/'web/styles.css').read_text(encoding='utf-8')
js=(ROOT/'web/app.js').read_text(encoding='utf-8')
markup=html.replace('<link rel="stylesheet" href="/assets/styles.css?v=1.0.0" />',f'<style>{css}</style>')
markup=markup.replace('<script defer src="/assets/app.js?v=1.0.0"></script>', f'<script>{js}</script>')
mock = r'''() => {
 window.qa={status:'idle',downloads:[], cancelled:false, startCount:0};
 const jid='0123456789abcdef0123456789abcdef';
 const rid='fedcba9876543210fedcba9876543210';
 window.fetch=async (uri, opts={})=>{
   if(uri==='/api/jobs'){
     window.qa.startCount++;
     window.qa.status='running';
     return new Response(JSON.stringify({id:jid,status:'queued'}),{status:202});
   }
   if(uri===`/api/jobs/${jid}`){
     if(window.qa.cancelled) return new Response(JSON.stringify({id:jid,status:'cancelled',stage:'已取消',percent:30}));
     if(window.qa.status==='running') {window.qa.status='completed';return new Response(JSON.stringify({id:jid,status:'running',stage:'生成表格',percent:50}));}
     return new Response(JSON.stringify({id:jid,status:'completed',stage:'处理完成',percent:100,result_id:rid,filename:'订单_智能排版.docx'}));
   }
   if(uri===`/api/jobs/${jid}/cancel`){window.qa.cancelled=true;return new Response(JSON.stringify({id:jid,status:'running',stage:'正在停止'}));}
   if(uri==='/api/history') return new Response(JSON.stringify({items:[{id:rid,name:'订单_智能排版.docx',count:1,action:'excel_to_word',created_at:1792160000}]}));
   return new Response('{}',{status:404});
 };
 document.addEventListener('click', ev=>{
   const a=ev.target.closest('a[href*="/api/history/"]');
   if(a){window.qa.downloads.push(a.getAttribute('href'));ev.preventDefault();}
 },true);
}'''

with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1360,'height':900},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(markup)
    page.evaluate(mock)
    assert page.locator('.version').inner_text()=='V1.0.0'
    assert page.locator('#welcome-drop').is_visible()
    assert not page.locator('#recommend-subtitle').is_visible()
    (ROOT/'docs').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT/'docs/01-空白工作台.png'),full_page=True)
    page.locator('#file-input').set_input_files(str(ROOT/'tests/fixtures/orders.xlsx'))
    assert page.locator('#loaded-view').is_visible()
    assert page.locator('#execute').is_enabled()
    page.screenshot(path=str(ROOT/'docs/02-文件处理.png'),full_page=True)
    page.locator('#execute').click()
    page.wait_for_function('window.qa.downloads.length === 1',timeout=7000)
    assert page.locator('#empty-view').is_visible()
    assert page.locator('#success-banner').is_visible()
    page.screenshot(path=str(ROOT/'docs/03-处理完成.png'),full_page=True)
    page.locator('#redownload').click()
    assert len(page.evaluate('window.qa.downloads'))==2
    page.locator('#history-toggle').click()
    page.locator('.history-item').wait_for()
    page.locator('.history-download').click()
    assert len(page.evaluate('window.qa.downloads'))==3
    page.locator('#history-close').click()

    # Test active cancellation: leave the first operation running until cancelled.
    page.locator('#file-input').set_input_files(str(ROOT/'tests/fixtures/orders.xlsx'))
    page.evaluate("window.qa.cancelled=false;window.qa.status='running';")
    page.locator('#execute').click()
    page.locator('#cancel-job').wait_for(state='visible',timeout=3000)
    page.locator('#cancel-job').click()
    page.wait_for_function('window.qa.cancelled',timeout=2000)
    page.locator('#cancel-job').wait_for(state='hidden',timeout=6000)
    assert page.locator('#loaded-view').is_visible(), 'cancel must keep input files for retry'
    assert not errors, errors
    print('PASS browser: startup, input, suggestions, direct download, re-download, history, cancellation')
    browser.close()
