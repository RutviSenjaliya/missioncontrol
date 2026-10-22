"""Unit tests for services and the mission state machine."""
import pytest

from app.agent.state import InvalidTransition, transition
from app.db.session import session_scope
from app.models import Mission, MissionStatus as S, Project
from app.services import auth as auth_svc
from app.services import decisions as decision_svc
from app.services import memory as memory_svc
from app.services import projects as project_svc
from app.services import reports as report_svc
from app.services import tasks as task_svc
from app.services.context import get_project_context
from app.services.errors import Forbidden, InvalidInput
from tests.conftest import ALICE, BOB


def _users(db):
    return auth_svc.user_from_token(db, ALICE), auth_svc.user_from_token(db, BOB)


def test_memory_supersession_and_search_excludes_outdated():
    with session_scope() as db:
        alice, _ = _users(db)
        p = project_svc.create_project(db, alice, "Mem")
        old = memory_svc.create_memory(db, p.id, "The backend uses Flask", tags=["stack"])
        new = memory_svc.create_memory(db, p.id, "The backend uses FastAPI", tags=["stack"], supersedes_id=old.id)
        assert old.status == "superseded"
        hits = [m.id for m, _ in memory_svc.search_memory(db, p.id, "backend")]
        assert hits == [new.id]
        hits_all = [m.id for m, _ in memory_svc.search_memory(db, p.id, "backend", include_superseded=True)]
        assert set(hits_all) == {old.id, new.id}
        ctx = get_project_context(db, p)
        assert [m["content"] for m in ctx["tech_stack"]] == ["The backend uses FastAPI"]


def test_memory_search_is_project_isolated():
    with session_scope() as db:
        alice, _ = _users(db)
        a = project_svc.create_project(db, alice, "A")
        b = project_svc.create_project(db, alice, "B")
        memory_svc.create_memory(db, a.id, "secret kubernetes plan")
        assert memory_svc.search_memory(db, b.id, "kubernetes") == []


def test_memory_validation():
    with session_scope() as db:
        alice, _ = _users(db)
        p = project_svc.create_project(db, alice, "V")
        with pytest.raises(InvalidInput):
            memory_svc.create_memory(db, p.id, "   ")
        with pytest.raises(InvalidInput):
            memory_svc.create_memory(db, p.id, "x", memory_type="bogus")


def test_decision_supersession_keeps_history():
    with session_scope() as db:
        alice, _ = _users(db)
        p = project_svc.create_project(db, alice, "D")
        d1 = decision_svc.record_decision(db, p.id, "Use Flask")
        d2 = decision_svc.record_decision(db, p.id, "Use FastAPI", supersedes_decision_id=d1.id)
        assert d1.status == "superseded" and d2.supersedes_decision_id == d1.id
        assert [d.id for d in decision_svc.list_decisions(db, p.id, current_only=True)] == [d2.id]
        assert len(decision_svc.list_decisions(db, p.id)) == 2
        with pytest.raises(InvalidInput):
            decision_svc.record_decision(db, p.id, "Again", supersedes_decision_id=d1.id)


def test_task_idempotency_and_cross_project_supersede_rejected():
    with session_scope() as db:
        alice, _ = _users(db)
        p = project_svc.create_project(db, alice, "T")
        q = project_svc.create_project(db, alice, "U")
        t1, c1 = task_svc.create_task(db, p.id, "Do it", idempotency_key="k1")
        t2, c2 = task_svc.create_task(db, p.id, "Do it", idempotency_key="k1")
        assert c1 and not c2 and t1.id == t2.id
        d = decision_svc.record_decision(db, p.id, "X")
        with pytest.raises(InvalidInput):
            decision_svc.record_decision(db, q.id, "Y", supersedes_decision_id=d.id)


def test_require_project_blocks_non_members():
    with session_scope() as db:
        alice, bob = _users(db)
        p = project_svc.create_project(db, alice, "Private")
        with pytest.raises(Forbidden):
            auth_svc.require_project(db, bob, p.id)


def test_state_machine_rules():
    m = Mission(id=1, status=S.PENDING.value)
    with pytest.raises(InvalidTransition):
        transition(m, S.COMPLETED)
    transition(m, S.PLANNING)
    transition(m, S.RUNNING)
    transition(m, S.VERIFYING)
    with pytest.raises(InvalidTransition):
        transition(m, S.COMPLETED)  # no verification evidence
    transition(m, S.COMPLETED, verified=True)
    assert m.completed_at is not None
    with pytest.raises(InvalidTransition):
        transition(m, S.RUNNING)  # terminal


def test_report_verification_detects_tampering_and_fake_references():
    with session_scope() as db:
        alice, _ = _users(db)
        p = project_svc.create_project(db, alice, "R", "desc")
        task_svc.create_task(db, p.id, "Real task")
        r, _ = report_svc.generate_report(db, p, "Handoff", report_svc.TEMPLATES["handoff"])
        assert report_svc.verify_report(db, p, r.id)["passed"] is True
        r.content = r.content.replace("## Blockers", "## Something else") + "\n- Fake (task #999999)\n"
        db.flush()
        res = report_svc.verify_report(db, p, r.id)
        failed = {c["check"] for c in res["checks"] if not c["passed"]}
        assert res["passed"] is False
        assert "section:Blockers" in failed and "task_references_exist" in failed


def test_report_rejects_unknown_sections():
    with session_scope() as db:
        alice, _ = _users(db)
        p = project_svc.create_project(db, alice, "S")
        with pytest.raises(InvalidInput):
            report_svc.generate_report(db, p, "X", ["Made Up Section"])
