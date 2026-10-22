# Devpost submission draft

Copy each section into the matching field on the “Enter a Submission” page. Replace anything in [brackets]. Every statement below matches what is in the repository; do not add claims that the code does not support.

---

## Project name
MissionControl

## Tagline
An AI project agent that remembers your project, does the work through a self-hosted MCP server, and proves what happened.

## Track and mini challenges
- **Primary track:** Alexa+ (self-hosted MCP server, spec 2025-11-25, Streamable HTTP)
- **Mini challenges:** None. *(Only enter AWS Builder if a real AWS service is integrated, tested and documented in the repo before you submit. Only enter Open Source if you also ship a separate, additional open-source project or contribution.)*

## Text description

**The problem.** Teams that use AI assistants over days or weeks keep re-explaining their project: goals, stack, decisions, unfinished work. And when an assistant says a task is “done”, that is a sentence, not evidence.

**What MissionControl does.** MissionControl is a context-aware agent that keeps state across sessions. It stores project knowledge as structured memory (goals, technology, constraints, procedures, decisions with supersession history, tasks), retrieves current context in a fresh session, plans multi-step missions, executes them through tools on our self-hosted MCP server, and marks a mission completed only after reading the result back from the database and checking it.

**How it works.**
- **Self-hosted MCP server** (MCP Python SDK 1.30.0, FastMCP) over **Streamable HTTP**, negotiating protocol **2025-11-25**. Eight tools: `get_project_context`, `search_memory`, `list_open_tasks`, `verify_report`, `generate_project_report`, `record_decision`, `create_task`, `update_task`. Each tool authenticates the caller, checks project membership and validates input before running a real database operation.
- **Agent** in a FastAPI backend: context → plan → validate → approval → execute → verify → record. The agent has no execution path other than its MCP client, so every action it takes can be reproduced by any MCP client.
- **Verification by read-back:** reports are re-read and checked section by section, and every task and decision they reference must exist in the project. Task and decision changes are read back and compared. A successful write with a failed check ends as *Partially completed*, never as success.
- **Server-enforced approval:** tools that change project records refuse to run without a mission the user approved.
- **Honest failure:** MCP outage, timeout, tool error, failed verification and unsupported requests each end as *Failed* or *Partially completed* with a reason.
- **Web app** (React + TypeScript): dashboard, project workspace, live mission timeline with recorded evidence, Memory Center to confirm, edit or delete what the agent remembers, reports with verification checks, and a connections screen listing the MCP tools.
- **PostgreSQL** is the single source of truth shared by the API and the MCP server.

**Built during the submission window.** The entire project was created during the hackathon submission period.

**Testing.** 37 backend tests (unit, REST API, MCP protocol with a raw JSON-RPC harness and the SDK client, end-to-end, failure cases) pass on SQLite and PostgreSQL; frontend typecheck, unit tests and build pass; `scripts/smoke_test.py` runs 17 live checks against running services. Setup and run instructions are in the README.

**Testing instructions for judges.** `docker compose up -d db && ./scripts/setup.sh`, then `./scripts/run_mcp_server.sh`, `./scripts/run_backend.sh`, `./scripts/run_frontend.sh`. Open http://127.0.0.1:5173 and sign in with the token `change-me-demo-token` (set in `backend/.env`). MCP endpoint: `http://127.0.0.1:8001/mcp` with header `Authorization: Bearer change-me-demo-token`.

