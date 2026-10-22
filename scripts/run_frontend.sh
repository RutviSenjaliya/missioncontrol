#!/usr/bin/env bash
# React app at http://127.0.0.1:5173 (proxies /api to the backend)
set -euo pipefail
cd "$(dirname "$0")/../frontend"
exec npm run dev -- --host 127.0.0.1
