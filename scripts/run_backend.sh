#!/usr/bin/env bash
# FastAPI backend at http://127.0.0.1:8000 (API docs: /docs)
set -euo pipefail
cd "$(dirname "$0")/../backend"
[ -d ../.venv ] && . ../.venv/bin/activate
exec uvicorn app.main:app --host "${API_HOST:-127.0.0.1}" --port "${API_PORT:-8000}"
