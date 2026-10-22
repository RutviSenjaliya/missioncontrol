#!/usr/bin/env bash
# Self-hosted MCP server (Streamable HTTP) at http://127.0.0.1:8001/mcp
set -euo pipefail
cd "$(dirname "$0")/../backend"
[ -d ../.venv ] && . ../.venv/bin/activate
exec python -m app.mcp_server.server
