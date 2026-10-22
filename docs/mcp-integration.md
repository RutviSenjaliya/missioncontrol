# MCP integration

## What is implemented

| Item | Value |
|---|---|
| Server | `backend/app/mcp_server/server.py` (FastMCP from the official MCP Python SDK) |
| SDK version | `mcp==1.30.0` |
| Protocol version negotiated | `2025-11-25` (hackathon minimum; latest supported by this SDK) |
| Transport | Streamable HTTP, endpoint `POST/GET/DELETE /mcp`, stateful sessions via `mcp-session-id` |
| Messages | JSON-RPC 2.0 |
| Capabilities used | `tools` (resources and prompts are not exposed: they did not add value to the core workflow) |
| Authentication | `Authorization: Bearer <user token>` on the HTTP request, checked on every tool call |

> **Hackathon requirement met:** the Alexa+ track requires MCP spec **2025-11-25 or later** over Streamable HTTP. This server negotiates `2025-11-25`, verified by `test_raw_jsonrpc_initialize_and_list` (raw JSON-RPC, no SDK on the client side).

## Start and connect

```bash
./scripts/run_mcp_server.sh            # http://127.0.0.1:8001/mcp
```

Any MCP client that supports Streamable HTTP can connect, for example the MCP Inspector (`npx @modelcontextprotocol/inspector`), choosing transport *Streamable HTTP*, URL `http://127.0.0.1:8001/mcp`, and header `Authorization: Bearer <token>`.

Raw protocol check with curl:

```bash
curl -i -X POST http://127.0.0.1:8001/mcp \
  -H "Authorization: Bearer change-me-demo-token" \
  -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
# -> 200, header mcp-session-id, body: event: message / data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25",...}}
```

## Tools

All tools take `project_id` (integer > 0) and are scoped to a project the caller is a member of. Results are JSON objects returned as `structuredContent` (and as text). Errors are returned as tool results with `isError: true` and a message starting with an error code.

| Tool | Kind | Inputs (besides `project_id`) | Returns |
|---|---|---|---|
| `get_project_context` | read | `focus?` | goals, tech_stack, constraints, facts, procedures, confirmed/proposed decisions, open/blocked/completed tasks, recent missions/reports/events, missing_information, relevant_memories (if focus) |
| `search_memory` | read | `query`, `limit?` (1–50) | ranked active memories with provenance and score |
| `list_open_tasks` | read | — | open, in-progress and blocked tasks, highest priority first |
| `verify_report` | read + marks status | `report_id`, `required_sections?` | `passed` and a list of checks (persisted, belongs to project, each section present and non-empty, referenced tasks and decisions exist) |
| `generate_project_report` | write | `title`, `required_sections`, `mission_id?`, `idempotency_key?` | `report_id`, `created` (false on idempotent repeat) |
| `record_decision` | write, approval | `title`, `mission_id`, `description?`, `status?`, `supersedes_decision_id?` | the stored decision |
| `create_task` | write, approval | `title`, `mission_id`, `description?`, `priority?`, `idempotency_key?` | the task and `created` |
| `update_task` | write, approval | `task_id`, `mission_id`, `status?`, `priority?`, `title?`, `description?` | the updated task |

Supported report sections: Project Summary, Technology Stack, Confirmed Decisions, Relevant Decisions, Open Tasks, Blockers, Next Steps, Recent Progress, Constraints, Sprint Goal, Planned Tasks.

## Error codes

| Code | Meaning |
|---|---|
| `unauthorized` | Missing or invalid bearer token |
| `forbidden` | Not a member of the project, mission belongs to another project/user, or task belongs to another project |
| `not_found` | Project, task or report does not exist |
| `invalid_input` | Domain validation failed (e.g. unknown section, empty title) |
| `approval_required` | Write tool called without an approved, running mission |
| `server_error` | Unexpected failure (details only in server logs) |

Schema-level validation (wrong types, missing required fields, out-of-range values) is enforced by the SDK from the tool signatures and also returns `isError: true`.

## Approval enforcement

The three tools that modify existing project records require `mission_id` of a mission that belongs to the same project, was created by the caller, has `approved_at` set and is currently `running`. Approval is granted only through `POST /api/missions/{id}/approve` by the mission’s creator. A model or a direct MCP client cannot bypass it. Report generation creates a new record and is covered by the user’s explicit request, so it does not need a separate approval.

## Tests

`backend/tests/test_mcp_protocol.py` runs against a real server on a free port:

1. Raw JSON-RPC over HTTP with httpx (no SDK on the client): initialize, session id, protocol version, capabilities, `notifications/initialized` (202), `tools/list`, unknown method error, session DELETE, request without session rejected (400).
2. Official SDK client: discovery, reads with real data, invalid types, missing arguments, unknown tool, unknown project, other user’s project, invalid token, write without approval, idempotent report generation, verification, and persistence visible through the REST API.

Known SDK behaviour: an unknown JSON-RPC method returns error code `-32602` from this SDK version rather than `-32601`; the test accepts either and checks that no result is returned.
