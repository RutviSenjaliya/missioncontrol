"""Grounded report generation and independent verification.

Report text is assembled ONLY from records in the database. Every task and decision the
report mentions carries an explicit reference such as "(task #12)" so verification can prove
that each referenced record really exists in this project.
"""
import re
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Decision, Project, Report, Task, VerificationStatus
from app.services.context import get_project_context
from app.services.errors import InvalidInput, NotFound

NONE = "_None recorded._"


def _lines(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else NONE


def _task_line(t: dict[str, Any]) -> str:
    extra = f" — {t['description']}" if t.get("description") else ""
    return f"{t['title']} [{t['priority']}, {t['status'].replace('_', ' ')}] (task #{t['id']}){extra}"


def _decision_line(d: dict[str, Any]) -> str:
    extra = f": {d['description']}" if d.get("description") else ""
    return f"{d['title']}{extra} (decision #{d['id']})"


def s_summary(c: dict) -> str:
    p = c["project"]
    goals = [g["content"] for g in c["goals"]]
    body = p["description"] or NONE
    if goals:
        body += "\n\n**Goals**\n" + _lines(goals)
    return body


def s_stack(c: dict) -> str:
    return _lines([m["content"] for m in c["tech_stack"]])


def s_decisions(c: dict) -> str:
    return _lines([_decision_line(d) for d in c["confirmed_decisions"]])


def s_open_tasks(c: dict) -> str:
    return _lines([_task_line(t) for t in c["open_tasks"]])


def s_blockers(c: dict) -> str:
    return _lines([_task_line(t) for t in c["blocked_tasks"]])


def s_next_steps(c: dict) -> str:
    steps = [f"Unblock: {t['title']} (task #{t['id']})" for t in c["blocked_tasks"]]
    steps += [f"Continue: {t['title']} (task #{t['id']})" for t in c["open_tasks"][:3]]
    return _lines(steps)


def s_progress(c: dict) -> str:
    done = [f"Completed: {t['title']} (task #{t['id']})" for t in c["recently_completed_tasks"]]
    missions = [f"Mission #{m['id']} {m['status'].replace('_', ' ')}: {m['request'][:90]}" for m in c["recent_missions"] if m["status"] in ("completed", "partially_completed")]
    return _lines(done + missions)


def s_constraints(c: dict) -> str:
    return _lines([m["content"] for m in c["constraints"]])


def s_sprint_goal(c: dict) -> str:
    high = [t for t in c["open_tasks"] if t["priority"] == "high"]
    goal = c["goals"][0]["content"] if c["goals"] else None
    if not goal and not c["open_tasks"]:
        return NONE
    parts = []
    if goal:
        parts.append(f"Advance the project goal: {goal}")
    if c["open_tasks"]:
        parts.append(f"Finish {len(high) or min(3, len(c['open_tasks']))} priority task(s) listed below.")
    if c["blocked_tasks"]:
        parts.append(f"Clear {len(c['blocked_tasks'])} blocker(s).")
    return " ".join(parts)


def s_sprint_tasks(c: dict) -> str:
    return _lines([_task_line(t) for t in c["open_tasks"][:6]])


SECTION_BUILDERS: dict[str, Callable[[dict], str]] = {
    "Project Summary": s_summary,
    "Technology Stack": s_stack,
    "Confirmed Decisions": s_decisions,
    "Relevant Decisions": s_decisions,
    "Open Tasks": s_open_tasks,
    "Blockers": s_blockers,
    "Next Steps": s_next_steps,
    "Recent Progress": s_progress,
    "Constraints": s_constraints,
    "Sprint Goal": s_sprint_goal,
    "Planned Tasks": s_sprint_tasks,
}

TEMPLATES: dict[str, list[str]] = {
    "handoff": ["Project Summary", "Technology Stack", "Confirmed Decisions", "Open Tasks", "Blockers", "Next Steps"],
    "sprint_plan": ["Sprint Goal", "Planned Tasks", "Relevant Decisions", "Constraints", "Blockers"],
    "progress": ["Project Summary", "Recent Progress", "Open Tasks", "Blockers"],
}


def build_report_markdown(context: dict, title: str, sections: list[str]) -> str:
    out = [f"# {title}", "", f"Project: {context['project']['name']} (project #{context['project']['id']})", ""]
    for name in sections:
        out += [f"## {name}", "", SECTION_BUILDERS[name](context), ""]
    if context.get("missing_information"):
        out += ["## Data Gaps", "", _lines(context["missing_information"]), ""]
    return "\n".join(out).rstrip() + "\n"


def generate_report(
    db: Session,
    project: Project,
    title: str,
    required_sections: list[str],
    mission_id: int | None = None,
    idempotency_key: str | None = None,
) -> tuple[Report, bool]:
    title = (title or "").strip()
    if not title:
        raise InvalidInput("title is required.")
    if not required_sections:
        raise InvalidInput("required_sections must not be empty.")
    unknown = [s for s in required_sections if s not in SECTION_BUILDERS]
    if unknown:
        raise InvalidInput(f"Unknown sections {unknown}. Supported: {sorted(SECTION_BUILDERS)}.")
    if idempotency_key:
        existing = db.scalar(select(Report).where(Report.project_id == project.id, Report.idempotency_key == idempotency_key))
        if existing:
            return existing, False
    ctx = get_project_context(db, project)
    report = Report(
        project_id=project.id,
        mission_id=mission_id,
        title=title[:300],
        content=build_report_markdown(ctx, title, required_sections),
        required_sections=list(required_sections),
        idempotency_key=idempotency_key,
    )
    db.add(report)
    db.flush()
    return report, True


_HEADING = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
_TASK_REF = re.compile(r"\(task #(\d+)\)")
_DECISION_REF = re.compile(r"\(decision #(\d+)\)")


def verify_report(db: Session, project: Project, report_id: int, required_sections: list[str] | None = None) -> dict[str, Any]:
    """Re-read the persisted report from the database and check it independently."""
    db.expire_all()  # never trust objects cached by the generating call
    checks: list[dict[str, Any]] = []
    report = db.get(Report, report_id)
    checks.append({"check": "report_persisted", "passed": report is not None, "detail": f"report #{report_id} read back from database"})
    if report is None:
        return {"report_id": report_id, "passed": False, "checks": checks}
    same_project = report.project_id == project.id
    checks.append({"check": "belongs_to_project", "passed": same_project, "detail": f"report project #{report.project_id}"})
    if not same_project:
        raise NotFound(f"Report {report_id} not found in this project.")

    required = required_sections or report.required_sections or []
    bodies: dict[str, str] = {}
    matches = list(_HEADING.finditer(report.content))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(report.content)
        bodies[m.group(1)] = report.content[m.end():end].strip()
    for name in required:
        present = name in bodies
        checks.append({"check": f"section:{name}", "passed": present and bool(bodies.get(name)), "detail": "present" if present else "missing"})

    task_ids = {int(x) for x in _TASK_REF.findall(report.content)}
    dec_ids = {int(x) for x in _DECISION_REF.findall(report.content)}
    if task_ids:
        found = set(db.scalars(select(Task.id).where(Task.project_id == project.id, Task.id.in_(task_ids))))
        missing = sorted(task_ids - found)
        checks.append({"check": "task_references_exist", "passed": not missing, "detail": f"{len(found)}/{len(task_ids)} referenced tasks found" + (f"; missing {missing}" if missing else "")})
    if dec_ids:
        found = set(db.scalars(select(Decision.id).where(Decision.project_id == project.id, Decision.id.in_(dec_ids))))
        missing = sorted(dec_ids - found)
        checks.append({"check": "decision_references_exist", "passed": not missing, "detail": f"{len(found)}/{len(dec_ids)} referenced decisions found" + (f"; missing {missing}" if missing else "")})

    passed = all(c["passed"] for c in checks)
    report.verification_status = VerificationStatus.PASSED.value if passed else VerificationStatus.FAILED.value
    report.verification_details = {"checks": checks}
    db.flush()
    return {"report_id": report.id, "title": report.title, "passed": passed, "checks": checks}


def report_to_dict(r: Report, include_content: bool = True) -> dict[str, Any]:
    d = {
        "id": r.id,
        "project_id": r.project_id,
        "mission_id": r.mission_id,
        "title": r.title,
        "required_sections": r.required_sections or [],
        "verification_status": r.verification_status,
        "verification_details": r.verification_details,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
    if include_content:
        d["content"] = r.content
    return d
