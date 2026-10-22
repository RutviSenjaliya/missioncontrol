"""Persistent project memory: storage, correction, supersession and retrieval."""
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Confirmation, Memory, MemoryStatus, MemoryType, utcnow
from app.services.errors import InvalidInput, NotFound

_VALID_TYPES = {t.value for t in MemoryType}
_VALID_CONF = {c.value for c in Confirmation}
_WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")
_STOP = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "our", "we", "is", "are", "with", "what", "use", "uses"}


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


def create_memory(
    db: Session,
    project_id: int,
    content: str,
    memory_type: str = MemoryType.SEMANTIC.value,
    source: str = "user",
    confirmation: str = Confirmation.CONFIRMED.value,
    tags: list[str] | None = None,
    supersedes_id: int | None = None,
    mission_id: int | None = None,
) -> Memory:
    content = (content or "").strip()
    if not content:
        raise InvalidInput("Memory content is required.")
    if memory_type not in _VALID_TYPES:
        raise InvalidInput(f"memory_type must be one of {sorted(_VALID_TYPES)}.")
    if confirmation not in _VALID_CONF:
        raise InvalidInput(f"confirmation must be one of {sorted(_VALID_CONF)}.")
    clean_tags = sorted({t.strip().lower() for t in (tags or []) if t and t.strip()})
    if supersedes_id is not None:
        old = db.get(Memory, supersedes_id)
        if old is None or old.project_id != project_id:
            raise InvalidInput("supersedes_id must reference a memory in the same project.")
        old.status = MemoryStatus.SUPERSEDED.value
        old.updated_at = utcnow()
    mem = Memory(
        project_id=project_id,
        memory_type=memory_type,
        content=content,
        source=source[:200],
        confirmation=confirmation,
        tags=clean_tags,
        supersedes_id=supersedes_id,
        mission_id=mission_id,
    )
    db.add(mem)
    db.flush()
    return mem


def get_memory(db: Session, memory_id: int) -> Memory:
    mem = db.get(Memory, memory_id)
    if mem is None:
        raise NotFound(f"Memory {memory_id} not found.")
    return mem


def update_memory(db: Session, mem: Memory, changes: dict[str, Any]) -> Memory:
    if "content" in changes and changes["content"] is not None:
        if not str(changes["content"]).strip():
            raise InvalidInput("Memory content cannot be empty.")
        mem.content = str(changes["content"]).strip()
    if changes.get("memory_type") is not None:
        if changes["memory_type"] not in _VALID_TYPES:
            raise InvalidInput("Invalid memory_type.")
        mem.memory_type = changes["memory_type"]
    if changes.get("confirmation") is not None:
        if changes["confirmation"] not in _VALID_CONF:
            raise InvalidInput("Invalid confirmation.")
        mem.confirmation = changes["confirmation"]
    if changes.get("status") is not None:
        if changes["status"] not in {s.value for s in MemoryStatus}:
            raise InvalidInput("Invalid status.")
        mem.status = changes["status"]
    if changes.get("tags") is not None:
        mem.tags = sorted({t.strip().lower() for t in changes["tags"] if t and t.strip()})
    mem.updated_at = utcnow()
    db.flush()
    return mem


def delete_memory(db: Session, mem: Memory) -> None:
    # Records that pointed at this one keep working (FK is SET NULL). Retrieval reads the
    # table directly, so there is no separate index/cache to invalidate.
    db.delete(mem)
    db.flush()


def list_memories(
    db: Session,
    project_id: int,
    memory_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> list[Memory]:
    stmt = select(Memory).where(Memory.project_id == project_id)
    if memory_type:
        stmt = stmt.where(Memory.memory_type == memory_type)
    if status:
        stmt = stmt.where(Memory.status == status)
    stmt = stmt.order_by(Memory.updated_at.desc(), Memory.id.desc())
    rows = list(db.scalars(stmt))
    if q:
        terms = _tokens(q)
        rows = [m for m in rows if terms & (_tokens(m.content) | set(m.tags))] if terms else rows
    return rows


def search_memory(db: Session, project_id: int, query: str, limit: int = 10, include_superseded: bool = False) -> list[tuple[Memory, float]]:
    """Keyword relevance search scoped to ONE project.

    Score = matched-term ratio, boosted for tag matches and confirmed records. Superseded
    memories are excluded unless explicitly requested so outdated facts do not drive planning.
    """
    if not query or not query.strip():
        raise InvalidInput("query is required.")
    limit = max(1, min(int(limit), 50))
    terms = _tokens(query)
    stmt = select(Memory).where(Memory.project_id == project_id)
    if not include_superseded:
        stmt = stmt.where(Memory.status == MemoryStatus.ACTIVE.value)
    scored: list[tuple[Memory, float]] = []
    for m in db.scalars(stmt):
        words = _tokens(m.content)
        tags = set(m.tags or [])
        hits = len(terms & words) + 1.5 * len(terms & tags)
        if hits == 0:
            continue
        score = hits / max(len(terms), 1)
        if m.confirmation == Confirmation.CONFIRMED.value:
            score *= 1.1
        scored.append((m, round(score, 3)))
    scored.sort(key=lambda x: (x[1], x[0].updated_at, x[0].id), reverse=True)
    return scored[:limit]


def memory_to_dict(m: Memory) -> dict[str, Any]:
    return {
        "id": m.id,
        "project_id": m.project_id,
        "memory_type": m.memory_type,
        "content": m.content,
        "source": m.source,
        "status": m.status,
        "confirmation": m.confirmation,
        "tags": m.tags or [],
        "supersedes_id": m.supersedes_id,
        "mission_id": m.mission_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
