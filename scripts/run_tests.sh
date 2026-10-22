#!/usr/bin/env bash
# Backend (unit, API, MCP protocol, end-to-end, failure) + frontend (typecheck, unit, build) tests.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] && . .venv/bin/activate
(cd backend && python -m pytest -q -p no:warnings)
(cd frontend && npm run typecheck && npm test && npm run build)
