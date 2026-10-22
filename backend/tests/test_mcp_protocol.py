"""MCP protocol tests against the live Streamable HTTP server.

Two independent harnesses are used:
  * raw JSON-RPC 2.0 over HTTP with httpx (no MCP SDK on the client side), and
  * the official MCP Python SDK client.
"""
import asyncio
import json

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import LATEST_PROTOCOL_VERSION

from tests.conftest import ALICE, BOB, auth

EXPECTED_TOOLS = {"get_project_context", "search_memory", "list_open_tasks", "verify_report",
                  "generate_project_report", "record_decision", "create_task", "update_task"}


def _sse_json(resp: httpx.Response) -> dict:
    if resp.headers.get("content-type", "").startswith("application/json"):
        return resp.json()
    for line in resp.text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise AssertionError(f"no JSON-RPC message in response: {resp.text[:200]}")


def test_raw_jsonrpc_initialize_and_list(mcp_server):
    headers = {**auth(), "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with httpx.Client(timeout=10) as h:
        r = h.post(mcp_server, headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": {"name": "raw-test", "version": "0"}}})
        assert r.status_code == 200
        sid = r.headers.get("mcp-session-id")
        assert sid, "Streamable HTTP server must issue a session id"
        msg = _sse_json(r)
        assert msg["jsonrpc"] == "2.0" and msg["id"] == 1
        assert msg["result"]["protocolVersion"] == LATEST_PROTOCOL_VERSION
        assert "tools" in msg["result"]["capabilities"]
        headers |= {"mcp-session-id": sid, "mcp-protocol-version": LATEST_PROTOCOL_VERSION}
        assert h.post(mcp_server, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
        tools = _sse_json(h.post(mcp_server, headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
        names = {t["name"] for t in tools["result"]["tools"]}
        assert names == EXPECTED_TOOLS
        for t in tools["result"]["tools"]:
            assert t["inputSchema"]["type"] == "object" and "project_id" in t["inputSchema"]["properties"]
        bad = _sse_json(h.post(mcp_server, headers=headers, json={"jsonrpc": "2.0", "id": 3, "method": "no/such/method"}))
        # Unknown methods get a JSON-RPC error object (this SDK version answers -32602 rather than -32601).
        assert "result" not in bad and bad["error"]["code"] in (-32601, -32602)
        assert h.delete(mcp_server, headers=headers).status_code in (200, 204)


def test_rejects_request_without_session(mcp_server):
    headers = {**auth(), "Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    r = httpx.post(mcp_server, headers=headers, json={"jsonrpc": "2.0", "id": 9, "method": "tools/list"}, timeout=10)
    assert r.status_code == 400


async def _session(url: str, token: str, fn):
    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            return await fn(s, init)


def run(url, token, fn):
    return asyncio.run(_session(url, token, fn))


def test_sdk_client_discovers_and_reads(mcp_server, client, project):
    pid = project["id"]

    async def go(s, init):
        assert init.protocolVersion == LATEST_PROTOCOL_VERSION
        assert init.serverInfo.name == "MissionControl"
        ctx = await s.call_tool("get_project_context", {"project_id": pid})
        tasks = await s.call_tool("list_open_tasks", {"project_id": pid})
        found = await s.call_tool("search_memory", {"project_id": pid, "query": "FastAPI backend"})
        return ctx, tasks, found

    ctx, tasks, found = run(mcp_server, ALICE, go)
    assert not ctx.isError and ctx.structuredContent["project"]["id"] == pid
    assert [d["title"] for d in ctx.structuredContent["confirmed_decisions"]] == ["Use FastAPI"]
    assert not tasks.isError and tasks.structuredContent["count"] == 3
    assert not found.isError and found.structuredContent["results"][0]["content"] == "Backend: FastAPI"


def test_invalid_input_unknown_tool_and_auth_errors(mcp_server, project):
    pid = project["id"]

    async def go(s, _):
        return (await s.call_tool("list_open_tasks", {"project_id": "not-a-number"}),
                await s.call_tool("search_memory", {"project_id": pid}),
                await s.call_tool("does_not_exist", {}),
                await s.call_tool("list_open_tasks", {"project_id": 999999}))

    bad_type, missing, unknown, nf = run(mcp_server, ALICE, go)
    assert bad_type.isError and missing.isError and unknown.isError
    assert nf.isError and "not_found" in nf.content[0].text

    async def as_bob(s, _):
        return await s.call_tool("get_project_context", {"project_id": pid})

    forbidden = run(mcp_server, BOB, as_bob)
    assert forbidden.isError and "forbidden" in forbidden.content[0].text

    nobody = run(mcp_server, "invalid-token", as_bob)
    assert nobody.isError and "unauthorized" in nobody.content[0].text


def test_write_tools_require_approved_mission(mcp_server, client, project):
    pid = project["id"]

    async def go(s, _):
        no_mission = await s.call_tool("create_task", {"project_id": pid, "title": "Sneaky", "mission_id": 999999})
        return no_mission

    res = run(mcp_server, ALICE, go)
    assert res.isError and "forbidden" in res.content[0].text
    titles = [t["title"] for t in client.get(f"/api/projects/{pid}/tasks", headers=auth()).json()]
    assert "Sneaky" not in titles


def test_report_tools_persist_to_shared_database_and_are_idempotent(mcp_server, client, project):
    pid = project["id"]
    sections = ["Project Summary", "Open Tasks", "Blockers"]

    async def go(s, _):
        a = await s.call_tool("generate_project_report", {"project_id": pid, "title": "MCP Report", "required_sections": sections, "idempotency_key": "k-1"})
        b = await s.call_tool("generate_project_report", {"project_id": pid, "title": "MCP Report", "required_sections": sections, "idempotency_key": "k-1"})
        v = await s.call_tool("verify_report", {"project_id": pid, "report_id": a.structuredContent["report_id"]})
        bad = await s.call_tool("generate_project_report", {"project_id": pid, "title": "X", "required_sections": ["Nope"]})
        return a, b, v, bad

    a, b, v, bad = run(mcp_server, ALICE, go)
    assert a.structuredContent["created"] is True and b.structuredContent["created"] is False
    assert a.structuredContent["report_id"] == b.structuredContent["report_id"]
    assert v.structuredContent["passed"] is True
    assert bad.isError and "invalid_input" in bad.content[0].text
    # Same source of truth: the REST API sees what the MCP tool wrote, including verification status.
    rep = client.get(f"/api/reports/{a.structuredContent['report_id']}", headers=auth()).json()
    assert rep["title"] == "MCP Report" and rep["verification_status"] == "passed" and "## Blockers" in rep["content"]
