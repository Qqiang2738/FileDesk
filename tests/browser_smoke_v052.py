"""Offline Playwright smoke; real HTTP and disk history are covered by pytest.

This runner works when local browser networking is administratively blocked.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT/'web/index.html').read_text(encoding='utf-8')
CSS = (ROOT/'web/styles.css').read_text(encoding='utf-8')
JS = (ROOT/'web/app.js').read_text(encoding='utf-8')
markup = (HTML.replace('<link rel="stylesheet" href="/assets/styles.css?v=1.0.0" />', f'<style>{CSS}</style>')
           .replace('<script defer src="/assets/app.js?v=1.0.0"></script>', f'<script>{JS}</script>'))
record={'id':'abcdef0123456789abcdef0123456789','name':'orders_01_智能排版.docx','action':'excel_to_word','count':1,'created_at':1792160000}
mock = '''() => {
 const rec=%s;
 window.fetch=async (uri,opts={}) => {
   if(uri==='/api/history') return new Response(JSON.stringify({items:[rec]}),{status:200,headers:{'Content-Type':'application/json'}});
   if(uri==='/api/process') return new Response(new Blob(['fake-docx-data'],{type:'application/octet-stream'}),{status:200,headers:{'Content-Disposition':"attachment; filename*=UTF-8''orders_01.docx",'X-FileDesk-Result-Id':rec.id}});
   if(uri==='/api/history'&&opts.method==='DELETE')return new Response(JSON.stringify({ok:true}),{status:200});
   return new Response('{}',{status:404});
 };
 document.addEventListener('click',ev=>{const anchor=ev.target.closest('a[href*="/api/history/"]');if(anchor){window.historyClicked=anchor.getAttribute('href');ev.preventDefault();}},true);
}''' % __import__('json').dumps(record,ensure_ascii=False)

with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True,executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1360,'height':920},accept_downloads=True)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content(markup)
    page.evaluate(mock)
    assert page.locator('#welcome-drop').is_visible()
    assert page.locator('.version').inner_text()=='V1.0.0'
    (ROOT/'docs').mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT/'docs/首页-字体优化.png'),full_page=True)
    page.locator('#file-input').set_input_files(str(ROOT/'tests/fixtures/orders.xlsx'))
    assert page.locator('#loaded-view').is_visible()
    assert page.locator('#operation-list').get_by_text('Excel → 可编辑 Word').count()>0
    page.screenshot(path=str(ROOT/'docs/工作台-字体优化.png'),full_page=True)
    with page.expect_download(timeout=10000) as info:
        page.locator('#execute').click()
    assert info.value.suggested_filename.endswith('.docx')
    assert page.locator('#empty-view').is_visible()
    page.locator('#history-toggle').click()
    page.locator('.history-item').first.wait_for()
    assert page.locator('.history-download').is_visible()
    page.screenshot(path=str(ROOT/'docs/历史-重新下载.png'),full_page=True)
    page.locator('.history-download').first.click()
    assert page.evaluate('window.historyClicked')=='/api/history/'+record['id']+'/download'
    # New page simulates a fresh tab. History contents come from the server API.
    page2=browser.new_page(viewport={'width':1360,'height':920})
    page2.set_content(markup)
    page2.evaluate(mock)
    page2.locator('#history-toggle').click()
    page2.locator('.history-download').wait_for()
    assert page2.locator('.history-download').count()==1
    assert not errors,errors
    print('PASS: legible UI, Excel recommendation, success reset, modal history re-download, fresh-tab history')
    browser.close()
