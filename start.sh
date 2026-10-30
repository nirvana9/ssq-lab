#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
printf '\nSSQ Lab 已启动：http://127.0.0.1:8765\n按 Ctrl+C 停止服务。\n'
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
