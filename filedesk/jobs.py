"""Bounded local background tasks with cooperative cancellation.

Cancellation applies between conversion stages. A third-party synchronous converter
that does not report progress cannot be interrupted safely by this layer.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import RLock
from time import time
from typing import Callable
import logging
import secrets
import shutil

MAX_PENDING = 2
TTL_SECONDS = 60 * 60
_LOCK = RLock()
_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix='filedesk-convert')
_JOBS: dict[str, 'Job'] = {}
TERMINAL = ('completed', 'failed', 'cancelled')


class TaskCancelled(Exception):
    """Expected cooperative cancellation, not a processing error."""


@dataclass
class Job:
    id: str
    operation: str
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)
    status: str = 'queued'
    stage: str = '等待开始'
    percent: int = 0
    error: str = ''
    result_id: str = ''
    filename: str = ''
    cancel_requested: bool = False


def _public(job: Job) -> dict:
    return {key: getattr(job, key) for key in
            ('id', 'operation', 'status', 'stage', 'percent', 'error', 'filename', 'result_id', 'cancel_requested')}


def update(job_id: str, stage: str, percent: int | None = None, status: str | None = None) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None or job.status in TERMINAL:
            return
        job.stage = str(stage)[:150]
        if percent is not None:
            job.percent = max(job.percent, min(100, max(0, int(percent))))
        if status:
            job.status = status
        job.updated_at = time()


def get(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return _public(job) if job else None


def check_cancelled(job_id: str) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None or job.cancel_requested or job.status == 'cancelled':
            raise TaskCancelled()


def cancel(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        if job.status in TERMINAL:
            return _public(job)
        job.cancel_requested = True
        job.updated_at = time()
        if job.status == 'queued':
            job.status = 'cancelled'
            job.stage = '已取消'
        else:
            job.stage = '正在停止（当前步骤结束后）'
        return _public(job)


def submit(operation: str, temp_folder: str,
           worker: Callable[[str, Callable[[str, int], None], str], tuple[str, str]],
           ) -> dict:
    with _LOCK:
        now = time()
        for key, existing in list(_JOBS.items()):
            if existing.status in TERMINAL and now - existing.updated_at > TTL_SECONDS:
                del _JOBS[key]
        pending = sum(j.status in ('queued', 'running') for j in _JOBS.values())
        if pending >= MAX_PENDING:
            raise ValueError('已有文件任务正在处理，请等待完成后再提交。')
        job_id = secrets.token_hex(16)
        job = Job(id=job_id, operation=operation)
        _JOBS[job_id] = job

    def run():
        try:
            check_cancelled(job_id)
            update(job_id, '准备文件', 2, 'running')
            def report(message: str, percent: int) -> None:
                check_cancelled(job_id)
                update(job_id, message, percent)
            result_id, filename = worker(temp_folder, report, job_id)
            with _LOCK:
                if job.cancel_requested:
                    # If cancellation raced with saving the result, discard it.
                    from .result_store import ResultStore
                    ResultStore().delete(result_id)
                    raise TaskCancelled()
                job.result_id = result_id
                job.filename = filename
                job.status = 'completed'
                job.stage = '处理完成'
                job.percent = 100
                job.updated_at = time()
        except TaskCancelled:
            with _LOCK:
                job.status = 'cancelled'
                job.stage = '已取消'
                job.updated_at = time()
        except Exception as exc:
            from .engine import FileDeskError
            if not isinstance(exc, FileDeskError):
                logging.exception('Background FileDesk conversion failed')
            error = str(exc) if isinstance(exc, FileDeskError) else '文件处理失败。可尝试缩小批次或检查源文件。'
            with _LOCK:
                job.error = error
                job.status = 'failed'
                job.stage = '处理失败'
                job.percent = 100
                job.updated_at = time()
        finally:
            shutil.rmtree(temp_folder, ignore_errors=True)

    try:
        _POOL.submit(run)
    except Exception:
        with _LOCK:
            del _JOBS[job_id]
        raise
    return _public(job)
