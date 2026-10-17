"""Local-only FastAPI backend for the FileDesk browser workspace."""
from __future__ import annotations

import json
import shutil
import logging
import os
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote, urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .engine import OPERATIONS, FileDeskError, clean_name, find_libreoffice
from .result_store import ResultStore
from . import jobs
from .version import VERSION
from .preview import PREVIEWS

ROOT = Path(getattr(__import__('sys'), '_MEIPASS', Path(__file__).resolve().parents[1]))
WEB = ROOT / 'web'
MAX_FILES = 35
MAX_EACH = 65 * 1024 * 1024
MAX_TOTAL = 200 * 1024 * 1024
MAX_RESULT = 450 * 1024 * 1024

app = FastAPI(title='文序 FileDesk', docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
@app.middleware('http')
async def guard(request: Request, call_next):
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin:
            uri = urlparse(origin)
            expected = request.headers.get('host', '')
            if uri.scheme != 'http' or uri.netloc != expected:
                return JSONResponse({'detail': '只允许本地应用发起文件操作'}, status_code=403)
    response = await call_next(request)
    # Defence in depth for an app that processes private local documents.
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    if request.url.path == '/' or request.url.path.startswith('/assets/'):
        # Paired HTML / JS / CSS must never be served out of sync after upgrades.
        response.headers['Cache-Control'] = 'no-store, max-age=0, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


def _media_type(path: Path) -> str:
    return {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.zip': 'application/zip',
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.webp': 'image/webp',
        '.csv': 'text/csv; charset=utf-8',
    }.get(path.suffix.lower(), 'application/octet-stream')


@app.get('/api/health')
def health():
    return {'status': 'ok', 'local_only': True, 'office_ready': bool(find_libreoffice()),
            'version': VERSION}


def _run(operation: str, options: str, files: list[UploadFile], working: Path, progress=None) -> Path:
    if operation not in OPERATIONS:
        raise FileDeskError('不支持此操作')
    if not 1 <= len(files) <= MAX_FILES:
        raise FileDeskError(f'每次最多处理 {MAX_FILES} 个文件')
    try:
        opts = json.loads(options)
        if not isinstance(opts, dict):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise FileDeskError('参数格式错误') from exc

    if callable(progress):
        opts['_progress'] = progress
    incoming = working / 'incoming'
    outgoing = working / 'results'
    incoming.mkdir()
    outgoing.mkdir()
    paths = []
    seen_names = set()
    total = 0
    for i, file in enumerate(files, 1):
        raw_name = (file.filename or '').replace('\\', '/').split('/')[-1]
        suffix = Path(raw_name).suffix.lower()
        if not re.fullmatch(r'\.[a-z0-9]{1,8}', suffix):
            raise FileDeskError('文件扩展名不合法')
        folder = incoming / f'{i:02d}'
        folder.mkdir()
        safe_base = clean_name(raw_name)
        resolved_base = safe_base
        n = 2
        while resolved_base.casefold() in seen_names:
            resolved_base = f'{safe_base}_{n}'
            n += 1
        seen_names.add(resolved_base.casefold())
        target = folder / f'{resolved_base}{suffix}'
        size = 0
        with target.open('wb') as destination:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                total += len(chunk)
                if size > MAX_EACH or total > MAX_TOTAL:
                    raise FileDeskError('文件太大：单个不超过 65 MB，批次不超过 200 MB')
                destination.write(chunk)
        if not size:
            raise FileDeskError(f'空文件：{raw_name}')
        paths.append(target)

    if callable(progress):
        progress('开始转换文件',6)
    output_files = OPERATIONS[operation](paths, outgoing, opts)
    if not output_files:
        raise FileDeskError('未生成任何结果')
    if any(not f.is_file() or not f.is_relative_to(outgoing) for f in output_files):
        raise FileDeskError('输出目录异常')
    if callable(progress):
        progress('检查转换结果',92)
    _verify_outputs(output_files)
    if callable(progress):
        progress('正在整理并打包结果',95)
    if len(output_files) == 1:
        result = output_files[0]
    else:
        result = outgoing / '文序_批量结果.zip'
        with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as bundle:
            used = set()
            for file in output_files:
                # Multiple sources may emit the same basename. Keep *all* outputs.
                name = file.name
                counter = 2
                while name.casefold() in used:
                    name = f'{file.stem}_{counter}{file.suffix}'
                    counter += 1
                used.add(name.casefold())
                bundle.write(file, arcname=name)
    if result.stat().st_size > MAX_RESULT:
        raise FileDeskError('结果过大，请减少页数或拆成多个批次处理')
    return result



def _verify_outputs(paths: list[Path]) -> None:
    """Reject empty/corrupt conversion artifacts before reporting completion.

    This is a structural integrity gate, *not* a promise of visual fidelity.
    """
    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise FileDeskError('转换结果为空或无法读取')
        suffix = path.suffix.lower()
        with path.open('rb') as stream:
            head = stream.read(16)
        if suffix == '.pdf' and not head.startswith(b'%PDF-'):
            raise FileDeskError('转换结果不是有效的 PDF 文件')
        if suffix in ('.docx', '.zip'):
            try:
                with zipfile.ZipFile(path) as archive:
                    if not archive.namelist():
                        raise ValueError('empty archive')
                    if suffix == '.docx' and 'word/document.xml' not in archive.namelist():
                        raise ValueError('missing Word document')
            except (zipfile.BadZipFile, ValueError, OSError) as exc:
                raise FileDeskError('转换结果不是有效的 Word/ZIP 文件') from exc
        if suffix in ('.jpg', '.jpeg') and not head.startswith(b'\xff\xd8\xff'):
            raise FileDeskError('JPG 文件内容不正确')
        if suffix == '.png' and not head.startswith(b'\x89PNG\r\n\x1a\n'):
            raise FileDeskError('PNG 文件内容不正确')
        if suffix == '.webp' and not (head.startswith(b'RIFF') and head[8:12] == b'WEBP'):
            raise FileDeskError('WebP 文件内容不正确')
        if suffix == '.csv':
            try:
                with path.open(encoding='utf-8-sig', newline='') as stream:
                    stream.read(256)
            except UnicodeError as exc:
                raise FileDeskError('CSV 结果编码异常') from exc


def _fail(exc: Exception) -> None:
    if isinstance(exc, FileDeskError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    logging.exception('FileDesk processing error')
    raise HTTPException(status_code=500, detail='处理失败。请检查文件格式或减少文件数量。') from exc


def _close_files(files: list[UploadFile]) -> None:
    for upload in files:
        upload.file.close()


@app.post('/api/process')
def process(operation: str = Form(...), options: str = Form('{}'), files: list[UploadFile] = File(...)):
    try:
        with tempfile.TemporaryDirectory(prefix='filedesk-') as folder:
            result = _run(operation, options, files, Path(folder))
            body = result.read_bytes()
            filename = result.name
            try:
                record = ResultStore().add(result, operation, len(files))
                result_id = record['id']
            except (OSError, ValueError):
                logging.exception('Could not retain this result for local history')
                result_id = ''  # A storage issue must not break a successful conversion.
            return Response(content=body, media_type=_media_type(result),
                            headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}",
                                     'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store',
                                     'X-FileDesk-Result-Id': result_id,
                                     'X-FileDesk-Filename': quote(filename)})
    except Exception as exc:
        _fail(exc)
    finally:
        _close_files(files)


