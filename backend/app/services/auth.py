"""Token authentication and project-level authorization.

Authorization is always checked server-side from the authenticated user, never from a
project id supplied by the frontend or by the model alone.
"""
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, User
from app.services.errors import Forbidden, NotFound


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(24)


def create_user(db: Session, name: str, token: str) -> User:
    user = User(name=name, token_hash=hash_token(token))
    db.add(user)
    db.flush()
    return user


def user_from_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    return db.scalar(select(User).where(User.token_hash == hash_token(token)))


def parse_bearer(header_value: str | None) -> str | None:
    if not header_value:
        return None
    scheme, _, value = header_value.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def require_project(db: Session, user: User, project_id: int) -> Project:
    """Return the project if it exists AND the user is a member; otherwise raise."""
    if not isinstance(project_id, int) or project_id <= 0:
        raise NotFound("Project not found.")
    project = db.get(Project, project_id)
    if project is None:
        raise NotFound(f"Project {project_id} not found.")
    member = db.get(ProjectMember, {"project_id": project_id, "user_id": user.id})
    if member is None:
        # Same message shape as not-found would leak less, but explicit 403 helps debugging; we
        # deliberately do not reveal project contents either way.
        raise Forbidden("You do not have access to this project.")
    return project
