"""Local-only, temporary, page-at-a-time PDF preview sessions.

No document data is sent to an external service; only the current browser talks
with the loopback server. Preview uploads are not part of conversion history.
"""
from __future__ import annotations

import re
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .engine import FileDeskError

MAX_PREVIEW_BYTES = 65 * 1024 * 1024
MAX_PREVIEW_PAGES = 1200
PREVIEW_TTL = 15 * 60
MAX_SESSIONS = 12
_ID = re.compile(r'^[a-f0-9]{32}$')


@dataclass
class PreviewEntry:
    path: Path
    pages: int
    name: str
    created: float


class PreviewStore:
    """Bounded ephemeral storage, independent of persistent conversion results."""

    def __init__(self, root: Path | None = None, ttl: int = PREVIEW_TTL):
        self._temporary = tempfile.TemporaryDirectory(prefix='filedesk-preview-') if root is None else None
        self.root = Path(root) if root else Path(self._temporary.name)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self._lock = threading.RLock()
        self._items: dict[str, PreviewEntry] = {}

    def _purge_locked(self):
        now = time.monotonic()
        for token, entry in list(self._items.items()):
            if now-entry.created >= self.ttl:
                self._delete_locked(token)

    def _delete_locked(self, token: str):
        entry = self._items.pop(token, None)
        if entry:
            entry.path.unlink(missing_ok=True)

    def add_pdf(self, uploaded, filename: str) -> tuple[str, int]:
        try:
            import pymupdf
        except ImportError as exc:
            raise FileDeskError('PDF 预览组件未安装，请重新运行 start-mac.command。') from exc
        if Path(filename).suffix.lower() != '.pdf':
            raise FileDeskError('目前只支持 PDF 页面预览。')
        token = uuid.uuid4().hex
        destination = self.root / f'{token}.pdf'
        try:
            size = 0
            with destination.open('wb') as out:
                while chunk := uploaded.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_PREVIEW_BYTES:
                        raise FileDeskError('PDF 超过 65 MB，无法预览。可以仍然尝试处理文件。')
                    out.write(chunk)
            if not size:
                raise FileDeskError('PDF 文件为空。')
            with destination.open('rb') as fp:
                if not fp.read(5) == b'%PDF-':
                    raise FileDeskError('文件内容不是有效的 PDF。')
            with pymupdf.open(str(destination)) as doc:
                if doc.needs_pass:
                    raise FileDeskError('此 PDF 已加密，需先解除密码保护才能预览。')
                count = len(doc)
                if count == 0 or count > MAX_PREVIEW_PAGES:
                    raise FileDeskError(f'仅支持预览 1–{MAX_PREVIEW_PAGES} 页的 PDF。')
            with self._lock:
                self._purge_locked()
                if len(self._items) >= MAX_SESSIONS:
                    # Prefer clearing the oldest preview; conversion jobs are untouched.
                    oldest = min(self._items, key=lambda id_: self._items[id_].created)
                    self._delete_locked(oldest)
                self._items[token] = PreviewEntry(destination, count, filename, time.monotonic())
            return token, count
        except FileDeskError:
            destination.unlink(missing_ok=True)
            raise
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise FileDeskError('无法读取该 PDF，请检查文件是否损坏。') from exc

    def read(self, token: str) -> PreviewEntry | None:
        if not _ID.fullmatch(token):
            return None
        with self._lock:
            self._purge_locked()
            return self._items.get(token)

    def remove(self, token: str) -> None:
        if not _ID.fullmatch(token):
            return
        with self._lock:
            self._delete_locked(token)

    def render(self, token: str, page_index: int, thumbnail: bool = False) -> bytes:
        try:
            import pymupdf
        except ImportError as exc:
            raise FileDeskError('PDF 预览引擎缺失。') from exc
        entry = self.read(token)
        if not entry:
            raise FileDeskError('预览已过期，请重新打开。')
        if page_index < 0 or page_index >= entry.pages:
            raise FileDeskError('页码超出范围。')
        try:
            with pymupdf.open(str(entry.path)) as doc:
                page = doc[page_index]
                # Cap the longest rendered side to avoid huge memory allocation.
                maximum = 220 if thumbnail else 1420
                scale = min(2.0, maximum / max(page.rect.width, page.rect.height, 1))
                pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale),
                                      colorspace=pymupdf.csRGB, alpha=False)
                return pix.tobytes('jpeg', jpg_quality=78 if thumbnail else 88)
        except Exception as exc:
            raise FileDeskError('预览这一页失败，请尝试下一页。') from exc


PREVIEWS = PreviewStore()
