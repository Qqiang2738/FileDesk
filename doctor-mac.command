#!/bin/bash
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
  .venv/bin/python -m filedesk.diagnostics
elif command -v python3 >/dev/null 2>&1; then
  python3 -m filedesk.diagnostics
else
  echo '未找到 Python 3。请先安装 Python 3.11 或更新版本。'
fi
echo ''
read -r -p '按回车键关闭本窗口…' _