@app.get('/api/history')
def history_list():
    return {'items': ResultStore().list()}


@app.get('/api/history/{result_id}/download')
def history_download(result_id: str):
    found = ResultStore().get(result_id)
    if found is None:
        raise HTTPException(status_code=404, detail='该结果已过期或已清理，请重新转换。')
    row, path = found
    content_type = _media_type(path)
    return FileResponse(path, filename=row['name'], media_type=content_type,
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                 'X-FileDesk-Filename': quote(row['name'])})


@app.delete('/api/history')
def history_clear():
    ResultStore().clear()
    return {'ok': True}


@app.get('/')
def homepage():
    return FileResponse(WEB / 'index.html', headers={'Cache-Control': 'no-store'})


app.mount('/assets', StaticFiles(directory=str(WEB)), name='assets')


@app.post('/api/jobs', status_code=202)
def job_start(operation: str = Form(...), options: str = Form('{}'), files: list[UploadFile] = File(...)):
    """Upload once, process in a bounded worker, poll stages in the UI.

    Files are saved to a temporary folder before returning the HTTP response;
    otherwise FastAPI will close UploadFile handles before the worker reads them.
    """
    if operation not in OPERATIONS:
        raise HTTPException(status_code=400, detail='不支持此操作')
    if not 1 <= len(files) <= MAX_FILES:
        raise HTTPException(status_code=400, detail=f'每次最多处理 {MAX_FILES} 个文件')
    try:
        decoded = json.loads(options)
        if not isinstance(decoded, dict):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail='参数格式错误') from exc
    # Reject queue overload before spending memory/disk on uploads.
    temp_dir = tempfile.mkdtemp(prefix='filedesk-job-')
    staged = []
    total = 0
    try:
        for i, upload in enumerate(files):
            filename = (upload.filename or '').replace('\\','/').split('/')[-1]
            suffix = Path(filename).suffix.lower()
            if not re.fullmatch(r'\.[a-z0-9]{1,8}', suffix):
                raise FileDeskError('文件扩展名不合法')
            path = Path(temp_dir) / f'upload_{i:02d}{suffix}'
            size = 0
            with path.open('wb') as destination:
                while chunk := upload.file.read(1024 * 1024):
                    size += len(chunk)
                    total += len(chunk)
                    if size > MAX_EACH or total > MAX_TOTAL:
                        raise FileDeskError('文件太大：单个不超过 65 MB，批次不超过 200 MB')
                    destination.write(chunk)
            if not size:
                raise FileDeskError(f'空文件：{filename}')
            staged.append((path,filename))

        def worker(folder: str, progress, job_id: str):
            from time import monotonic
            deadline = monotonic() + 12 * 60
            def checked_progress(message, percentage):
                jobs.check_cancelled(job_id)
                if monotonic() > deadline:
                    raise FileDeskError('处理超过 12 分钟，已停止当前批次。建议按较小范围分批处理。')
                progress(message,percentage)
            handles = []
            try:
                loaded = []
                for path, name in staged:
                    file = path.open('rb')
                    handles.append(file)
                    loaded.append(UploadFile(file=file,filename=name))
                with tempfile.TemporaryDirectory(prefix='filedesk-process-') as processing_folder:
                    result = _run(operation,options,loaded,Path(processing_folder),checked_progress)
                    row = ResultStore().add(result,operation,len(loaded))
                    return row['id'], result.name
            finally:
                for file in handles:
                    file.close()

        try:
            return jobs.submit(operation,temp_dir,worker)
        except ValueError as exc:
            raise FileDeskError(str(exc)) from exc
    except Exception as exc:
        shutil.rmtree(temp_dir,ignore_errors=True)
        _fail(exc)
    finally:
        _close_files(files)


