"""Project decisions with explicit supersession history."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Decision, DecisionStatus, utcnow
from app.services.errors import InvalidInput

_VALID = {s.value for s in DecisionStatus}


def record_decision(
    db: Session,
    project_id: int,
    title: str,
    description: str = "",
    status: str = DecisionStatus.CONFIRMED.value,
    supersedes_decision_id: int | None = None,
    source: str = "user",
) -> Decision:
    title = (title or "").strip()
    if not title:
        raise InvalidInput("Decision title is required.")
    if status not in {DecisionStatus.CONFIRMED.value, DecisionStatus.PROPOSED.value}:
        raise InvalidInput("status must be 'confirmed' or 'proposed'.")
    if supersedes_decision_id is not None:
        old = db.get(Decision, supersedes_decision_id)
        if old is None or old.project_id != project_id:
            raise InvalidInput("supersedes_decision_id must reference a decision in the same project.")
        if old.status == DecisionStatus.SUPERSEDED.value:
            raise InvalidInput(f"Decision {old.id} is already superseded.")
        if status == DecisionStatus.CONFIRMED.value:
            old.status = DecisionStatus.SUPERSEDED.value
            old.updated_at = utcnow()
    d = Decision(
        project_id=project_id,
        title=title[:300],
        description=(description or "").strip(),
        status=status,
        supersedes_decision_id=supersedes_decision_id,
        source=source[:200],
    )
    db.add(d)
    db.flush()
    return d


def list_decisions(db: Session, project_id: int, current_only: bool = False) -> list[Decision]:
    stmt = select(Decision).where(Decision.project_id == project_id)
    if current_only:
        stmt = stmt.where(Decision.status == DecisionStatus.CONFIRMED.value)
    return list(db.scalars(stmt.order_by(Decision.created_at.desc(), Decision.id.desc())))


def decision_to_dict(d: Decision) -> dict[str, Any]:
    return {
        "id": d.id,
        "project_id": d.project_id,
        "title": d.title,
        "description": d.description,
        "status": d.status,
        "source": d.source,
        "supersedes_decision_id": d.supersedes_decision_id,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }
