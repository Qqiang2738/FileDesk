"""V1.0 release acceptance: singleton, headers, diagnostics, version alignment."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import json
import re

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter, PdfReader

from filedesk import server
from filedesk.instance import InstanceLock, AlreadyRunning, find_local_filedesk
from filedesk.version import VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_contract():
    assert VERSION == '1.0.0'
    html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
    js = (ROOT / 'web/app.js').read_text(encoding='utf-8')
    assert f'name="filedesk-build" content="{VERSION}"' in html
    assert f'styles.css?v={VERSION}' in html
    assert f'app.js?v={VERSION}' in html
    assert f"const BUILD = '{VERSION}'" in js
    assert 'V' + VERSION in html
    assert VERSION in (ROOT / 'README.md').read_text(encoding='utf-8')
    with TestClient(server.app) as client:
        assert client.get('/api/health').json()['version'] == VERSION


def test_standalone_local_security_headers():
    with TestClient(server.app) as client:
        for endpoint in ('/', '/assets/app.js', '/api/health', '/api/history'):
            response = client.get(endpoint)
            assert response.status_code == 200
            assert response.headers['x-frame-options'] == 'DENY'
            assert response.headers['x-content-type-options'] == 'nosniff'
            assert response.headers['referrer-policy'] == 'no-referrer'
            csp = response.headers['content-security-policy']
            assert "object-src 'none'" in csp and "connect-src 'self'" in csp
        assert client.get('/').headers['cache-control'].startswith('no-store')
        # Reject cross-site forms and fetch while keeping same-origin browser use.
        response = client.post('/api/jobs', headers={'Origin': 'http://other.example'},
            data={'operation': 'image_convert', 'options': '{}'},
            files=[('files', ('image.png', b'invalid', 'image/png'))])
        assert response.status_code == 403


def test_instance_guard_blocks_second_process_in_same_profile(tmp_path):
    lock = tmp_path / '.instance.lock'
    with InstanceLock(lock):
        with pytest.raises(AlreadyRunning):
            with InstanceLock(lock):
                pass
    with InstanceLock(lock):
        assert lock.stat().st_size in (0, 1)


def test_find_existing_filedesk_only_when_health_matches(monkeypatch):
    from filedesk import instance
    monkeypatch.setattr(instance, '_is_open', lambda port: port == 8765)
    class Resp:
        def __init__(self, data): self.data = data
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, length): return json.dumps(self.data).encode('utf-8')
    class Open:
        def __init__(self, data): self.data = data
        def open(self, request, timeout):
            assert request.full_url == 'http://127.0.0.1:8765/api/health'
            return Resp(self.data)
    monkeypatch.setattr(instance, 'build_opener', lambda *args: Open(
        {'status': 'ok', 'local_only': True, 'version': '0.7.0'}))
    assert find_local_filedesk() == (8765, '0.7.0')
    monkeypatch.setattr(instance, 'build_opener', lambda *args: Open(
        {'status': 'ok', 'local_only': False, 'version': '0.7.0'}))
    assert find_local_filedesk() is None


def test_doctor_without_reading_work_files(monkeypatch, tmp_path):
    from filedesk import diagnostics
    monkeypatch.setenv('FILEDESK_HISTORY_DIR', str(tmp_path / 'my-history'))
    checks = diagnostics.check_environment()
    assert any(name == '本地历史存储' and result == 'OK' for result, name, _ in checks)
    assert any(name == '系统临时目录' and result == 'OK' for result, name, _ in checks)
    assert not list((tmp_path / 'my-history').glob('.filedesk-check-*'))


def test_release_does_not_ship_desktop_wrapper():
    assert not (ROOT / 'build-mac-dmg.command').exists()
    assert not (ROOT / 'run-mac-desktop.command').exists()
    assert (ROOT / 'doctor-mac.command').exists()
    assert (ROOT / 'start-mac.command').exists()
    assert not list(ROOT.rglob('*.app'))


def test_release_critical_pdf_image_api_still_works(monkeypatch, tmp_path):
    monkeypatch.setenv('FILEDESK_HISTORY_DIR', str(tmp_path / 'history'))
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    data = BytesIO()
    writer.write(data)
    with TestClient(server.app) as client:
        resp = client.post('/api/process', data={'operation': 'pdf_merge', 'options': '{}'}, files=[
            ('files', ('one.pdf', data.getvalue(), 'application/pdf')),
            ('files', ('two.pdf', data.getvalue(), 'application/pdf')),
        ])
        assert resp.status_code == 200, resp.text
        assert len(PdfReader(BytesIO(resp.content)).pages) == 2
        assert 'filename*=' in resp.headers['content-disposition']
        assert resp.headers['content-type'] == 'application/pdf'
        source = BytesIO()
        Image.new('RGBA', (70, 50), (80, 100, 130, 170)).save(source, 'PNG')
        photo = client.post('/api/process', data={'operation': 'image_convert',
            'options': '{"format":"jpg"}'}, files=[('files', ('photo.png', source.getvalue(), 'image/png'))])
        assert photo.status_code == 200, photo.text
        assert photo.headers['content-type'] == 'image/jpeg'
        assert '.jpg' in photo.headers['content-disposition']
        with Image.open(BytesIO(photo.content)) as output:
            assert output.format == 'JPEG'
        entries = client.get('/api/history').json()['items']
        assert len(entries) == 2
        saved = client.get(f"/api/history/{entries[0]['id']}/download")
        assert saved.status_code == 200
        assert saved.content == photo.content