@app.get('/api/jobs/{job_id}')
def job_status(job_id: str):
    if not re.fullmatch('[a-f0-9]{32}',job_id):
        raise HTTPException(status_code=404,detail='任务不存在')
    result = jobs.get(job_id)
    if result is None:
        raise HTTPException(status_code=404,detail='任务不存在或已过期')
    return result


@app.get('/api/jobs/{job_id}/download')
def job_download(job_id: str):
    job = jobs.get(job_id)
    if job is None or job['status'] != 'completed':
        raise HTTPException(status_code=404,detail='任务尚未完成或已过期')
    return history_download(job['result_id'])


@app.post('/api/jobs/{job_id}/cancel')
def job_cancel(job_id: str):
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise HTTPException(status_code=404, detail='任务不存在')
    result = jobs.cancel(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail='任务不存在或已过期')
    return result


@app.post('/api/preview/pdf')
def preview_pdf(file: UploadFile = File(...)):
    """Create a temporary, local page-preview session."""
    try:
        token, count = PREVIEWS.add_pdf(file.file, file.filename or '')
        return {'id': token, 'pages': count}
    except Exception as exc:
        _fail(exc)
    finally:
        file.file.close()


@app.get('/api/preview/{preview_id}/pages/{page_number}')
def preview_page(preview_id: str, page_number: int, size: str = 'full'):
    if size not in ('full', 'thumb'):
        raise HTTPException(status_code=400, detail='预览尺寸不合法')
    if PREVIEWS.read(preview_id) is None:
        raise HTTPException(status_code=404, detail='预览已过期，请重新打开')
    try:
        data = PREVIEWS.render(preview_id, page_number, thumbnail=size == 'thumb')
        return Response(content=data, media_type='image/jpeg',
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except Exception as exc:
        _fail(exc)


@app.delete('/api/preview/{preview_id}')
def preview_close(preview_id: str):
    PREVIEWS.remove(preview_id)
    return {'ok': True}
