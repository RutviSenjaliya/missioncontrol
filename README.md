# MissionControl

**An AI project agent that remembers your project, does the work through real MCP tools, and proves what happened.**

Amazon Developer Hackathon 2026 · Alexa+ track · self-hosted MCP server route (Streamable HTTP)

![Mission with verification evidence](docs/screenshots/mission-verified.png)

## Why

Teams using AI assistants over weeks keep re-explaining their project, and “done” is just a sentence. MissionControl stores project knowledge as structured memory, retrieves it in a fresh session, executes missions through a self-hosted MCP server, and marks a mission completed only after reading the result back from the database and checking it.

**The loop:** persistent project knowledge → context-aware plan → MCP tool execution → verified result → updated project history.

## What works today

| Capability | What you can see |
|---|---|
| Persistent memory | Goals, stack, constraints, procedures, decisions and tasks with source, confirmation status and supersession. Memory Center to confirm, edit and delete. |
| Fresh-session context | Every mission retrieves current context through MCP; superseded facts (e.g. an old “use Flask” decision) are excluded. |
| Missions | Handoff report, sprint plan, progress summary, show open tasks, search memory, add task, update task, record decision. |
| Real MCP execution | 8 tools on a self-hosted MCP server, protocol 2025-11-25 over Streamable HTTP. The agent has no other way to act. |
| Verification | Reports are read back and checked section by section, and every referenced task and decision must exist. Task and decision changes are read back and compared. |
| Approval | Changes to project records wait for your approval, enforced by the MCP server. |
| Honest failure | MCP outage, timeout, tool error, failed verification or an unsupported request end as Failed or Partially completed with a reason. Never a false green. |
| Timeline | Every real operation is an event with recorded data. |

## Architecture

```mermaid
flowchart LR
    UI[React UI] -->|REST /api| API[FastAPI + agent]
    API -->|MCP client · Streamable HTTP| MCP[Self-hosted MCP server]
    API --> DB[(PostgreSQL)]
    MCP --> DB
```

Details: [docs/architecture.md](docs/architecture.md) · MCP: [docs/mcp-integration.md](docs/mcp-integration.md) · Product: [docs/PRD.md](docs/PRD.md) · API: [docs/api.md](docs/api.md) · Decisions: [decisions.md](decisions.md) · Submission text: [docs/SUBMISSION.md](docs/SUBMISSION.md)

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript 5.6, Vite 5 |
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, Alembic |
| MCP | Official MCP Python SDK 1.30.0 (FastMCP), Streamable HTTP |
| Database | PostgreSQL 16 (SQLite supported for tests) |
| Planner | Deterministic rule-based planner (default); Amazon Bedrock planner (optional) |
| Tests | pytest, Vitest, Playwright (manual live run) |

## Quick start

Prerequisites: Python 3.12, Node.js 20+, Docker (for PostgreSQL) or a local PostgreSQL 16.

```bash
git clone <your-repo-url> missioncontrol && cd missioncontrol
docker compose up -d db              # PostgreSQL on localhost:5432
./scripts/setup.sh                   # venv, pip install, backend/.env, migrations, demo data, npm ci
```

Start the three services in separate terminals:

```bash
./scripts/run_mcp_server.sh          # MCP server  http://127.0.0.1:8001/mcp
./scripts/run_backend.sh             # API         http://127.0.0.1:8000  (docs at /docs)
./scripts/run_frontend.sh            # Web app     http://127.0.0.1:5173
```

Open http://127.0.0.1:5173 and sign in with `DEMO_USER_TOKEN` from `backend/.env` (default `change-me-demo-token`; change it). The seeded **Campus Events App** project is ready for missions.

