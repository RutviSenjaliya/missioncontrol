# End-to-end task list

Status key: **Done** = implemented and verified (evidence column). **Team** = needs a person, an account or information not available in the build environment.

## Phase 1 — Requirements and architecture

| ID | Task | Status | Evidence |
|---|---|---|---|
| T01 | Read hackathon rules, judging criteria and submission fields | Done | Official rules reviewed 22 Oct 2026; deadline 23 Oct 2026 12:00 PT |
| T02 | Confirm required MCP spec version | Done | Rules require 2025-11-25+; server upgraded and negotiates `2025-11-25` (SDK 1.30.0) |
| T03 | Verify SDK supports Streamable HTTP | Done | `test_raw_jsonrpc_initialize_and_list` |
| T04 | Freeze MVP scope | Done | PRD §5 |
| T05 | Design database schema | Done | architecture.md §4, `migrations/versions/0001_initial_schema.py` |
| T06 | Agree API contract | Done | api.md, `frontend/src/lib/types.ts` |
| T07 | Agree MCP tool contracts | Done | mcp-integration.md |
| T08 | Repository structure, .gitignore, .env.example | Done | repo root |
| T09 | Check AI provider access | **Team** | Rule-based planner works offline; Bedrock needs AWS credentials |

## Phase 2 — Backend foundation

| ID | Task | Status | Evidence |
|---|---|---|---|
| T10 | FastAPI app, config, health endpoint | Done | `GET /api/health` |
| T11 | PostgreSQL + SQLAlchemy | Done | Full suite passes on PostgreSQL 16 |
| T12 | Models + Alembic migrations | Done | `alembic upgrade head` + `alembic check` clean |
| T13 | Project APIs | Done | `test_project_crud_and_validation` |
| T14 | Memory service with provenance and supersession | Done | `test_memory_supersession_and_search_excludes_outdated` |
| T15 | Task and mission storage | Done | `test_task_idempotency_and_cross_project_supersede_rejected` |
| T16 | Project-level authorization | Done | `test_project_isolation_between_users` |
| T17 | Seed script with demo data | Done | `python -m app.cli seed --demo` |
| T18 | Backend unit and API tests | Done | `test_services.py`, `test_api.py` |

## Phase 3 — MCP server

| ID | Task | Status | Evidence |
|---|---|---|---|
| T19 | MCP server on Streamable HTTP | Done | `scripts/run_mcp_server.sh` |
| T20 | Initialization, capability negotiation, discovery | Done | raw JSON-RPC test |
| T21 | `get_project_context`, `search_memory` | Done | `test_sdk_client_discovers_and_reads` |
| T22 | `list_open_tasks`, `create_task`, `update_task` | Done | E2E approval tests |
| T23 | `record_decision` | Done | `test_update_task_and_decision_supersession_missions` |
| T24 | `generate_project_report`, `verify_report` | Done | `test_report_tools_persist_to_shared_database_and_are_idempotent` |
| T25 | Validation, authorization, structured errors | Done | `test_invalid_input_unknown_tool_and_auth_errors` |
| T26 | Protocol tests with a real client | Done | `test_mcp_protocol.py` (6 tests) |

## Phase 4 — Agent and orchestration

| ID | Task | Status | Evidence |
|---|---|---|---|
| T27 | AI provider abstraction | Done | `agent/providers.py`; Bedrock path implemented, **not verified** without credentials |
| T28 | Mission state machine | Done | `test_state_machine_rules` |
| T29 | Execution event logging | Done | Timeline in every E2E test |
| T30 | Context retrieval for missions | Done | `context_retrieved` event |
| T31 | Planner with success conditions | Done | Plan panel; `validate_plan` |
| T32 | Agent → MCP client | Done | Agent has no other execution path |
| T33 | Server-side approval | Done | `test_write_tools_require_approved_mission`, `test_rejected_mission_changes_nothing` |
| T34 | Limits, retries, idempotency | Done | `test_execution_limit`, `test_tool_timeout_is_retried_then_fails` |
| T35 | Verification by read-back | Done | `test_verification_failure_gives_partial_not_success` |
| T36 | Outcomes stored as memory | Done | continuity assertion in acceptance test |

## Phase 5 — Frontend

| ID | Task | Status | Evidence |
|---|---|---|---|
| T37 | React + TypeScript + Vite + design tokens | Done | `npm run build` |
| T38 | Screen design | Done | `docs/screenshots/` |
| T39 | API service layer | Done | `src/lib/api.ts` |
| T40 | Dashboard | Done | live browser test |
| T41 | Project workspace + mission composer | Done | live browser test |
| T42 | Mission details + live timeline | Done | live browser test |
| T43 | Memory Center (view, source, confirm, edit, delete) | Done | live browser test |
| T44 | Reports with verification evidence | Done | live browser test |
| T45 | Approval controls | Done | live browser test |
| T46 | Connections screen | Done | live browser test |
| T47 | Loading, error, empty states; responsive; dark mode; focus styles | Done | screenshots at 390 px and dark scheme |

## Phase 6 — Integration and reliability

| ID | Task | Status | Evidence |
|---|---|---|---|
| T48 | Frontend on real backend and agent | Done | Playwright run against live servers |
| T49 | End-to-end acceptance test | Done | `test_acceptance_flow_fresh_session_report_and_continuity` |
| T50 | Fresh-session memory test | Done | same test (connection pool disposed, new client) |
| T51 | Failure tests | Done | `test_failures.py` (8 tests) |
| T52 | Isolation and prompt-injection review | Done | `test_stored_instructions_are_treated_as_data` |
| T53 | Clean install test | Done | fresh venv + `npm ci` |
| T54 | Live smoke test | Done | `scripts/smoke_test.py` 17/17 |

## Phase 7 — Submission

| ID | Task | Status | Evidence |
|---|---|---|---|
| T55 | README | Done | README.md |
| T56 | decisions.md and pinned requirements | Done | decisions.md, requirements.txt |
| T57 | Architecture diagrams | Done | architecture.md (Mermaid) |
| T58 | License | Done | MIT |
| T59 | Push to a public GitHub repository | **Team** | see README “Publish to GitHub” |
| T60 | Demo script | Done | demo-script.md |
| T61 | Record English demo video under 3 minutes | **Team** | |
| T62 | Product feedback / feature requests if required | **Team** | |
| T63 | Fill submission fields before the deadline | **Team** | |
