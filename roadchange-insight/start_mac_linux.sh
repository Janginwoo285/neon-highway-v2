#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
if [ ! -d .venv ];then python3 -m venv .venv;fi
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