Manual setup instead of `setup.sh`:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example backend/.env
cd backend && alembic upgrade head && python -m app.cli seed --demo && cd ..
cd frontend && npm ci && cd ..
```

Create more users (for isolation tests or teammates): `cd backend && python -m app.cli create-user "Name"` prints a token once.

## Verify it yourself

```bash
./scripts/run_tests.sh                       # 37 backend tests + frontend typecheck, unit tests, build
python scripts/smoke_test.py --token change-me-demo-token   # live end-to-end against running services (17 checks)
```

Run the backend suite on PostgreSQL:

```bash
createdb missioncontrol_test   # or: docker compose exec db createdb -U missioncontrol missioncontrol_test
cd backend && TEST_DATABASE_URL=postgresql+psycopg://missioncontrol:missioncontrol@localhost:5432/missioncontrol_test pytest -q
```

Connect any MCP client (e.g. MCP Inspector) to `http://127.0.0.1:8001/mcp` with transport *Streamable HTTP* and header `Authorization: Bearer <token>`. Results of the last full run: [docs/verification-report.md](docs/verification-report.md).

## Example missions

Type these in a project’s Missions tab:

| Request | What happens |
|---|---|
| Create a project handoff report | Report from stored data → saved → read back → 10 checks → Verified |
| Create a sprint plan from our goals, decisions and unfinished tasks | Sprint report with goal, planned tasks, decisions, constraints, blockers |
| Summarize our progress | Includes completed tasks and earlier missions (continuity) |
| Show open tasks | Read-only; no verification needed |
| Add task: Record the demo video (high priority) | Waits for approval → creates → reads back |
| Mark task #3 done | Waits for approval → updates → reads back |
| Record decision: Use PostgreSQL - one shared source of truth, supersedes #2 | Waits for approval → records → checks #2 is no longer current |
| Search: deployment budget | Ranked memory search |

## Using Amazon Bedrock as the planner (optional)

```bash
pip install boto3
# backend/.env
AI_PROVIDER=bedrock
BEDROCK_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.nova-lite-v1:0
AWS_ACCESS_KEY_ID=<from your client>
AWS_SECRET_ACCESS_KEY=<from your client>
```

Put Bedrock-only IAM keys in `backend/.env` as `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (the file is git-ignored), or leave them empty to use the standard AWS credential chain. The model’s plan goes through the same validation as the default planner (known tools only, forced project id, verification after writes, approval decided by the app). This path is implemented but was **not verified** in the build environment (no credentials).

## Repository layout

```
backend/
  app/
    api/            REST routes and auth dependency
    agent/          orchestrator, state machine, planners
    mcp_client/     MCP client (Streamable HTTP)
    mcp_server/     self-hosted MCP server and tools
    models/         SQLAlchemy models
    services/       memory, decisions, tasks, context, reports, auth
    cli.py          seed and create-user
  migrations/       Alembic
  tests/            unit, API, MCP protocol, end-to-end, failure tests
frontend/src/       pages, components, API client, styles
docs/               PRD, architecture, MCP, API, demo script, tasks, verification report, screenshots
scripts/            setup, run, test and smoke-test scripts
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Missions fail with “MCP server unavailable” | Start `./scripts/run_mcp_server.sh`; check `MCP_SERVER_URL` in `backend/.env`. The Connections screen shows the live status. |
| `connection refused` on port 5432 | `docker compose up -d db`, or point `DATABASE_URL` at your PostgreSQL. |
| Sign-in says “Invalid token” | Use `DEMO_USER_TOKEN` from `backend/.env` and run `python -m app.cli seed` after changing it. |
| UI says it can’t reach the API | Start the backend on port 8000, or set `VITE_API_PROXY` before `npm run dev`. |
| MCP client rejected when the server runs on a public host name | Configure the MCP SDK transport-security allowed hosts for that host. |

## Publish to GitHub

```bash
git remote add origin https://github.com/<you>/missioncontrol.git
git push -u origin main
```

Make the repository public (or grant judges access) and check it from a logged-out browser.

## Known limitations

The default planner handles the request types listed above; anything else fails honestly with suggestions. Memory search is keyword-based, not semantic. Projects are single-owner (membership exists in the schema, no invitation UI). No rate limiting. Bedrock planner unverified. `npm audit` lists advisories in dev-only tooling (Vite/Vitest dev server, bound to 127.0.0.1); production browser packages report none.

## Future work

Semantic memory search, team roles and invitations, MCP resources for reports, Bedrock planner as default once verified, deployment templates.

## License

MIT — see [LICENSE](LICENSE).
