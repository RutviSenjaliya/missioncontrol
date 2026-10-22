from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project, ProjectMember, User
from app.services.errors import InvalidInput


def create_project(db: Session, user: User, name: str, description: str = "") -> Project:
    name = (name or "").strip()
    if not name:
        raise InvalidInput("Project name is required.")
    project = Project(name=name[:200], description=(description or "").strip(), owner_id=user.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id))
    db.flush()
    return project


def list_projects(db: Session, user: User) -> list[Project]:
    stmt = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .order_by(Project.updated_at.desc())
    )
    return list(db.scalars(stmt))
