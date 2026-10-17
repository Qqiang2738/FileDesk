"""Best-effort local singleton for a standalone, loopback-only file workstation.

The OS lock protects against two V1.x processes writing the same history data.
Legacy FileDesk services are detected separately by their /api/health endpoint.
"""
from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener

from .result_store import default_history_dir


class AlreadyRunning(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, path: Path | None = None):
        self.path = path or (default_history_dir().parent / '.filedesk.instance.lock')
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.handle = open(self.path, 'a+b')
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        try:
            if os.name == 'nt':
                import msvcrt
                if not self.path.stat().st_size:
                    self.handle.write(b'0')
                    self.handle.flush()
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self.handle.close()
            self.handle = None
            raise AlreadyRunning('文序已在本机运行，请使用已有网页窗口。') from exc
        return self

    def __exit__(self, *_):
        if self.handle is not None:
            try:
                if os.name == 'nt':
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
                self.handle = None


def _is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(.08)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def find_local_filedesk(preferred: int = 8765) -> tuple[int, str] | None:
    """Discover older running versions without sending traffic off this computer."""
    seen = set()
    opener = build_opener(ProxyHandler({}))
    for port in [preferred, *range(8765, 8786)]:
        if port in seen or not (1 <= port <= 65535):
            continue
        seen.add(port)
        if not _is_open(port):
            continue
        url = f'http://127.0.0.1:{port}/api/health'
        try:
            with opener.open(Request(url, headers={'Accept': 'application/json'}), timeout=.4) as response:
                data = json.loads(response.read(2048).decode('utf-8'))
            if data.get('status') == 'ok' and data.get('local_only') is True and isinstance(data.get('version'), str):
                return port, data['version']
        except (OSError, ValueError, UnicodeError, TypeError):
            continue
    return None
