#!/usr/bin/env bash
# One-time setup: Python venv + deps, database migration, demo seed, frontend deps.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
[ -f backend/.env ] || cp .env.example backend/.env
cd backend
alembic upgrade head
python -m app.cli seed --demo
cd ../frontend
npm ci
echo "Setup complete. Start: ./scripts/run_mcp_server.sh, ./scripts/run_backend.sh, ./scripts/run_frontend.sh"
