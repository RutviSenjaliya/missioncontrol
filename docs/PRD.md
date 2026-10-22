# MissionControl — Product Requirements Document

| | |
|---|---|
| Product | MissionControl |
| Track | Alexa+ — self-hosted MCP server route |
| Version | 1.0 (hackathon release) |
| Status | Implemented and tested (see [verification-report.md](verification-report.md)) |
| Source brief | MissionControl Complete Project Documentation and Team Onboarding Guide v1.0 |

## 1. Summary

MissionControl is an AI project assistant that remembers project context across sessions, uses it to plan multi-step work, executes that work through real tools exposed by a self-hosted MCP server, and verifies the outcome against persisted data before it reports success.

**One sentence:** an agent that remembers your project, does the work through real tools, and proves what happened.

## 2. Problem

Teams working with AI assistants over days or weeks repeatedly lose continuity:

| Problem | What happens today |
|---|---|
| Context loss | Goals, decisions and constraints are scattered across chats and people. |
| Repeated explanations | Every session starts by re-explaining the stack and unfinished work. |
| Weak execution | Assistants describe actions instead of performing them. |
| Unverified results | “Done” is a sentence, not evidence. |
| Poor continuity | No single record of decisions, actions and outcomes. |

## 3. Users

Primary: student and hackathon teams, developers and small project teams who need continuity across work sessions. Secondary: individuals with recurring project workflows. The release is optimised for project-based work, not general personal assistance.

## 4. Goals and success metrics

| Goal | Metric (release target) | Result |
|---|---|---|
| Context survives sessions | A fresh session retrieves stored goals, stack, decisions and tasks | Met — `test_acceptance_flow_fresh_session_report_and_continuity` |
| Work is executed, not described | 100% of mission actions run as MCP `tools/call` against the self-hosted server | Met — agent has no other execution path |
| Success is proven | 0 missions marked completed without passing read-back verification | Met — enforced by the state machine invariant |
| Failures are honest | Every failure mode in §9 ends in `failed` or `partially_completed` with a reason | Met — `tests/test_failures.py` |
| Outdated facts don’t drive plans | Superseded decisions and memories never appear as current | Met — context and report tests |

## 5. Scope

### In scope (implemented)

1. Project workspace with goals, technology stack, constraints, decisions, tasks, memory, missions and reports.
2. Persistent structured memory (semantic, episodic, procedural, working) with provenance, confirmation status, tags, supersession, edit and delete.
3. Context retrieval that excludes superseded information and lists data gaps.
4. Mission planning with explicit steps, success conditions and approval requirements.
5. Self-hosted MCP server over Streamable HTTP with 8 tools backed by real application operations.
6. Agent that discovers and invokes tools only through an MCP client.
7. Verification by independent read-back (report sections, referenced records, task/decision state).
8. Mission state machine with Pending, Planning, Awaiting approval, Running, Verifying, Completed, Failed, Partially completed and Cancelled.
9. Server-side approval for actions that modify project records.
10. Execution limits, bounded retries and idempotency keys.
11. Execution timeline with recorded evidence for every step.
12. Token authentication and project-level authorization in the API and MCP server.
13. Web interface: dashboard, project workspace, mission details, Memory Center, tasks and decisions, reports and connections.
14. Automated tests: unit, API, MCP protocol, end-to-end and failure tests, plus a live smoke test.

### Out of scope for this release

Official Alexa+ device integration; autonomous agents with unrestricted permissions; multi-agent frameworks; graph databases; external integrations not used in the demo; embedding-based semantic search; team roles beyond project membership.

## 6. User stories and acceptance criteria

