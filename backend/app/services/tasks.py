"""Project tasks with idempotent creation."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Priority, Task, TaskStatus, utcnow
from app.services.errors import InvalidInput, NotFound

_STATUS = {s.value for s in TaskStatus}
_PRIORITY = {p.value for p in Priority}
OPEN_STATES = [TaskStatus.OPEN.value, TaskStatus.IN_PROGRESS.value, TaskStatus.BLOCKED.value]


def create_task(
    db: Session,
    project_id: int,
    title: str,
    description: str = "",
    priority: str = Priority.MEDIUM.value,
    status: str = TaskStatus.OPEN.value,
    idempotency_key: str | None = None,
) -> tuple[Task, bool]:
    """Returns (task, created). With an idempotency key, a repeat call returns the original task."""
    title = (title or "").strip()
    if not title:
        raise InvalidInput("Task title is required.")
    if priority not in _PRIORITY:
        raise InvalidInput(f"priority must be one of {sorted(_PRIORITY)}.")
    if status not in _STATUS:
        raise InvalidInput(f"status must be one of {sorted(_STATUS)}.")
    if idempotency_key:
        existing = db.scalar(
            select(Task).where(Task.project_id == project_id, Task.idempotency_key == idempotency_key)
        )
        if existing:
            return existing, False
    t = Task(
        project_id=project_id,
        title=title[:300],
        description=(description or "").strip(),
        priority=priority,
        status=status,
        idempotency_key=idempotency_key,
        completed_at=utcnow() if status == TaskStatus.DONE.value else None,
    )
    db.add(t)
    db.flush()
    return t, True


def get_task(db: Session, task_id: int) -> Task:
    t = db.get(Task, task_id)
    if t is None:
        raise NotFound(f"Task {task_id} not found.")
    return t


def update_task(db: Session, task: Task, changes: dict[str, Any]) -> Task:
    if changes.get("title") is not None:
        if not str(changes["title"]).strip():
            raise InvalidInput("Task title cannot be empty.")
        task.title = str(changes["title"]).strip()[:300]
    if changes.get("description") is not None:
        task.description = str(changes["description"]).strip()
    if changes.get("priority") is not None:
        if changes["priority"] not in _PRIORITY:
            raise InvalidInput(f"priority must be one of {sorted(_PRIORITY)}.")
        task.priority = changes["priority"]
    if changes.get("status") is not None:
        if changes["status"] not in _STATUS:
            raise InvalidInput(f"status must be one of {sorted(_STATUS)}.")
        task.status = changes["status"]
        task.completed_at = utcnow() if task.status == TaskStatus.DONE.value else None
    task.updated_at = utcnow()
    db.flush()
    return task


_PRIO_ORDER = {"high": 0, "medium": 1, "low": 2}


def list_tasks(db: Session, project_id: int, status: list[str] | None = None) -> list[Task]:
    stmt = select(Task).where(Task.project_id == project_id)
    if status:
        stmt = stmt.where(Task.status.in_(status))
    rows = list(db.scalars(stmt.order_by(Task.created_at.asc(), Task.id.asc())))
    rows.sort(key=lambda t: (t.status == TaskStatus.DONE.value, _PRIO_ORDER.get(t.priority, 9)))
    return rows


def task_to_dict(t: Task) -> dict[str, Any]:
    return {
        "id": t.id,
        "project_id": t.project_id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }
