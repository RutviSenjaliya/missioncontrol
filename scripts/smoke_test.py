#!/usr/bin/env python3
"""Live end-to-end smoke test against RUNNING servers (API + MCP + database).

Usage:
  python scripts/smoke_test.py --api http://127.0.0.1:8000 --mcp http://127.0.0.1:8001/mcp --token <token>

It creates a fresh project, stores context, then drives real missions through the agent and
the MCP server, and checks results by reading them back. Exit code 0 only if every check passes.
Use it before a demo and after deploying.
"""
import argparse
import asyncio
import sys
import time

import httpx

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> bool:
    RESULTS.append((ok, label))
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    return ok


def wait_mission(c: httpx.Client, mid: int, until=("completed", "failed", "partially_completed", "cancelled", "awaiting_approval"), timeout=30.0) -> dict:
    end = time.time() + timeout
    while True:
        m = c.get(f"/api/missions/{mid}").json()
        if m["status"] in until or time.time() > end:
            return m
        time.sleep(0.4)


async def mcp_direct(url: str, token: str, pid: int) -> None:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            check(bool(init.protocolVersion), f"MCP initialize over Streamable HTTP (protocol {init.protocolVersion})")
            tools = await s.list_tools()
            check(len(tools.tools) == 8, f"MCP tools/list returns {len(tools.tools)} tools")
            res = await s.call_tool("list_open_tasks", {"project_id": pid})
            check(not res.isError and res.structuredContent["count"] >= 2, "MCP tools/call list_open_tasks reads real data")
            bad = await s.call_tool("create_task", {"project_id": pid, "title": "bypass", "mission_id": 999999999})
            check(bad.isError, "MCP write without an approved mission is refused")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--mcp", default="http://127.0.0.1:8001/mcp")
    ap.add_argument("--token", default="change-me-demo-token")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api, headers={"Authorization": f"Bearer {a.token}"}, timeout=30)

    print("1. Connections")
    st = c.get("/api/status")
    if not check(st.status_code == 200, "API reachable and token accepted"):
        return 1
    s = st.json()
    check(s["database"]["ok"], f"Database connected ({s['database'].get('dialect')})")
    check(s["mcp"]["ok"], f"Backend reaches MCP server ({s['mcp'].get('protocol_version')})")

    print("2. Store project context")
    p = c.post("/api/projects", json={"name": f"Smoke test {int(time.time())}", "description": "Created by scripts/smoke_test.py"}).json()
    pid = p["id"]
    for content, tags in [("Win the hackathon with a working demo.", ["goal"]), ("Backend: FastAPI", ["stack"]), ("Database: PostgreSQL", ["stack"])]:
        c.post(f"/api/projects/{pid}/memories", json={"content": content, "tags": tags})
    old = c.post(f"/api/projects/{pid}/decisions", json={"title": "Use Flask"}).json()
    c.post(f"/api/projects/{pid}/decisions", json={"title": "Use FastAPI", "supersedes_decision_id": old["id"]})
    c.post(f"/api/projects/{pid}/tasks", json={"title": "Write README", "priority": "high"})
    c.post(f"/api/projects/{pid}/tasks", json={"title": "Fix CI", "status": "blocked"})
    ctx = c.get(f"/api/projects/{pid}/context").json()
    check([d["title"] for d in ctx["confirmed_decisions"]] == ["Use FastAPI"], "Context returns only the current decision")

    print("3. Mission: handoff report (no approval needed)")
    m = c.post(f"/api/projects/{pid}/missions", json={"request": "Create a project handoff report"}).json()
    m = wait_mission(c, m["id"])
    check(m["status"] == "completed", f"Mission #{m['id']} completed: {m['result_summary']}")
    rep = c.get(f"/api/reports/{m['reports'][0]['id']}").json() if m.get("reports") else {}
    check(rep.get("verification_status") == "passed", "Report persisted and verified by read-back")
    check("Use Flask" not in rep.get("content", "x Use Flask"), "Superseded decision excluded from report")

    print("4. Mission: write with approval")
    m = c.post(f"/api/projects/{pid}/missions", json={"request": "Add task: Record demo video (high priority)"}).json()
    m = wait_mission(c, m["id"])
    check(m["status"] == "awaiting_approval", "Write mission waits for approval")
    titles = [t["title"] for t in c.get(f"/api/projects/{pid}/tasks").json()]
    check("Record demo video" not in titles, "Nothing written before approval")
    c.post(f"/api/missions/{m['id']}/approve")
    m = wait_mission(c, m["id"], until=("completed", "failed", "partially_completed", "cancelled"))
    check(m["status"] == "completed", f"After approval: {m['result_summary']}")
    titles = [t["title"] for t in c.get(f"/api/projects/{pid}/tasks").json()]
    check("Record demo video" in titles, "Task visible through REST (same source of truth as MCP)")

    print("5. Honest failure")
    m = c.post(f"/api/projects/{pid}/missions", json={"request": "Order me a pizza"}).json()
    m = wait_mission(c, m["id"])
    check(m["status"] == "failed" and bool(m["error"]), "Unsupported request is reported as Failed, not success")

    print("6. Continuity")
    m = c.post(f"/api/projects/{pid}/missions", json={"request": "Summarize our progress"}).json()
    m = wait_mission(c, m["id"])
    content = c.get(f"/api/reports/{m['reports'][0]['id']}").json()["content"] if m.get("reports") else ""
    check("completed" in content and "Mission #" in content, "Later mission uses earlier mission outcomes")

    print("7. MCP server directly (independent client)")
    asyncio.run(mcp_direct(a.mcp, a.token, pid))

    passed = sum(ok for ok, _ in RESULTS)
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
