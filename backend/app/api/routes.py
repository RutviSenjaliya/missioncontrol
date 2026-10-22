"""REST API used by the frontend. Tool execution is NOT done here; missions go through the agent + MCP."""
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.agent import orchestrator
from app.agent.state import InvalidTransition, transition
from app.api.deps import current_user, get_token
from app.config import get_settings
from app.db.session import get_db
from app.mcp_client.client import MCPUnavailable, connect
from app.models import ExecutionEvent, Mission, MissionStatus as S, Project, Report, TaskStatus, User, utcnow
from app.schemas import DecisionIn, MemoryIn, MemoryPatch, MissionIn, ProjectIn, TaskIn, TaskPatch
from app.services import auth as auth_svc
from app.services import context as context_svc
from app.services import decisions as decision_svc
from app.services import memory as memory_svc
from app.services import projects as project_svc
from app.services import reports as report_svc
from app.services import tasks as task_svc

router = APIRouter(prefix="/api")


def _project(db: Session, user: User, project_id: int) -> Project:
    return auth_svc.require_project(db, user, project_id)


def project_to_dict(p: Project, db: Session) -> dict[str, Any]:
    open_count = db.scalar(select(func.count()).select_from(task_svc.Task).where(task_svc.Task.project_id == p.id, task_svc.Task.status.in_(task_svc.OPEN_STATES)))
    return {"id": p.id, "name": p.name, "description": p.description, "open_tasks": open_count or 0,
            "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat()}


def mission_to_dict(m: Mission, with_events: bool = False) -> dict[str, Any]:
    d = {
        "id": m.id, "project_id": m.project_id, "request": m.request, "mission_type": m.mission_type,
        "status": m.status, "plan": m.plan, "requires_approval": m.requires_approval,
        "approved_at": m.approved_at.isoformat() if m.approved_at else None,
        "result_summary": m.result_summary, "error": m.error, "tool_calls": m.tool_calls,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "started_at": m.started_at.isoformat() if m.started_at else None,
        "completed_at": m.completed_at.isoformat() if m.completed_at else None,
    }
    if with_events:
        d["events"] = [event_to_dict(e) for e in m.events]
    return d


def event_to_dict(e: ExecutionEvent) -> dict[str, Any]:
    return {"id": e.id, "mission_id": e.mission_id, "seq": e.seq, "event_type": e.event_type, "description": e.description,
            "tool_name": e.tool_name, "result": e.result, "verification_status": e.verification_status,
            "created_at": e.created_at.isoformat() if e.created_at else None}


# --------------------------------------------------------------------------- health / me
@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name}


@router.get("/status")
async def status(user: User = Depends(current_user), token: str = Depends(get_token), db: Session = Depends(get_db)):
    """Connection status for the Settings screen. Never returns secrets."""
    s = get_settings()
    try:
        db.execute(text("SELECT 1"))
        db_status = {"ok": True, "dialect": db.get_bind().dialect.name}
    except Exception as e:  # pragma: no cover
        db_status = {"ok": False, "error": type(e).__name__}
    try:
        async with connect(s.mcp_server_url, token, connect_timeout=5) as conn:
            mcp_status = {"ok": True, "url": s.mcp_server_url, "server": conn.server_name, "protocol_version": conn.protocol_version,
                          "transport": "streamable-http", "tools": [{"name": k, "description": v["description"]} for k, v in sorted(conn.tools.items())]}
    except MCPUnavailable as e:
        mcp_status = {"ok": False, "url": s.mcp_server_url, "error": str(e)}
    return {"database": db_status, "mcp": mcp_status,
            "ai_provider": {"name": s.ai_provider, "model": s.bedrock_model_id if s.ai_provider == "bedrock" else None},
            "limits": {"max_tool_calls": s.agent_max_tool_calls, "tool_timeout_seconds": s.agent_tool_timeout_seconds,
                       "mission_timeout_seconds": s.agent_mission_timeout_seconds, "max_retries": s.agent_max_retries}}


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    projects = project_svc.list_projects(db, user)
    ids = [p.id for p in projects] or [-1]
    missions = list(db.scalars(select(Mission).where(Mission.project_id.in_(ids)).order_by(Mission.created_at.desc(), Mission.id.desc()).limit(25)))
    active = [m for m in missions if m.status not in ("completed", "failed", "partially_completed", "cancelled")]
    done = [m for m in missions if m.status in ("completed", "failed", "partially_completed", "cancelled")][:8]
    names = {p.id: p.name for p in projects}
    key_events = ("mission_completed", "mission_failed", "mission_partially_completed", "mission_cancelled", "approval_requested", "approval_received")
    events = list(db.scalars(select(ExecutionEvent).join(Mission).where(Mission.project_id.in_(ids), ExecutionEvent.event_type.in_(key_events))
                             .order_by(ExecutionEvent.id.desc()).limit(10)))
    return {
        "projects": [project_to_dict(p, db) for p in projects],
        "active_missions": [{**mission_to_dict(m), "project_name": names.get(m.project_id)} for m in active],
        "recent_missions": [{**mission_to_dict(m), "project_name": names.get(m.project_id)} for m in done],
        "recent_events": [{**event_to_dict(e), "project_name": names.get(e.mission.project_id)} for e in events],
    }


