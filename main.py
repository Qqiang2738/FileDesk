"""Start FileDesk on your own computer: python main.py"""
from __future__ import annotations

import os
import socket
import threading
import webbrowser

import uvicorn

from filedesk.version import VERSION
from filedesk.instance import InstanceLock, AlreadyRunning, find_local_filedesk


def pick_available_port(preferred: int) -> int:
    candidates = [preferred] + [port for port in range(8765, 8786) if port != preferred]
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError('本机端口 8765–8785 均被占用，请关闭旧版文序或调整 FILEDESK_PORT。')


def main():
    port = int(os.getenv('FILEDESK_PORT', '8765'))
    running = find_local_filedesk(port)
    if running:
        old_port, version = running
        url = f'http://127.0.0.1:{old_port}'
        if version == VERSION:
            print(f'\n文序 V{VERSION} 已在运行：{url}')
            if os.getenv('FILEDESK_NO_BROWSER') != '1':
                webbrowser.open(url)
            return
        raise RuntimeError(
            f'检测到旧版文序 V{version} 正在运行（{url}）。'
            '请先在旧版终端按 Control+C 完全退出，再启动 V1.0，避免历史结果写入冲突。'
        )

    try:
        with InstanceLock():
            available = pick_available_port(port)
            if available != port:
                print(f'\n提示：端口 {port} 正被其他程序占用，将改用端口 {available}。')
                port = available
            print(f'\n文序 FileDesk V{VERSION} 已启动： http://127.0.0.1:{port}')
            print('文件只在本机处理；按 Ctrl+C 结束。\n')
            if os.getenv('FILEDESK_NO_BROWSER') != '1':
                threading.Timer(1.3, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
            uvicorn.run('filedesk.server:app', host='127.0.0.1', port=port, log_level='warning')
    except AlreadyRunning as exc:
        raise RuntimeError(str(exc)) from exc


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f'\n无法启动：{error}\n')
        raise SystemExit(1)
