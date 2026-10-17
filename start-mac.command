#!/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo '请先安装 Python 3.11 或更高版本'; read -r; exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' ; then
  echo '文序需要 Python 3.11 或更新版本。请先安装新版 Python 后重新启动。'
  read -r
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
# Avoid re-installing all packages each time the tool opens. Re-install on
# first launch, or when requirements.txt changes.
SIGNATURE=$(shasum -a 256 requirements.txt | awk '{print $1}')
STAMP=.venv/.filedesk-requirements
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$SIGNATURE" ]; then
  echo '首次启动或依赖更新：正在检查 Python 依赖…'
  .venv/bin/python -m pip install -r requirements.txt
  printf '%s' "$SIGNATURE" > "$STAMP"
fi
.venv/bin/python main.py