# ------------------------------------------------------------------------------ projects
@router.get("/projects")
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [project_to_dict(p, db) for p in project_svc.list_projects(db, user)]


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = project_svc.create_project(db, user, body.name, body.description)
    db.commit()
    return project_to_dict(p, db)


@router.get("/projects/{project_id}")
def get_project(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return project_to_dict(_project(db, user, project_id), db)


@router.get("/projects/{project_id}/context")
def project_context(project_id: int, focus: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return context_svc.get_project_context(db, _project(db, user, project_id), focus)


# ------------------------------------------------------------------------------ memories
@router.get("/projects/{project_id}/memories")
def list_memories(project_id: int, memory_type: str | None = None, status: str | None = None, q: str | None = None,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    return [memory_svc.memory_to_dict(m) for m in memory_svc.list_memories(db, project_id, memory_type, status, q)]


@router.post("/projects/{project_id}/memories", status_code=201)
def create_memory(project_id: int, body: MemoryIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    m = memory_svc.create_memory(db, project_id, body.content, body.memory_type, body.source or "user", body.confirmation, body.tags, body.supersedes_id)
    db.commit()
    return memory_svc.memory_to_dict(m)


def _own_memory(db: Session, user: User, memory_id: int):
    m = memory_svc.get_memory(db, memory_id)
    _project(db, user, m.project_id)
    return m


@router.patch("/memories/{memory_id}")
def patch_memory(memory_id: int, body: MemoryPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = memory_svc.update_memory(db, _own_memory(db, user, memory_id), body.model_dump(exclude_unset=True))
    db.commit()
    return memory_svc.memory_to_dict(m)


@router.delete("/memories/{memory_id}", status_code=204)
def delete_memory(memory_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    memory_svc.delete_memory(db, _own_memory(db, user, memory_id))
    db.commit()


# ----------------------------------------------------------------------------- decisions
@router.get("/projects/{project_id}/decisions")
def list_decisions(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    return [decision_svc.decision_to_dict(d) for d in decision_svc.list_decisions(db, project_id)]


@router.post("/projects/{project_id}/decisions", status_code=201)
def create_decision(project_id: int, body: DecisionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    d = decision_svc.record_decision(db, project_id, body.title, body.description, body.status, body.supersedes_decision_id)
    db.commit()
    return decision_svc.decision_to_dict(d)


# --------------------------------------------------------------------------------- tasks
@router.get("/projects/{project_id}/tasks")
def list_tasks(project_id: int, status: list[str] | None = Query(default=None), user: User = Depends(current_user), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    return [task_svc.task_to_dict(t) for t in task_svc.list_tasks(db, project_id, status)]


@router.post("/projects/{project_id}/tasks", status_code=201)
def create_task(project_id: int, body: TaskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    t, _ = task_svc.create_task(db, project_id, body.title, body.description, body.priority, body.status)
    db.commit()
    return task_svc.task_to_dict(t)


@router.patch("/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = task_svc.get_task(db, task_id)
    _project(db, user, t.project_id)
    t = task_svc.update_task(db, t, body.model_dump(exclude_unset=True))
    db.commit()
    return task_svc.task_to_dict(t)


# ------------------------------------------------------------------------------ missions
@router.get("/projects/{project_id}/missions")
def list_missions(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    rows = db.scalars(select(Mission).where(Mission.project_id == project_id).order_by(Mission.created_at.desc(), Mission.id.desc()))
    return [mission_to_dict(m) for m in rows]


@router.post("/projects/{project_id}/missions", status_code=202)
def create_mission(project_id: int, body: MissionIn, background: BackgroundTasks, user: User = Depends(current_user),
                   token: str = Depends(get_token), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    m = Mission(project_id=project_id, created_by=user.id, request=body.request.strip(), status=S.PENDING.value)
    db.add(m)
    db.flush()
    orchestrator.add_event(db, m, "mission_created", "Mission created from your request")
    db.commit()
    background.add_task(orchestrator.plan_mission, m.id, token)
    return mission_to_dict(m, with_events=True)


def _own_mission(db: Session, user: User, mission_id: int) -> Mission:
    m = db.get(Mission, mission_id)
    if m is None:
        raise HTTPException(404, "Mission not found.")
    _project(db, user, m.project_id)
    return m


@router.get("/missions/{mission_id}")
def get_mission(mission_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _own_mission(db, user, mission_id)
    d = mission_to_dict(m, with_events=True)
    d["reports"] = [report_svc.report_to_dict(r, include_content=False) for r in db.scalars(select(Report).where(Report.mission_id == m.id))]
    return d


@router.post("/missions/{mission_id}/approve", status_code=202)
def approve_mission(mission_id: int, background: BackgroundTasks, user: User = Depends(current_user),
                    token: str = Depends(get_token), db: Session = Depends(get_db)):
    m = _own_mission(db, user, mission_id)
    if m.created_by != user.id:
        raise HTTPException(403, "Only the user who created the mission can approve it.")
    if m.status != S.AWAITING_APPROVAL.value:
        raise HTTPException(409, f"Mission is '{m.status}', not awaiting approval.")
    m.approved_at = utcnow()
    transition(m, S.RUNNING)
    orchestrator.add_event(db, m, "approval_received", f"Approved by {user.name}")
    db.commit()
    background.add_task(orchestrator.run_approved_mission, m.id, token)
    return mission_to_dict(m, with_events=True)


@router.post("/missions/{mission_id}/reject")
def reject_mission(mission_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _cancel(db, user, mission_id, "Rejected by user; no changes were made", require_awaiting=True)


@router.post("/missions/{mission_id}/cancel")
def cancel_mission(mission_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _cancel(db, user, mission_id, "Cancelled by user")


def _cancel(db: Session, user: User, mission_id: int, note: str, require_awaiting: bool = False):
    m = _own_mission(db, user, mission_id)
    if require_awaiting and m.status != S.AWAITING_APPROVAL.value:
        raise HTTPException(409, f"Mission is '{m.status}', not awaiting approval.")
    try:
        transition(m, S.CANCELLED)
    except InvalidTransition as e:
        raise HTTPException(409, str(e)) from e
    m.result_summary = note
    orchestrator.add_event(db, m, "mission_cancelled", note)
    db.commit()
    return mission_to_dict(m, with_events=True)


# ------------------------------------------------------------------------------- reports
@router.get("/projects/{project_id}/reports")
def list_reports(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _project(db, user, project_id)
    rows = db.scalars(select(Report).where(Report.project_id == project_id).order_by(Report.created_at.desc(), Report.id.desc()))
    return [report_svc.report_to_dict(r, include_content=False) for r in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if r is None:
        raise HTTPException(404, "Report not found.")
    _project(db, user, r.project_id)
    return report_svc.report_to_dict(r)
