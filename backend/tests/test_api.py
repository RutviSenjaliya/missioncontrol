"""REST API tests: CRUD, validation, authentication and project isolation."""
from tests.conftest import ALICE, BOB, auth


def test_health_and_auth(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/projects", headers=auth("wrong")).status_code == 401
    assert client.get("/api/me", headers=auth()).json()["name"] == "Alice"


def test_project_crud_and_validation(client):
    r = client.post("/api/projects", json={"name": "P1"}, headers=auth())
    assert r.status_code == 201
    pid = r.json()["id"]
    assert any(p["id"] == pid for p in client.get("/api/projects", headers=auth()).json())
    assert client.post("/api/projects", json={"name": ""}, headers=auth()).status_code == 422


def test_project_isolation_between_users(client, project):
    pid = project["id"]
    assert client.get(f"/api/projects/{pid}", headers=auth(BOB)).status_code == 403
    assert client.get(f"/api/projects/{pid}/memories", headers=auth(BOB)).status_code == 403
    assert client.post(f"/api/projects/{pid}/tasks", json={"title": "x"}, headers=auth(BOB)).status_code == 403
    assert client.post(f"/api/projects/{pid}/missions", json={"request": "handoff report"}, headers=auth(BOB)).status_code == 403
    task_id = client.get(f"/api/projects/{pid}/tasks", headers=auth()).json()[0]["id"]
    assert client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=auth(BOB)).status_code == 403
    assert all(p["id"] != pid for p in client.get("/api/projects", headers=auth(BOB)).json())
    assert client.get("/api/projects/999999", headers=auth()).status_code == 404


def test_memory_center_edit_and_delete(client, project):
    pid = project["id"]
    m = client.post(f"/api/projects/{pid}/memories", json={"content": "Old fact", "confirmation": "tentative"}, headers=auth()).json()
    assert m["source"] == "user" and m["confirmation"] == "tentative"
    upd = client.patch(f"/api/memories/{m['id']}", json={"content": "Corrected fact", "confirmation": "confirmed"}, headers=auth()).json()
    assert upd["content"] == "Corrected fact" and upd["confirmation"] == "confirmed"
    assert client.patch(f"/api/memories/{m['id']}", json={"content": "hack"}, headers=auth(BOB)).status_code == 403
    assert client.delete(f"/api/memories/{m['id']}", headers=auth()).status_code == 204
    ids = [x["id"] for x in client.get(f"/api/projects/{pid}/memories", headers=auth()).json()]
    assert m["id"] not in ids
    assert client.post(f"/api/projects/{pid}/memories", json={"content": "x", "memory_type": "nope"}, headers=auth()).status_code == 422


def test_context_excludes_superseded_decision(client, project):
    ctx = client.get(f"/api/projects/{project['id']}/context", headers=auth()).json()
    titles = [d["title"] for d in ctx["confirmed_decisions"]]
    assert titles == ["Use FastAPI"] and ctx["superseded_decision_count"] == 1
    assert [t["title"] for t in ctx["blocked_tasks"]] == ["Set up CI"]


def test_task_update_and_invalid_status(client, project):
    pid = project["id"]
    t = client.post(f"/api/projects/{pid}/tasks", json={"title": "New"}, headers=auth()).json()
    done = client.patch(f"/api/tasks/{t['id']}", json={"status": "done"}, headers=auth()).json()
    assert done["status"] == "done" and done["completed_at"]
    assert client.patch(f"/api/tasks/{t['id']}", json={"status": "finished"}, headers=auth()).status_code == 422


def test_status_endpoint_reports_live_mcp(client):
    s = client.get("/api/status", headers=auth()).json()
    assert s["database"]["ok"] is True
    assert s["mcp"]["ok"] is True and s["mcp"]["transport"] == "streamable-http"
    assert {t["name"] for t in s["mcp"]["tools"]} >= {"get_project_context", "verify_report"}
    assert "token" not in str(s).lower()
