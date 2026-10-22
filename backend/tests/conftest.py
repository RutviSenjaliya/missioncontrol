"""Test fixtures.

A REAL MCP server (Streamable HTTP) is started in a background thread on a free port, using the
same database as the API under test. Tests therefore exercise the actual protocol, not mocks.

Database: SQLite file by default; set TEST_DATABASE_URL to run against PostgreSQL, e.g.
  TEST_DATABASE_URL=postgresql+psycopg://missioncontrol:missioncontrol@localhost:5432/missioncontrol_test
"""
import os
import socket
import tempfile
import threading
import time

_tmp = tempfile.mkdtemp(prefix="mc-test-")
_DB_URL = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


_PORT = _free_port()
os.environ["DATABASE_URL"] = _DB_URL
os.environ["MCP_SERVER_URL"] = f"http://127.0.0.1:{_PORT}/mcp"
os.environ["MCP_PORT"] = str(_PORT)
os.environ["AI_PROVIDER"] = "rule"
os.environ["DEMO_USER_TOKEN"] = "test-token-alice"

import pytest  # noqa: E402
import uvicorn  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.session import Base, get_engine, session_scope  # noqa: E402
from app.services import auth as auth_svc  # noqa: E402

ALICE, BOB = "test-token-alice", "test-token-bob"


@pytest.fixture(scope="session", autouse=True)
def database():
    eng = get_engine()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with session_scope() as db:
        auth_svc.create_user(db, "Alice", ALICE)
        auth_svc.create_user(db, "Bob", BOB)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture(scope="session", autouse=True)
def mcp_server(database):
    from app.mcp_server.server import create_app

    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=_PORT, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 15
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("MCP server did not start")
        time.sleep(0.05)
    yield get_settings().mcp_server_url
    server.should_exit = True
    t.join(timeout=5)


@pytest.fixture()
def settings():
    return get_settings()


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def auth(token: str = ALICE) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def project(client):
    """A fresh project for Alice with realistic data."""
    h = auth()
    p = client.post("/api/projects", json={"name": "Test Project", "description": "A project used in tests."}, headers=h).json()
    pid = p["id"]
    for content, tags in [("Ship the MVP before the hackathon deadline.", ["goal"]), ("Backend: FastAPI", ["stack"]),
                          ("Frontend: React", ["stack"]), ("Budget is zero dollars.", ["constraint"])]:
        assert client.post(f"/api/projects/{pid}/memories", json={"content": content, "tags": tags}, headers=h).status_code == 201
    old = client.post(f"/api/projects/{pid}/decisions", json={"title": "Use Flask"}, headers=h).json()
    client.post(f"/api/projects/{pid}/decisions", json={"title": "Use FastAPI", "supersedes_decision_id": old["id"]}, headers=h)
    for title, prio, status in [("Build API", "high", "in_progress"), ("Write docs", "low", "open"), ("Set up CI", "medium", "blocked")]:
        client.post(f"/api/projects/{pid}/tasks", json={"title": title, "priority": prio, "status": status}, headers=h)
    return p