## Links
- Code repository: [https://github.com/USERNAME/missioncontrol]
- Demo video (public, English, under 3 minutes): [YouTube or Vimeo link]

---

## Product feedback

**Which developer tools, APIs and SDKs did you use, and for what?**
- **Model Context Protocol specification (2025-11-25) and docs at modelcontextprotocol.io** — to design the server, tools, error handling and transport behaviour.
- **MCP Python SDK (`mcp` 1.30.0, FastMCP)** — to build the self-hosted MCP server with Streamable HTTP, and as the MCP client inside our agent.
- Supporting open-source stack (not Amazon tools): FastAPI, SQLAlchemy, Alembic, PostgreSQL, React, Vite.
- No AWS services are used at runtime in this submission.

**What worked well?**
- FastMCP generated correct JSON input schemas straight from Python type hints and `Field` constraints, so validation errors come back as proper tool errors without extra code.
- Streamable HTTP with session ids worked reliably for both our in-process agent and a raw HTTP client; it was easy to write protocol-level tests with plain `httpx`.
- Structured tool results (`structuredContent`) made it simple for the agent to verify outcomes without parsing text.
- Being able to read HTTP headers from the tool context let the MCP server do its own authentication and project-level authorization.

**What needs work?**
- SDK upgrades: our first pinned SDK version broke with a newer pydantic at import time, and moving to a version that negotiates 2025-11-25 needed dependency re-pinning. A compatibility table (SDK version → protocol versions → supported pydantic range) would save time.
- `Context` parameters are detected by type annotation, so `from __future__ import annotations` silently breaks tools that need the context (the call fails with “ctx Field required”). A clear error or docs note would help.
- An unknown JSON-RPC method returned error code -32602 instead of the -32601 we expected from JSON-RPC 2.0; documenting the intended behaviour would help test authors.
- Docs for running a stateful Streamable HTTP server behind a real host name (transport security / allowed hosts) were hard to find.

**How was your onboarding experience (zero to hello world)?**
Fast: a FastMCP server answering `initialize` and `tools/list` over Streamable HTTP took minutes. Most time went into production concerns the quick-starts don’t cover: authentication from HTTP headers, version pinning, and protocol-level testing.

**Would you build with these again?**
Yes. MCP gave us a clean boundary between the agent and the application: every action the agent takes is a standard, testable tool call that any other MCP client — including Alexa+ — can make too.

---

## Friction log (optional, up to 10% judging bonus)

| # | Task attempted | Steps taken | Expected | Actual | Severity | Workaround | Suggestion |
|---|---|---|---|---|---|---|---|
| 1 | Start the MCP server with a pinned SDK | Installed `mcp` with the latest pydantic, imported `mcp.server.fastmcp` | Server starts | Import error from a pydantic incompatibility | High (blocks start) | Pinned compatible pydantic and SDK versions | Publish a compatibility matrix; declare an upper bound on pydantic in older SDK releases |
| 2 | Meet the Alexa+ minimum spec version | Checked `LATEST_PROTOCOL_VERSION` of the pinned SDK | 2025-11-25 | Older SDK negotiated 2025-06-18 | High (track requirement) | Upgraded to SDK 1.30.0 and re-ran the protocol tests | State the minimum SDK version for the track in the hackathon resources |
| 3 | Use `Context` in tools for auth | Module used `from __future__ import annotations` | Context injected | Every tool call failed with “ctx Field required” | Medium | Removed postponed annotations from the server module | Resolve string annotations or raise a clear startup error |
| 4 | Upgrade the SDK in an existing environment | `pip install mcp==1.30.0` with `--ignore-installed` | Only MCP-related packages change | Starlette jumped to a major version FastAPI does not support; API crashed on start | Medium | Pinned Starlette back to the FastAPI-compatible version | Note common web-framework pins in the upgrade guide |
| 5 | Test error handling for unknown methods | Sent `no/such/method` via raw JSON-RPC | Error -32601 | Error -32602 | Low | Test accepts both and asserts no result | Document the expected code |

## Feature requests (optional)

| Feature | Why it matters to MissionControl | Priority |
|---|---|---|
| Official guide for connecting a self-hosted MCP server to Alexa+ (auth, discovery, testing) | We could only verify with generic MCP clients; a path to try it in Alexa+ would let us validate the real end-user experience | Critical |
| Built-in auth helpers for Streamable HTTP servers (bearer/OAuth) in the Python SDK | Every real server needs per-user authorization; we wrote our own | Important |
| Conformance test suite for MCP servers | Would replace our hand-written raw JSON-RPC tests and prove spec compliance to judges | Important |
| SDK compatibility matrix (SDK ↔ protocol ↔ pydantic) | Avoids broken installs before deadlines | Nice-to-have |
