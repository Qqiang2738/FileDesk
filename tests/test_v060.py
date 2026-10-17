"""V1.0.0 reliability regressions: cancellation, history races and actual artifacts."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from threading import Event
import time
import zipfile

from fastapi.testclient import TestClient
from PIL import Image
import pytest
from pypdf import PdfWriter, PdfReader

from filedesk import jobs, server
from filedesk.engine import FileDeskError
from filedesk.result_store import ResultStore


def _wait_for(job_id, statuses=('completed', 'failed', 'cancelled')):
    for _ in range(160):
        job = jobs.get(job_id)
        if job and job['status'] in statuses:
            return job
        time.sleep(.025)
    pytest.fail(f'task {job_id} did not finish')


def test_cancel_running_task_and_delete_uploads(tmp_path):
    started, release = Event(), Event()
    directory = tmp_path / 'queued'
    directory.mkdir()
    (directory / 'input.txt').write_text('sensitive temporary upload')

    def worker(folder, progress, job_id):
        progress('转换阶段', 20)
        started.set()
        assert release.wait(4)
        progress('下个转换阶段', 40)  # cooperative cancellation checkpoint
        pytest.fail('Cancelled work must not report completion')

    job = jobs.submit('fake', str(directory), worker)
    assert started.wait(3)
    result = jobs.cancel(job['id'])
    assert result['cancel_requested'] is True
    assert result['stage'].startswith('正在停止')
    release.set()
    completed = _wait_for(job['id'])
    assert completed['status'] == 'cancelled'
    assert completed['result_id'] == ''
    for _ in range(80):
        if not directory.exists(): break
        time.sleep(.025)
    assert not directory.exists()


def test_cancel_queued_task_never_invokes_worker(tmp_path):
    gate, entered, called = Event(), Event(), Event()
    one = tmp_path / 'one'; two = tmp_path / 'two'
    one.mkdir(); two.mkdir()
    def first(folder, progress, job_id):
        entered.set()
        assert gate.wait(4)
        return '', 'nothing'
    def second(folder, progress, job_id):
        called.set()
        return '', 'nothing'
    active = jobs.submit('fake', str(one), first)
    assert entered.wait(3)
    queued = jobs.submit('fake', str(two), second)
    assert jobs.cancel(queued['id'])['status'] == 'cancelled'
    gate.set()
    _wait_for(active['id'])
    _wait_for(queued['id'])
    for _ in range(100):
        if not two.exists(): break
        time.sleep(.02)
    assert not called.is_set()
    assert not two.exists()


def test_failed_results_are_not_reported_as_success(tmp_path):
    src = tmp_path / 'bad.pdf'
    src.write_text('This is NOT a PDF')
    with pytest.raises(FileDeskError, match='有效的 PDF'):
        server._verify_outputs([src])
    src = tmp_path / 'broken.docx';src.write_bytes(b'PKbad')
    with pytest.raises(FileDeskError, match='Word/ZIP'):
        server._verify_outputs([src])
    src = tmp_path / 'image.jpg';src.write_bytes(b'not actually jpeg')
    with pytest.raises(FileDeskError, match='JPG'):
        server._verify_outputs([src])
    pdf = tmp_path / 'ok.pdf'
    writer = PdfWriter();writer.add_blank_page(width=100,height=100)
    with pdf.open('wb') as file:writer.write(file)
    server._verify_outputs([pdf])


def test_duplicate_output_filenames_are_never_omitted(tmp_path, monkeypatch):
    def fake(paths, outgoing, opts):
        out = []
        for index, content in enumerate(('alpha', 'bravo')):
            directory = outgoing / str(index)
            directory.mkdir()
            file = directory / 'result.csv'
            file.write_text(content, encoding='utf-8')
            out.append(file)
        return out
    monkeypatch.setitem(server.OPERATIONS, 'qa_collision', fake)
    from starlette.datastructures import UploadFile
    files = [UploadFile(file=BytesIO(b'a'),filename='a.csv')]
    directory = tmp_path / 'run';directory.mkdir()
    result = server._run('qa_collision', '{}', files, directory)
    with zipfile.ZipFile(result) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) == 2
        assert {archive.read(name).decode() for name in names} == {'alpha', 'bravo'}


def test_identical_upload_names_do_not_overwrite_image_conversion(tmp_path, monkeypatch):
    monkeypatch.setenv('FILEDESK_HISTORY_DIR', str(tmp_path/'history'))
    def png(color):
        out=BytesIO()
        Image.new('RGB',(15,12),color).save(out,format='PNG')
        return out.getvalue()
    client=TestClient(server.app)
    r=client.post('/api/process',data={'operation':'image_convert','options':'{"format":"jpg"}'},
                  files=[('files',('same.png',png('red'),'image/png')),
                         ('files',('same.png',png('blue'),'image/png'))])
    assert r.status_code == 200, r.text
    with zipfile.ZipFile(BytesIO(r.content)) as archive:
        names=archive.namelist()
        assert len(names)==len(set(names))==2
        pixels=[Image.open(BytesIO(archive.read(name))).getpixel((0,0)) for name in names]
        assert pixels[0][0] > pixels[0][2] and pixels[1][2] > pixels[1][0]


def test_history_thread_safe_and_deletes_one_record(tmp_path):
    store=ResultStore(tmp_path/'history')
    items=[]
    for index in range(8):
        path=tmp_path/f'item_{index}.csv'
        path.write_text(f'编号\n{index}',encoding='utf-8')
        items.append(path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        records=list(pool.map(lambda path: ResultStore(tmp_path/'history').add(path,'table_to_csv',1), items))
    assert len(store.list())==8
    ids={row['id'] for row in store.list()}
    assert ids=={row['id'] for row in records}
    assert store.delete(records[0]['id'])
    assert not store.get(records[0]['id'])
    assert len(store.list())==7
    assert not store.delete('not-an-id')


def test_cancel_endpoint_rejects_unknown_id():
    with TestClient(server.app) as client:
        assert client.post('/api/jobs/invalid/cancel').status_code == 404
        assert client.post('/api/jobs/'+'0'*32+'/cancel').status_code == 404


def test_source_and_page_versions_consistent():
    root=Path(__file__).parents[1]
    html=(root/'web/index.html').read_text()
    js=(root/'web/app.js').read_text()
    assert 'content="1.0.0"' in html
    assert "BUILD = '1.0.0'" in js
    assert 'V1.0.0' in html
    assert 'cancel-job' in html and 'inline-error' in html
    assert 'fetch(\'/api/jobs/\'+activeJobId+\'/cancel\'' in js
    with TestClient(server.app) as client:
        assert client.get('/api/health').json()['version']=='1.0.0'