| ID | Story | Acceptance criteria |
|---|---|---|
| US-1 | As a user I create a project and record what matters once. | Project, memories (with kind and confirmation), decisions and tasks are stored and survive restarts. |
| US-2 | As a user I return later and continue without re-explaining. | A new session’s mission retrieves goals, stack, current decisions and open tasks from the database. |
| US-3 | As a user I ask for a handoff report. | A report is generated only from stored records, saved, read back, and stamped verified only if every required section is present and every referenced task and decision exists. |
| US-4 | As a user I ask for a sprint plan or progress summary. | Same grounding and verification as US-3, using the sprint or progress template. |
| US-5 | As a user I ask the agent to add a task, update a task, or record a decision. | The mission stops at *Needs your approval*; nothing changes until I approve; after approval the change is read back and verified. Rejecting cancels with no change. |
| US-6 | As a user I correct my project’s memory. | I can view source and timestamps, confirm tentative records, edit content and delete records. |
| US-7 | As a user I see exactly what the agent did. | Mission details show the plan, success conditions, each tool call and its recorded data, verification checks and MCP protocol version. |
| US-8 | As a user I am told the truth when something breaks. | MCP outage, tool error, timeout, verification failure, unsupported request and provider failure each show Failed or Partially completed with a reason. |
| US-9 | As a judge I can verify the MCP integration independently. | Any MCP client can initialize, list tools and call them at `/mcp`; the repo includes raw JSON-RPC tests and a smoke test. |

## 7. Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | Every read or write of project data checks project membership server-side. |
| FR-2 | Memories store type, content, source, status, confirmation, tags, supersedes link, mission link and timestamps. |
| FR-3 | Recording a decision or memory that supersedes another marks the old record superseded; history is kept. |
| FR-4 | Context retrieval returns current information only and reports missing information. |
| FR-5 | Plans may only reference tools advertised by the MCP server; every write must be followed by a verification step; project id is forced to the mission’s project. |
| FR-6 | `record_decision`, `create_task` and `update_task` require an approved, running mission owned by the caller; the MCP server enforces this. |
| FR-7 | A mission can enter Completed only with passing verification evidence. |
| FR-8 | Write tools accept idempotency keys; retries never duplicate records. |
| FR-9 | Every mission outcome is stored as episodic memory for future missions. |
| FR-10 | The UI distinguishes model statements from application-verified facts and never shows a success state without verification. |

## 8. Non-functional requirements

| Area | Requirement |
|---|---|
| Reliability | Tool timeout 20 s, mission timeout 90 s, max 12 tool calls, 1 retry for safe steps (all configurable). |
| Security | Tokens stored as SHA-256 hashes; no secrets in logs, UI or repo; stored content treated as data, never instructions. |
| Portability | PostgreSQL in development and production; SQLite supported for tests and experiments; both are exercised by the test suite. |
| Accessibility | Keyboard focus visible, colour never the only status signal, reduced-motion respected, responsive to mobile widths, light and dark themes. |
| Reproducibility | Pinned Python dependencies, npm lockfile, Alembic migrations, one-command setup. |

## 9. Failure behaviour

| Situation | Mission status | User sees |
|---|---|---|
| MCP server unreachable | Failed | “MCP server unavailable at …” |
| Request not understood | Failed | Supported request examples |
| Tool returns an error (validation, forbidden, not found) | Failed, or Partially completed if an earlier write succeeded | The tool’s error code and message |
| Tool timeout | Retried once if safe, then Failed or Partially completed | Each attempt in the timeline |
| Write succeeded, verification failed | Partially completed | Which checks failed |
| AI provider unavailable or misconfigured | Failed | Provider error |
| Execution limit exceeded | Failed | Which limit |
| User rejects approval | Cancelled | “Rejected by user; no changes were made” |

## 10. Release plan

Delivered in seven phases (requirements, backend, MCP server, agent, frontend, integration, submission). The detailed task list with completion status is in [TASKS.md](TASKS.md).

## 11. Open items for the team

1. MCP spec requirement (2025-11-25 or later, Streamable HTTP) is met: the server negotiates `2025-11-25` with MCP Python SDK 1.30.0.
2. Optional: enable the Bedrock planner with real AWS credentials and run the suite with `AI_PROVIDER=bedrock` (implemented, not verified in this build environment).
3. Record the demo video following [demo-script.md](demo-script.md).
