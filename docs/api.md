# REST API contract

Base path `/api`. All endpoints except `/health` require `Authorization: Bearer <token>`. Errors return `{"detail": "...", "code"?: "..."}` with 401 (no/invalid token), 403 (not a project member), 404, 409 (wrong state) or 422 (validation). Interactive docs: `http://127.0.0.1:8000/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + database check |
| GET | `/me` | Current user |
| GET | `/status` | Database, MCP (protocol, tools) and planner status; never secrets |
| GET | `/dashboard` | Projects, active/recent missions, key recent events |
| GET/POST | `/projects` | List / create (`{name, description}`) |
| GET | `/projects/{id}` | Project with open task count |
| GET | `/projects/{id}/context?focus=` | The context the agent would retrieve |
| GET/POST | `/projects/{id}/memories` | List (`memory_type`, `status`, `q` filters) / create (`{content, memory_type, confirmation, tags, source, supersedes_id}`) |
| PATCH/DELETE | `/memories/{id}` | Correct (`content, memory_type, confirmation, status, tags`) / delete |
| GET/POST | `/projects/{id}/decisions` | List / record (`{title, description, status, supersedes_decision_id}`) |
| GET/POST | `/projects/{id}/tasks` | List / create (`{title, description, priority, status}`) |
| PATCH | `/tasks/{id}` | Update task |
| GET/POST | `/projects/{id}/missions` | List / start (`{request}`) → 202 with mission and first event |
| GET | `/missions/{id}` | Mission with plan, events and reports |
| POST | `/missions/{id}/approve` | Approve (creator only, status must be `awaiting_approval`) → 202 |
| POST | `/missions/{id}/reject` | Reject → `cancelled` |
| POST | `/missions/{id}/cancel` | Cancel a non-terminal mission |
| GET | `/projects/{id}/reports` | Report list with verification status |
| GET | `/reports/{id}` | Report content and verification details |

Mission object: `id, project_id, request, mission_type, status, plan{mission_type, summary, requires_approval, steps[{n, tool, args, purpose, role, check}], success_conditions, provider}, requires_approval, approved_at, result_summary, error, tool_calls, created_at, started_at, completed_at, events[], reports[]`.

Event object: `id, mission_id, seq, event_type, description, tool_name, result, verification_status (passed|failed|not_applicable|null), created_at`. Event types: `mission_created, planning_started, mcp_connected, context_retrieved, context_failed, plan_generated, planning_failed, approval_requested, approval_received, tool_invoked, tool_succeeded, tool_failed, verification, mcp_unavailable, mission_<status>, outcome_recorded, cancelled`.
