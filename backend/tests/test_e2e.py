"""End-to-end acceptance tests (Section 16.5 of the project document) and continuity.

The agent runs through the REAL MCP server over Streamable HTTP. TestClient executes FastAPI
background tasks before returning, so the mission has finished when the response arrives.
"""
from app.db.session import get_engine
from tests.conftest import auth


def mission(client, pid, request):
    m = client.post(f"/api/projects/{pid}/missions", json={"request": request}, headers=auth())
    assert m.status_code == 202
    return client.get(f"/api/missions/{m.json()['id']}", headers=auth()).json()


def test_acceptance_flow_fresh_session_report_and_continuity(client, project):
    pid = project["id"]
    # 1-2. Project and details were stored by the fixture. 3. Start a "fresh session":
    get_engine().dispose()  # drop every pooled DB connection; nothing is carried over in memory
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as fresh:
        # 4. Saved context is retrievable.
        ctx = fresh.get(f"/api/projects/{pid}/context", headers=auth()).json()
        assert {m["content"] for m in ctx["tech_stack"]} == {"Backend: FastAPI", "Frontend: React"}
        # 5-9. Mission -> MCP tools -> report -> verification -> final state.
        m = mission(fresh, pid, "Create a project handoff report with summary, stack, decisions, open tasks, blockers and next steps")
    assert m["status"] == "completed", m
    types = [e["event_type"] for e in m["events"]]
    for expected in ["mission_created", "mcp_connected", "context_retrieved", "plan_generated", "tool_invoked",
                     "tool_succeeded", "verification", "mission_completed", "outcome_recorded"]:
        assert expected in types
    mcp_ev = next(e for e in m["events"] if e["event_type"] == "mcp_connected")
    assert mcp_ev["result"]["protocol_version"] and "generate_project_report" in mcp_ev["result"]["tools"]
    assert [e["tool_name"] for e in m["events"] if e["event_type"] == "tool_invoked"] == ["generate_project_report", "verify_report"]
    ver = next(e for e in m["events"] if e["event_type"] == "verification")
    assert ver["verification_status"] == "passed"
    assert len(m["reports"]) == 1
    report = client.get(f"/api/reports/{m['reports'][0]['id']}", headers=auth()).json()
    assert report["verification_status"] == "passed"
    for section in ["Project Summary", "Technology Stack", "Confirmed Decisions", "Open Tasks", "Blockers", "Next Steps"]:
        assert f"## {section}" in report["content"]
    assert "Use FastAPI" in report["content"] and "Use Flask" not in report["content"]  # superseded decision excluded
    # 10. History remains available and the outcome became memory.
    hist = client.get(f"/api/projects/{pid}/missions", headers=auth()).json()
    assert hist[0]["id"] == m["id"]
    episodic = client.get(f"/api/projects/{pid}/memories?memory_type=episodic", headers=auth()).json()
    assert any(f"Mission #{m['id']}" in e["content"] for e in episodic)
    # Continuity: a later mission builds on the earlier one.
    nxt = mission(client, pid, "Summarize our progress")
    assert nxt["status"] == "completed"
    content = client.get(f"/api/reports/{nxt['reports'][0]['id']}", headers=auth()).json()["content"]
    assert f"Mission #{m['id']} completed" in content


def test_sprint_plan_uses_context(client, project):
    m = mission(client, project["id"], "Create a sprint plan based on our goals, confirmed decisions and unfinished tasks")
    assert m["status"] == "completed" and m["mission_type"] == "sprint_plan_report"
    content = client.get(f"/api/reports/{m['reports'][0]['id']}", headers=auth()).json()["content"]
    assert "Ship the MVP" in content and "Build API" in content and "Budget is zero dollars." in content


def test_write_mission_waits_for_approval_then_verifies(client, project):
    pid = project["id"]
    m = mission(client, pid, "Add task: Record demo video (high priority)")
    assert m["status"] == "awaiting_approval" and m["requires_approval"] is True
    assert "Record demo video" not in [t["title"] for t in client.get(f"/api/projects/{pid}/tasks", headers=auth()).json()]
    r = client.post(f"/api/missions/{m['id']}/approve", headers=auth())
    assert r.status_code == 202
    done = client.get(f"/api/missions/{m['id']}", headers=auth()).json()
    assert done["status"] == "completed", done
    tasks = client.get(f"/api/projects/{pid}/tasks", headers=auth()).json()
    new = next(t for t in tasks if t["title"] == "Record demo video")
    assert new["priority"] == "high"
    assert client.post(f"/api/missions/{m['id']}/approve", headers=auth()).status_code == 409


def test_update_task_and_decision_supersession_missions(client, project):
    pid = project["id"]
    tasks = client.get(f"/api/projects/{pid}/tasks", headers=auth()).json()
    tid = next(t["id"] for t in tasks if t["title"] == "Set up CI")
    m = mission(client, pid, f"Mark task #{tid} done")
    client.post(f"/api/missions/{m['id']}/approve", headers=auth())
    assert client.get(f"/api/missions/{m['id']}", headers=auth()).json()["status"] == "completed"
    assert next(t for t in client.get(f"/api/projects/{pid}/tasks", headers=auth()).json() if t["id"] == tid)["status"] == "done"

    cur = next(d for d in client.get(f"/api/projects/{pid}/decisions", headers=auth()).json() if d["status"] == "confirmed")
    m = mission(client, pid, f"Record decision: Use Litestar - benchmark winner, supersedes #{cur['id']}")
    client.post(f"/api/missions/{m['id']}/approve", headers=auth())
    final = client.get(f"/api/missions/{m['id']}", headers=auth()).json()
    assert final["status"] == "completed", final
    decisions = {d["title"]: d["status"] for d in client.get(f"/api/projects/{pid}/decisions", headers=auth()).json()}
    assert decisions["Use Litestar"] == "confirmed" and decisions[cur["title"]] == "superseded"


def test_rejected_mission_changes_nothing(client, project):
    pid = project["id"]
    before = len(client.get(f"/api/projects/{pid}/tasks", headers=auth()).json())
    m = mission(client, pid, "Add task: Should never exist")
    r = client.post(f"/api/missions/{m['id']}/reject", headers=auth()).json()
    assert r["status"] == "cancelled"
    assert len(client.get(f"/api/projects/{pid}/tasks", headers=auth()).json()) == before


def test_read_only_mission(client, project):
    m = mission(client, project["id"], "Show open tasks")
    assert m["status"] == "completed"
    ver = [e for e in m["events"] if e["event_type"] == "verification"]
    assert ver and ver[0]["verification_status"] == "not_applicable"
