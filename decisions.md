# Engineering decisions

Each entry states what was decided, why, what else was considered, and whether it is implemented. Only implemented behaviour is described as implemented.

## D1. Track: Alexa+ via the self-hosted MCP server route
**Decision:** Build a self-hosted MCP server plus a web app whose agent uses it. We do not claim an official Alexa+ device integration.
**Why:** The team has no Alexa+ device access; the MCP route lets judges verify real tool execution with any MCP client.
**Status:** Implemented.

## D2. MCP as the only execution path for the agent
**Decision:** The agent performs all tool work through an MCP client talking to our own MCP server, even though both run from the same codebase.
**Why:** It makes the integration real rather than decorative, keeps the agent decoupled from the model provider, and means every agent action can be reproduced and audited by an external MCP client.
**Alternative:** Calling services directly from the agent (simpler, but MCP would then be a side feature).
**Status:** Implemented.

## D3. Streamable HTTP transport, MCP Python SDK 1.12.4, protocol 2025-06-18
**Decision:** FastMCP from the official SDK, stateful Streamable HTTP sessions at `/mcp`.
**Why:** Streamable HTTP is required by the track; the official SDK implements initialization, capability negotiation, JSON-RPC framing, sessions and schema validation correctly. 1.12.4 was pinned because it works with pydantic 2.11 and negotiates 2025-06-18.
**Open:** Confirm the spec version required by the official rules.
**Status:** Implemented and protocol-tested with a raw JSON-RPC harness and the SDK client.

## D4. Only the tools capability
**Decision:** Expose 8 tools; no MCP resources, prompts or optional extensions.
**Why:** Tools are what the workflow needs. We do not claim features we do not use.
**Status:** Implemented.

## D5. FastAPI + React/TypeScript/Vite
**Why:** FastAPI gives typed validation and OpenAPI docs in Python, the same language as the MCP SDK. React + TypeScript gives typed API contracts (`frontend/src/lib/types.ts`). Vite proxies `/api` in development so the browser uses one origin.
**Status:** Implemented. Only two runtime frontend dependencies (react, react-dom); routing and Markdown rendering are small in-house modules.

## D6. PostgreSQL as the source of truth; SQLite for tests
**Decision:** PostgreSQL for development and production; SQLite allowed for tests and experiments. Both are exercised: the full suite passes on each.
**Why:** One shared database for the API and the MCP server avoids two inconsistent sources of truth.
**Status:** Implemented. Alembic migration `0001` creates the schema; `alembic check` is clean.

## D7. Memory representation
**Decision:** One `memories` table with a `memory_type` column (semantic, episodic, procedural, working), provenance (`source`, `mission_id`), `confirmation` (confirmed/tentative), tags, and `status` + `supersedes_id`. Decisions are a separate table with their own supersession chain.
**Why:** The four memory types are logical categories, not four databases. Tags (`goal`, `stack`, `constraint`) give precise retrieval without embeddings.
**Retrieval:** Keyword relevance with tag boost, current records only. Embedding search was deferred until it demonstrably improves retrieval.
**Conflicts:** Supersession is explicit (user or mission states what is replaced). The planner never guesses which decision a new one replaces.
**Status:** Implemented.

## D8. Project isolation
**Decision:** `project_members` is the authorization boundary. Every REST route and every MCP tool calls `require_project(user, project_id)`; the MCP server authenticates the HTTP request itself rather than trusting the backend.
**Status:** Implemented; cross-user tests on every resource.

## D9. Agent workflow and planning
**Decision:** context → plan → validate → (approval) → execute → verify → record. Plans are JSON with steps, roles (`action`, `verify`, `read`) and checks. The orchestrator validates every plan: only advertised tools, `project_id` forced to the mission’s project, every write followed by verification, step limit, and `requires_approval` computed by the application.
**Planner:** `RuleBasedProvider` is the default: deterministic, offline, fully tested. `BedrockProvider` uses the Converse API and passes through the same validation; it is implemented but not verified without AWS credentials.
**Why:** A working, tested path is worth more than an untested model integration; the provider abstraction lets a model planner be switched on without changing safety rules.
**Status:** Implemented.

## D10. Verification
**Decision:** Verification reads persisted data back through MCP tools, independent of the write call’s response. Reports: persisted, correct project, every required section present and non-empty, every `(task #n)` / `(decision #n)` reference exists in the project. Tasks and decisions: read back and compare state. Read-only missions: marked not applicable.
**Invariant:** The state machine refuses `completed` without passing verification. A successful write with failed verification is `partially_completed`.
**Grounding:** Reports are assembled only from database records and mark empty sections “None recorded”, so the generator cannot invent tasks or decisions.
**Status:** Implemented.

## D11. Approval
**Decision:** `record_decision`, `create_task` and `update_task` need an approved, running mission created by the caller — enforced in the MCP server. Report generation creates a new record from the user’s explicit request and does not need separate approval.
**Status:** Implemented.

## D12. Failures, retries, limits, idempotency
**Decision:** Max 12 tool calls, 20 s per tool, 90 s per mission, one retry only for safe steps (reads, verification, or writes with an idempotency key) and only for `timeout`/`server_error`. Write tools take idempotency keys `mission-{id}-step-{n}` backed by unique constraints.
**Outcomes kept distinct:** failed tool call, successful write + failed verification, partial completion, verified completion, cancellation.
**Status:** Implemented and tested.

## D13. Security controls
Bearer tokens hashed with SHA-256; no secrets in repo, logs or UI; stored content treated as data (tested with an injected instruction); event payloads bounded in size; MCP audit log records tool, user, project and outcome without content. CORS limited to configured origins.
**Not implemented:** OAuth, rate limiting, team roles. Acceptable for the hackathon scope; listed as limitations.

## D14. Frontend design
**Decision:** A “strip board” visual language borrowed from air-traffic flight strips: each mission is a strip with a status edge; a *Verified* stamp appears only for application-verified outcomes. Barlow typeface (signage-like), light and dark themes, visible focus, reduced-motion support.
**Why:** The product’s core promise is honest status; the design makes status the most legible thing on screen.
**Status:** Implemented; checked in Chromium at desktop and 390 px widths and in dark mode.

## Limitations
Rule-based planner understands a fixed set of request types; Bedrock path unverified; keyword (not semantic) memory search; single-user projects (no invitations UI); no rate limiting; Google Fonts need internet (system-font fallback otherwise).

## Implementation history
| Date | Change |
|---|---|
| 2026-10-22 | Backend, models, migration, services, MCP server (8 tools), MCP client, orchestrator, state machine, REST API, CLI seed. |
| 2026-10-22 | Pinned pydantic 2.11.7 / mcp 1.12.4 after an SDK import incompatibility. |
| 2026-10-22 | Fixed FastMCP `Context` detection (removed postponed annotations in server module) after the first live mission failed — and was correctly reported as Failed. |
| 2026-10-22 | Test suite: 36 backend tests on SQLite and PostgreSQL; frontend typecheck, unit tests, build. |
| 2026-10-22 | Frontend; live Playwright run; dashboard feed limited to key events; docs; smoke test 17/17. |
