"""Builds the grounded project context the agent plans with.

Only current information is returned by default: superseded memories and decisions are
excluded so the agent never treats an outdated fact as current.
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DecisionStatus,
    Memory,
    MemoryStatus,
    MemoryType,
    Mission,
    Project,
    Report,
    TaskStatus,
)
from app.services import decisions as decision_svc
from app.services import memory as memory_svc
from app.services import tasks as task_svc

STACK_TAGS = {"stack", "tech_stack", "technology"}
GOAL_TAGS = {"goal", "objective"}
CONSTRAINT_TAGS = {"constraint", "requirement"}


def _brief(m: Memory) -> dict[str, Any]:
    return {"id": m.id, "content": m.content, "confirmation": m.confirmation, "source": m.source, "tags": m.tags or []}


def get_project_context(db: Session, project: Project, focus: str | None = None) -> dict[str, Any]:
    active = list(
        db.scalars(
            select(Memory)
            .where(Memory.project_id == project.id, Memory.status == MemoryStatus.ACTIVE.value)
            .order_by(Memory.updated_at.desc(), Memory.id.desc())
        )
    )
    semantic = [m for m in active if m.memory_type == MemoryType.SEMANTIC.value]

    def tagged(tags: set[str]) -> list[dict[str, Any]]:
        return [_brief(m) for m in semantic if tags & set(m.tags or [])]

    stack, goals, constraints = tagged(STACK_TAGS), tagged(GOAL_TAGS), tagged(CONSTRAINT_TAGS)
    used = {x["id"] for x in stack + goals + constraints}
    other_facts = [_brief(m) for m in semantic if m.id not in used]

    all_decisions = decision_svc.list_decisions(db, project.id)
    confirmed = [d for d in all_decisions if d.status == DecisionStatus.CONFIRMED.value]
    proposed = [d for d in all_decisions if d.status == DecisionStatus.PROPOSED.value]

    tasks = task_svc.list_tasks(db, project.id)
    open_tasks = [t for t in tasks if t.status in (TaskStatus.OPEN.value, TaskStatus.IN_PROGRESS.value)]
    blocked = [t for t in tasks if t.status == TaskStatus.BLOCKED.value]
    done = sorted(
        [t for t in tasks if t.status == TaskStatus.DONE.value],
        key=lambda t: (t.completed_at or t.updated_at),
        reverse=True,
    )[:5]

    missions = list(
        db.scalars(
            select(Mission).where(Mission.project_id == project.id).order_by(Mission.created_at.desc(), Mission.id.desc()).limit(5)
        )
    )
    reports = list(
        db.scalars(select(Report).where(Report.project_id == project.id).order_by(Report.created_at.desc(), Report.id.desc()).limit(5))
    )
    episodic = [_brief(m) for m in active if m.memory_type == MemoryType.EPISODIC.value][:5]
    procedures = [_brief(m) for m in active if m.memory_type == MemoryType.PROCEDURAL.value]

    missing = []
    if not stack:
        missing.append("No technology stack recorded (tag a memory with 'stack').")
    if not goals:
        missing.append("No project goals recorded (tag a memory with 'goal').")
    if not confirmed:
        missing.append("No confirmed decisions recorded.")
    if not tasks:
        missing.append("No tasks recorded.")

    ctx: dict[str, Any] = {
        "project": {"id": project.id, "name": project.name, "description": project.description},
        "goals": goals,
        "tech_stack": stack,
        "constraints": constraints,
        "facts": other_facts,
        "procedures": procedures,
        "confirmed_decisions": [decision_svc.decision_to_dict(d) for d in confirmed],
        "proposed_decisions": [decision_svc.decision_to_dict(d) for d in proposed],
        "superseded_decision_count": sum(1 for d in all_decisions if d.status == DecisionStatus.SUPERSEDED.value),
        "open_tasks": [task_svc.task_to_dict(t) for t in open_tasks],
        "blocked_tasks": [task_svc.task_to_dict(t) for t in blocked],
        "recently_completed_tasks": [task_svc.task_to_dict(t) for t in done],
        "recent_missions": [
            {"id": m.id, "request": m.request, "status": m.status, "result_summary": m.result_summary}
            for m in missions
        ],
        "recent_reports": [
            {"id": r.id, "title": r.title, "verification_status": r.verification_status, "created_at": r.created_at.isoformat()}
            for r in reports
        ],
        "recent_events": episodic,
        "missing_information": missing,
    }
    if focus and focus.strip():
        try:
            ctx["relevant_memories"] = [
                {**_brief(m), "score": s} for m, s in memory_svc.search_memory(db, project.id, focus, limit=8)
            ]
        except Exception:
            ctx["relevant_memories"] = []
    return ctx
