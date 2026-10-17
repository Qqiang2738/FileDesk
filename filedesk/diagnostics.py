"""Read-only environment checks for Mac/other local-browser FileDesk users.

Run: python -m filedesk.diagnostics
No input documents, filenames or history records are read or uploaded.
"""
from __future__ import annotations

import importlib.metadata
import platform
import sys
import tempfile
from pathlib import Path

from .engine import find_libreoffice
from .result_store import default_history_dir
from .version import VERSION

DEPENDENCIES = {
    'fastapi': 'fastapi', 'uvicorn': 'uvicorn', 'python-multipart': 'python-multipart',
    'pypdf': 'pypdf', 'pillow': 'Pillow', 'pypdfium2': 'pypdfium2',
    'python-docx': 'python-docx', 'reportlab': 'reportlab', 'pymupdf': 'PyMuPDF',
}


def check_environment():
    checks = []
    def add(kind, label, detail):
        checks.append((kind, label, detail))

    if sys.version_info >= (3, 11):
        add('OK', 'Python', platform.python_version())
    else:
        add('ERROR', 'Python', '需要 3.11 或更高版本')
    for label, package in DEPENDENCIES.items():
        try:
            add('OK', label, importlib.metadata.version(package))
        except importlib.metadata.PackageNotFoundError:
            add('ERROR', label, '尚未安装；请重新运行 start-mac.command')
    libreoffice = find_libreoffice()
    add('OK' if libreoffice else 'WARN', 'LibreOffice',
        '已检测到' if libreoffice else '未检测到；旧 XLS 和部分 Office 转换可能不可用')
    try:
        # A temporary throwaway directory tests the actual history location without
        # reading user's private history manifest or any document contents.
        folder = default_history_dir()
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix='.filedesk-check-', dir=folder):
            pass
        add('OK', '本地历史存储', '可写')
    except OSError:
        add('ERROR', '本地历史存储', '不可写，无法保存结果历史')
    try:
        with tempfile.TemporaryDirectory(prefix='filedesk-check-') as root:
            test = Path(root) / 'check'
            test.write_text('ok', encoding='utf-8')
        add('OK', '系统临时目录', '可写')
    except OSError:
        add('ERROR', '系统临时目录', '不可写，文件转换无法进行')
    return checks


def main() -> int:
    print(f'\n文序 FileDesk V{VERSION} · 本机环境检查')
    print(f'系统：{platform.system()} / {platform.machine()}')
    checks = check_environment()
    for kind, name, value in checks:
        print(f'[{kind}] {name}: {value}')
    failed = any(kind == 'ERROR' for kind, _, _ in checks)
    print('结果：' + ('发现需要修复的问题' if failed else '基础环境正常（不等于文件转换质量验收通过）'))
    print('本诊断不读取或上传任何用户工作文件。\n')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
