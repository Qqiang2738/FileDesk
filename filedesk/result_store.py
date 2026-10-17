"""Private, bounded, persistent local result history (no source file copies)."""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from threading import RLock

_HISTORY_LOCK = RLock()

MAX_ENTRIES = 20
MAX_HISTORY_BYTES = 600 * 1024 * 1024
MAX_AGE = 7 * 24 * 3600


def default_history_dir() -> Path:
    import platform
    if os.environ.get('FILEDESK_HISTORY_DIR'):
        return Path(os.environ['FILEDESK_HISTORY_DIR']).expanduser()
    if platform.system() == 'Darwin':
        return Path.home() / 'Library' / 'Application Support' / 'FileDesk' / 'history'
    if platform.system() == 'Windows':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FileDesk' / 'history'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'FileDesk' / 'history'


class ResultStore:
    def __init__(self, base: Path | None = None):
        self.base = base or default_history_dir()
        self.base.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            self.base.chmod(0o700)
        except OSError:
            pass
        self.manifest = self.base / 'manifest.json'

    def _load(self):
        try:
            data = json.loads(self.manifest.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return [e for e in data if isinstance(e, dict) and re.fullmatch(r'[a-f0-9]{32}', str(e.get('id', '')))]
        except (OSError, ValueError):
            pass
        return []

    def _save(self, items):
        # Atomic replace, with restrictive permissions for local confidential outputs.
        handle, name = tempfile.mkstemp(prefix='.manifest-', dir=self.base)
        with os.fdopen(handle, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False)
        os.chmod(name, 0o600)
        os.replace(name, self.manifest)

    def _path(self, row):
        suffix = str(row.get('extension', '')).lower()
        if suffix not in ('.pdf', '.docx', '.zip', '.png', '.jpg', '.jpeg', '.webp', '.csv'):
            return None
        return self.base / (row['id'] + suffix)

    def _prune(self, rows):
        now = time.time()
        kept = []
        total = 0
        for row in rows:
            path = self._path(row)
            if path is None:
                continue
            try:
                actual_size = path.stat().st_size
                age = now - float(row.get('created_at', 0))
            except (OSError, ValueError, TypeError):
                continue
            if age > MAX_AGE or len(kept) >= MAX_ENTRIES or total + actual_size > MAX_HISTORY_BYTES:
                path.unlink(missing_ok=True)
                continue
            row['size'] = actual_size
            kept.append(row)
            total += actual_size
        return kept

    def list(self):
        with _HISTORY_LOCK:
            items = self._prune(self._load())
            self._save(items)
            return items

    def add(self, path: Path, action: str, count: int):
        with _HISTORY_LOCK:
            return self._add_locked(path, action, count)

    def _add_locked(self, path: Path, action: str, count: int):
        extension = path.suffix.lower()
        if extension not in ('.pdf', '.docx', '.zip', '.png', '.jpg', '.jpeg', '.webp', '.csv'):
            raise ValueError('unsupported output type')
        record = {'id': uuid.uuid4().hex, 'name': path.name, 'action': action[:90],
                  'count': int(count), 'created_at': time.time(), 'extension': extension,
                  'size': path.stat().st_size}
        destination = self._path(record)
        shutil.copyfile(path, destination)
        destination.chmod(0o600)
        try:
            items = self._prune([record, *self._load()])
            self._save(items)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        if not any(row['id'] == record['id'] for row in items):
            raise ValueError('history capacity exceeded')
        return record

    def get(self, identifier: str):
        if not re.fullmatch(r'[a-f0-9]{32}', identifier):
            return None
        with _HISTORY_LOCK:
            row = next((item for item in self.list() if item['id'] == identifier), None)
            if not row:
                return None
            return row, self._path(row)

    def delete(self, identifier: str) -> bool:
        if not re.fullmatch(r'[a-f0-9]{32}', identifier):
            return False
        with _HISTORY_LOCK:
            rows = self._load()
            found = [row for row in rows if row['id'] == identifier]
            if not found:
                return False
            for row in found:
                path = self._path(row)
                if path is not None:
                    path.unlink(missing_ok=True)
            self._save([row for row in rows if row['id'] != identifier])
            return True

    def clear(self):
        with _HISTORY_LOCK:
            rows = self._load()
            for row in rows:
                path = self._path(row)
                if path is not None:
                    path.unlink(missing_ok=True)
            self._save([])
