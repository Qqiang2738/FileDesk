"""V1.0.0 preview: one-page raster, limits, local cleanup, security and UX contract."""
from io import BytesIO
from pathlib import Path
from time import monotonic

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from filedesk import server
from filedesk.preview import PreviewStore


def make_pdf(pages=3) -> bytes:
    result=BytesIO()
    writer=PdfWriter()
    for i in range(pages):
        writer.add_blank_page(width=612, height=792)
    writer.write(result)
    return result.getvalue()


def test_preview_create_render_navigate_and_cleanup(monkeypatch, tmp_path):
    store=PreviewStore(tmp_path/'temp')
    monkeypatch.setattr(server,'PREVIEWS',store)
    with TestClient(server.app) as client:
        created=client.post('/api/preview/pdf',files={'file':('many.pdf',make_pdf(3),'application/pdf')})
        assert created.status_code==200,created.text
        obj=created.json()
        assert obj['pages']==3 and len(obj['id'])==32
        token=obj['id']
        source=tmp_path/'temp'/f'{token}.pdf'
        assert source.exists()
        p=client.get(f'/api/preview/{token}/pages/2')
        assert p.status_code==200 and p.content.startswith(b'\xff\xd8\xff')
        assert p.headers['content-type']=='image/jpeg'
        assert p.headers['cache-control']=='no-store'
        small=client.get(f'/api/preview/{token}/pages/2?size=thumb')
        assert small.status_code==200 and small.content.startswith(b'\xff\xd8\xff')
        from PIL import Image
        with Image.open(BytesIO(p.content)) as full, Image.open(BytesIO(small.content)) as thumb:
            assert full.size[0]>thumb.size[0]
        assert client.get(f'/api/preview/{token}/pages/3').status_code==400
        assert client.get(f'/api/preview/{token}/pages/0?size=bogus').status_code==400
        assert client.delete(f'/api/preview/{token}').status_code==200
        assert not source.exists()
        assert client.get(f'/api/preview/{token}/pages/0').status_code==404


def test_preview_rejects_invalid_non_pdf_and_password(monkeypatch,tmp_path):
    import pymupdf
    store=PreviewStore(tmp_path/'temp')
    monkeypatch.setattr(server,'PREVIEWS',store)
    with TestClient(server.app) as client:
        assert client.post('/api/preview/pdf', files={'file':('image.jpg',b'hello','image/jpeg')}).status_code==400
        assert client.post('/api/preview/pdf', files={'file':('bad.pdf',b'not a pdf','application/pdf')}).status_code==400
        assert client.get('/api/preview/not-a-token/pages/0').status_code==404
        # password protection does not silently rasterize private content
        doc=pymupdf.open(stream=make_pdf(1),filetype='pdf')
        encrypted=doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='user')
        doc.close()
        assert client.post('/api/preview/pdf',files={'file':('locked.pdf',encrypted,'application/pdf')}).status_code==400
    assert not list((tmp_path/'temp').glob('*.pdf'))


def test_preview_ttl_evicts_expired_and_session_cap(tmp_path):
    from filedesk.preview import MAX_SESSIONS
    store=PreviewStore(tmp_path,ttl=1)
    token,_=store.add_pdf(BytesIO(make_pdf()),'a.pdf')
    store._items[token].created=monotonic()-3
    assert store.read(token) is None
    assert not (tmp_path/f'{token}.pdf').exists()
    for i in range(MAX_SESSIONS+2):
        store.add_pdf(BytesIO(make_pdf()),f'{i}.pdf')
    assert len(store._items)==MAX_SESSIONS
    assert len(list(tmp_path.glob('*.pdf')))==MAX_SESSIONS


def test_preview_upload_size_limit(tmp_path):
    from filedesk.preview import MAX_PREVIEW_BYTES
    from filedesk.engine import FileDeskError
    store=PreviewStore(tmp_path)
    class Oversized:
        def __init__(self):self.called=0
        def read(self,n):
            self.called+=1
            return b'%'*(1024*1024) if self.called<=66 else b''
    try:
        store.add_pdf(Oversized(),'large.pdf')
        raise AssertionError('must reject oversized file')
    except FileDeskError as e:
        assert '65 MB' in str(e)
    assert not list(tmp_path.glob('*.pdf'))


def test_preview_ui_and_version_contract():
    root=Path(__file__).resolve().parents[1]
    js=(root/'web/app.js').read_text()
    html=(root/'web/index.html').read_text()
    assert 'V1.0.0' in html
    assert 'preview-modal' in html and 'preview-files' in html
    assert 'preview-open' in js and 'closePreview' in js
    assert 'previewOrder' not in js # the existing moveFile function is reused
    assert 'moveFile(item.id,delta)' in js


def test_pdf_merge_order_after_preview_scenarios(tmp_path):
    """Order encoded into the merge POST must become real PDF page order."""
    from starlette.datastructures import UploadFile
    import pymupdf
    from pypdf import PdfReader

    def with_label(label):
        doc=pymupdf.open();page=doc.new_page()
        page.insert_text((55,100),label,fontsize=20)
        raw=doc.tobytes();doc.close();return raw

    uploads=[UploadFile(file=BytesIO(with_label(label)),filename=f'{label}.pdf')
             for label in ('second','first','third')]
    root=tmp_path/'run';root.mkdir()
    merged=server._run('pdf_merge','{}',uploads,root)
    reader=PdfReader(str(merged))
    assert len(reader.pages)==3
    assert ['second','first','third']==[page.extract_text().strip() for page in reader.pages]
