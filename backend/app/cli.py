"""Management commands.

  python -m app.cli seed            # create the demo user (token from DEMO_USER_TOKEN)
  python -m app.cli seed --demo     # ...plus a realistic demo project
  python -m app.cli create-user NAME  # prints a new API token once
"""
import argparse
import sys

from sqlalchemy import select

from app.config import get_settings
from app.db.session import session_scope
from app.models import Project, User
from app.services import auth as auth_svc
from app.services import decisions as decision_svc
from app.services import memory as memory_svc
from app.services import projects as project_svc
from app.services import tasks as task_svc


def seed(with_demo: bool) -> None:
    s = get_settings()
    with session_scope() as db:
        user = auth_svc.user_from_token(db, s.demo_user_token)
        if user is None:
            user = auth_svc.create_user(db, s.demo_user_name, s.demo_user_token)
            print(f"Created user '{user.name}' (id {user.id}). Sign in with DEMO_USER_TOKEN from your .env.")
        else:
            print(f"User '{user.name}' already exists (id {user.id}).")
        if not with_demo:
            return
        if db.scalar(select(Project).where(Project.owner_id == user.id, Project.name == "Campus Events App")):
            print("Demo project already exists.")
            return
        p = project_svc.create_project(db, user, "Campus Events App",
                                       "A web app where students discover, RSVP to and organise campus events.")
        for content, tags in [
            ("Help students find and join campus events in under a minute.", ["goal"]),
            ("Launch a working beta for the spring semester.", ["goal"]),
            ("Frontend: React + TypeScript (Vite)", ["stack"]),
            ("Backend: Python FastAPI", ["stack"]),
            ("Database: PostgreSQL", ["stack"]),
            ("Hosting budget is under $50 per month.", ["constraint"]),
            ("Must work well on mobile browsers.", ["constraint"]),
        ]:
            memory_svc.create_memory(db, p.id, content, tags=tags, source="seed")
        memory_svc.create_memory(db, p.id, "Release checklist: run tests, run migrations, smoke-test RSVP flow, then deploy.",
                                 memory_type="procedural", source="seed", tags=["release"])
        old = decision_svc.record_decision(db, p.id, "Use Flask for the backend", "Initial choice for speed.", source="seed")
        decision_svc.record_decision(db, p.id, "Migrate backend to FastAPI", "Async support and automatic OpenAPI docs.",
                                     supersedes_decision_id=old.id, source="seed")
        decision_svc.record_decision(db, p.id, "Use PostgreSQL as the single source of truth", "Shared by API and background jobs.", source="seed")
        for title, prio, status in [
            ("Build RSVP API endpoints", "high", "in_progress"),
            ("Design event card component", "medium", "open"),
            ("Set up CI pipeline", "medium", "blocked"),
            ("Write onboarding copy", "low", "open"),
            ("Create database schema", "high", "done"),
        ]:
            task_svc.create_task(db, p.id, title, priority=prio, status=status)
        print(f"Created demo project '{p.name}' (id {p.id}).")


def create_user(name: str) -> None:
    token = auth_svc.new_token()
    with session_scope() as db:
        u = auth_svc.create_user(db, name, token)
        print(f"Created user '{u.name}' (id {u.id}).\nAPI token (shown once): {token}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("seed")
    sp.add_argument("--demo", action="store_true", help="also create a demo project")
    cu = sub.add_parser("create-user")
    cu.add_argument("name")
    args = ap.parse_args(argv)
    if args.cmd == "seed":
        seed(args.demo)
    elif args.cmd == "create-user":
        create_user(args.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
