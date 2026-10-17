"""Image download naming, CSV integration, and bounded streaming regression."""
from pathlib import Path
import csv
import io
import time

from docx import Document
from fastapi.testclient import TestClient
from PIL import Image

from filedesk.server import app
from filedesk.engine import OPERATIONS
from filedesk.smart_excel import excel_to_word
from filedesk.tabular_stream import sheets


def test_csv_export_and_streaming_editable_word(tmp_path):
    sample=tmp_path/'列表.csv'
    with sample.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f)
        w.writerow(['产品编号','产品名称','数量','单位'])
        w.writerow(['B001','铜线',20,'米'])
        w.writerow(['B002','接头',12,'个'])
    output=OPERATIONS['excel_to_word']([sample],tmp_path,{})
    assert any(x.suffix=='.docx' for x in output)
    assert any(x.suffix=='.csv' for x in output)
    doc=Document(next(x for x in output if x.suffix=='.docx'))
    assert any('铜线' in cell.text for table in doc.tables for row in table.rows for cell in row.cells)
    exported=OPERATIONS['table_to_csv']([sample],tmp_path,{})
    assert exported[0].suffix=='.csv'
    with exported[0].open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.reader(f))
    assert len(rows)==3 and rows[1][1]=='B001'


def test_xlsx_stream_metadata_no_loss():
    src=Path(__file__).parent/'fixtures'/'orders.xlsx'
    with sheets(src) as parts:
        name,rows=parts[0]
        material=list(rows)
    assert name=='订单' and len(material)==4
    assert material[0][1][0]=='订单号'
    assert material[1][1][1]=='甲客户'


def test_single_jpg_http_response_preserves_extension(tmp_path,monkeypatch):
    monkeypatch.setenv('FILEDESK_HISTORY_DIR',str(tmp_path/'history'))
    png=io.BytesIO()
    Image.new('RGBA',(12,8),(255,0,0,40)).save(png,'PNG')
    with TestClient(app) as c:
        r=c.post('/api/jobs',data={'operation':'image_convert','options':'{"format":"jpg"}'},
                 files=[('files',('源图.png',png.getvalue(),'image/png'))])
        assert r.status_code==202, r.text
        jid=r.json()['id']
        for _ in range(120):
            status=c.get('/api/jobs/'+jid).json()
            if status['status'] in ('completed','failed'):break
            time.sleep(.05)
        assert status['status']=='completed',status
        assert status['filename'].endswith('.jpg')
        response=c.get('/api/jobs/'+jid+'/download')
        assert response.status_code==200
        assert response.headers['content-type'].startswith('image/jpeg')
        assert response.headers['x-filedesk-filename'].lower().endswith('.jpg')
        assert b'filename*=' in response.headers['content-disposition'].encode().lower()
        assert response.content.startswith(b'\xff\xd8\xff')
        assert Image.open(io.BytesIO(response.content)).size==(12,8)
        record=c.get('/api/history/'+status['result_id']+'/download')
        assert record.content==response.content
        assert record.headers['content-type'].startswith('image/jpeg')


def test_csv_280k_cells_stream_without_legacy_cap(tmp_path):
    src=tmp_path/'超过25万.csv'
    with src.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f)
        w.writerow(['编号','名称','数量']+[f'字段{i}' for i in range(97)])
        for i in range(2600):
            w.writerow([f'ID{i:05d}',f'商品{i}',20]+['内容']*97)
    out=tmp_path/'output';out.mkdir()
    produced=excel_to_word([src],out,{})
    assert len([x for x in produced if x.suffix=='.docx'])==7
    with next(x for x in produced if x.suffix=='.csv').open(encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f)
        header=next(reader)
        assert len(header)==101
        assert sum(1 for _ in reader)==2600
