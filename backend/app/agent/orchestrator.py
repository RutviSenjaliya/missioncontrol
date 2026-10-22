"""Agent orchestration: context -> plan -> approval -> MCP execution -> verification -> memory.

Every timeline event written here corresponds to a real operation that happened. Nothing is
recorded as successful unless the MCP server returned success, and a mission is only marked
completed when its verification checks pass on data read back from the database.
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any

import anyio
from sqlalchemy.orm import Session

from app.agent.providers import APPROVAL_TOOLS, WRITE_TOOLS, PlanningError, get_provider
from app.agent.state import transition
from app.config import Settings, get_settings
from app.db.session import SessionLocal
from app.mcp_client.client import MCPConnection, MCPUnavailable, ToolResult, connect
from app.models import ExecutionEvent, Mission, MissionStatus as S, MemoryType, VerificationStatus, utcnow
from app.services import memory as memory_svc

log = logging.getLogger("missioncontrol.agent")
RETRYABLE_PREFIXES = ("timeout", "server_error")
CHECK_TYPES = {"report_verified", "task_in_open_list", "task_status", "decision_current", "read_only"}


class PlanValidationError(Exception):
    pass


# --------------------------------------------------------------------------- event helpers
def _compact(data: Any, limit: int = 6000) -> Any:
    """Keep event payloads bounded so logs never copy large blobs of project data."""
    try:
        raw = json.dumps(data, default=str)
    except TypeError:
        return {"note": "unserialisable result"}
    if len(raw) <= limit:
        return data
    return {"truncated": True, "preview": raw[:limit]}


def add_event(db: Session, mission: Mission, event_type: str, description: str, *, tool: str | None = None,
              result: Any = None, verification: str | None = None) -> ExecutionEvent:
    seq = (max((e.seq for e in mission.events), default=0)) + 1
    ev = ExecutionEvent(mission_id=mission.id, seq=seq, event_type=event_type, description=description,
                        tool_name=tool, result=_compact(result) if result is not None else None,
                        verification_status=verification)
    mission.events.append(ev)
    db.commit()  # commit each event so the UI timeline updates live
    return ev


def _context_digest(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "goals": len(ctx.get("goals", [])),
        "tech_stack": len(ctx.get("tech_stack", [])),
        "constraints": len(ctx.get("constraints", [])),
        "confirmed_decisions": [d["id"] for d in ctx.get("confirmed_decisions", [])],
        "open_tasks": [t["id"] for t in ctx.get("open_tasks", [])],
        "blocked_tasks": [t["id"] for t in ctx.get("blocked_tasks", [])],
        "recent_reports": [r["id"] for r in ctx.get("recent_reports", [])],
        "relevant_memories": [m["id"] for m in ctx.get("relevant_memories", [])],
        "missing_information": ctx.get("missing_information", []),
    }


# ------------------------------------------------------------------------- plan validation
def validate_plan(plan: dict[str, Any], tools: dict[str, dict[str, Any]], project_id: int, settings: Settings) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise PlanValidationError("Plan must be an object.")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PlanValidationError("Plan has no steps.")
    if len(steps) > settings.agent_max_tool_calls - 1:
        raise PlanValidationError(f"Plan has {len(steps)} steps; the limit is {settings.agent_max_tool_calls - 1}.")
    clean = copy.deepcopy(plan)
    seen_write = False
    verified_after_write = True
    for i, s in enumerate(clean["steps"], start=1):
        if not isinstance(s, dict) or s.get("tool") not in tools:
            raise PlanValidationError(f"Step {i} uses a tool the MCP server does not advertise: {s.get('tool') if isinstance(s, dict) else s!r}.")
        if not isinstance(s.get("args"), dict):
            raise PlanValidationError(f"Step {i} args must be an object.")
        s["n"] = i
        s["args"]["project_id"] = project_id  # the plan can never target another project
        s.setdefault("role", "action")
        if s["tool"] in WRITE_TOOLS:
            seen_write, verified_after_write = True, False
        chk = s.get("check")
        if chk is not None and (not isinstance(chk, dict) or chk.get("type") not in CHECK_TYPES):
            raise PlanValidationError(f"Step {i} has an unknown verification check.")
        if s["role"] == "verify" and chk and chk["type"] != "read_only":
            verified_after_write = True
    if seen_write and not verified_after_write:
        raise PlanValidationError("Every write must be followed by a verification step.")
    clean["requires_approval"] = any(s["tool"] in APPROVAL_TOOLS for s in clean["steps"])  # decided by the app, not the model
    return clean


# ------------------------------------------------------------------------ step utilities
def _resolve(value: Any, outputs: dict[int, dict[str, Any]]) -> Any:
    if isinstance(value, str) and value.startswith("$") and "." in value:
        head, *path = value[1:].split(".")
        if head.isdigit() and int(head) in outputs:
            cur: Any = outputs[int(head)]
            for p in path:
                if not isinstance(cur, dict) or p not in cur:
                    raise PlanValidationError(f"Reference {value} could not be resolved.")
                cur = cur[p]
            return cur
        raise PlanValidationError(f"Reference {value} points to a step that has not produced output.")
    if isinstance(value, dict):
        return {k: _resolve(v, outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, outputs) for v in value]
    return value


def evaluate_check(check: dict[str, Any], data: dict[str, Any], outputs: dict[int, dict[str, Any]]) -> tuple[bool, str]:
    c = _resolve(check, outputs)
    t = c["type"]
    if t == "report_verified":
        n_ok = sum(1 for x in data.get("checks", []) if x.get("passed"))
        return bool(data.get("passed")), f"{n_ok}/{len(data.get('checks', []))} report checks passed"
    if t == "task_in_open_list":
        ids = [x["id"] for x in data.get("tasks", [])]
        ok = c.get("task_id") in ids
        return ok, f"task #{c.get('task_id')} {'found' if ok else 'NOT found'} in {len(ids)} open tasks read back"
    if t == "task_status":
        everything = data.get("open_tasks", []) + data.get("blocked_tasks", []) + data.get("recently_completed_tasks", [])
        match = next((x for x in everything if x["id"] == c.get("task_id")), None)
        ok = match is not None and match["status"] == c.get("status")
        return ok, f"task #{c.get('task_id')} read back with status '{match['status'] if match else 'not found'}' (expected '{c.get('status')}')"
    if t == "decision_current":
        current = [d["id"] for d in data.get("confirmed_decisions", [])]
        ok = c.get("decision_id") in current
        detail = f"decision #{c.get('decision_id')} {'is' if ok else 'is NOT'} current"
        if c.get("superseded_id"):
            gone = c["superseded_id"] not in current
            ok = ok and gone
            detail += f"; decision #{c['superseded_id']} {'no longer current' if gone else 'STILL current'}"
        return ok, detail
    return True, "read-only step"


def _describe(tool: str, data: dict[str, Any]) -> str:
    if tool == "generate_project_report":
        return f"Report #{data.get('report_id')} '{data.get('title')}' {'saved' if data.get('created') else 'already existed (idempotent retry)'}"
    if tool == "create_task":
        t = data.get("task", {})
        return f"Task #{t.get('id')} '{t.get('title')}' {'created' if data.get('created') else 'already existed (idempotent retry)'}"
    if tool == "update_task":
        t = data.get("task", {})
        return f"Task #{t.get('id')} now '{t.get('status')}'"
    if tool == "record_decision":
        d = data.get("decision", {})
        return f"Decision #{d.get('id')} '{d.get('title')}' stored"
    if tool == "list_open_tasks":
        return f"{data.get('count', 0)} unfinished task(s) read"
    if tool == "search_memory":
        return f"{data.get('count', 0)} memory record(s) matched"
    if tool == "verify_report":
        return f"Report #{data.get('report_id')} read back for verification"
    if tool == "get_project_context":
        return "Project context read back"
    return "Tool succeeded"


async def _call_with_retry(conn: MCPConnection, step: dict[str, Any], args: dict[str, Any], db: Session, mission: Mission, settings: Settings) -> ToolResult:
    safe = step["role"] in ("read", "verify") or "idempotency_key" in args
    attempts = 1 + (settings.agent_max_retries if safe else 0)
    res = ToolResult(False, None, "not attempted")
    for attempt in range(1, attempts + 1):
        if mission.tool_calls >= settings.agent_max_tool_calls:
            return ToolResult(False, None, f"limit_exceeded: mission reached {settings.agent_max_tool_calls} tool calls")
        mission.tool_calls += 1
        res = await conn.call(step["tool"], args)
        if res.ok:
            return res
        retry = attempt < attempts and (res.error or "").startswith(RETRYABLE_PREFIXES)
        add_event(db, mission, "tool_failed", f"Step {step['n']}: {step['tool']} failed (attempt {attempt}/{attempts}): {res.error}" + (" — retrying" if retry else ""),
                  tool=step["tool"], result={"arguments": args, "error": res.error}, verification=None)
        if not retry:
            break
    return res


# ----------------------------------------------------------------------------- phases
async def plan_mission(mission_id: int, token: str, settings: Settings | None = None) -> None:
    """RECEIVED -> validate -> connect MCP -> retrieve context -> plan -> (await approval | execute)."""
    settings = settings or get_settings()
    db = SessionLocal()
    try:
        mission = db.get(Mission, mission_id)
        if mission is None or mission.status != S.PENDING.value:
            return
        transition(mission, S.PLANNING)
        add_event(db, mission, "planning_started", "Mission validated; connecting to the MCP server")
        try:
            async with connect(settings.mcp_server_url, token, settings.agent_tool_timeout_seconds) as conn:
                add_event(db, mission, "mcp_connected", f"Connected to MCP server '{conn.server_name}' (protocol {conn.protocol_version}); {len(conn.tools)} tools discovered",
                          result={"protocol_version": conn.protocol_version, "server": conn.server_name, "tools": sorted(conn.tools)})
                mission.tool_calls += 1
                ctx_res = await conn.call("get_project_context", {"project_id": mission.project_id, "focus": mission.request[:500]})
                if not ctx_res.ok:
                    add_event(db, mission, "context_failed", f"Context retrieval failed: {ctx_res.error}", tool="get_project_context", result={"error": ctx_res.error})
                    return _finish(db, mission, S.FAILED, f"Could not retrieve project context: {ctx_res.error}")
                ctx = ctx_res.data or {}
                add_event(db, mission, "context_retrieved", "Project context retrieved from persistent storage via MCP", tool="get_project_context", result=_context_digest(ctx))
                try:
                    provider = get_provider(settings)
                    raw = provider.plan(mission.request, ctx, conn.tools)
                    plan = validate_plan(raw, conn.tools, mission.project_id, settings)
                    plan["provider"] = provider.name
                except (PlanningError, PlanValidationError) as e:
                    add_event(db, mission, "planning_failed", str(e))
                    return _finish(db, mission, S.FAILED, f"Planning failed: {e}")
                except Exception as e:  # provider/network errors
                    log.exception("provider error")
                    add_event(db, mission, "planning_failed", f"AI provider error: {type(e).__name__}")
                    return _finish(db, mission, S.FAILED, f"AI provider error: {type(e).__name__}: {e}")
                mission.plan = plan
                mission.mission_type = plan.get("mission_type")
                mission.requires_approval = plan["requires_approval"]
                add_event(db, mission, "plan_generated", f"Plan with {len(plan['steps'])} step(s): {plan.get('summary', '')}", result={"steps": [f"{s['n']}. {s['tool']} — {s['purpose']}" for s in plan["steps"]]})
                if plan["requires_approval"]:
                    transition(mission, S.AWAITING_APPROVAL)
                    add_event(db, mission, "approval_requested", "This mission changes project records and is waiting for your approval")
                    db.commit()
                    return
                transition(mission, S.RUNNING)
                db.commit()
                await _execute(db, mission, conn, settings)
        except MCPUnavailable as e:
            add_event(db, mission, "mcp_unavailable", str(e))
            _finish(db, mission, S.FAILED, str(e))
    except Exception as e:  # last-resort guard: never leave a mission stuck in a running state
        log.exception("mission %s crashed", mission_id)
        db.rollback()
        m = db.get(Mission, mission_id)
        if m and m.status not in {s.value for s in (S.COMPLETED, S.FAILED, S.PARTIALLY_COMPLETED, S.CANCELLED)}:
            m.status = S.FAILED.value
            m.error = f"Internal error: {type(e).__name__}"
            m.completed_at = utcnow()
            db.commit()
    finally:
        db.close()


async def run_approved_mission(mission_id: int, token: str, settings: Settings | None = None) -> None:
    """Called after the user approves: AWAITING_APPROVAL was already moved to RUNNING by the API."""
    settings = settings or get_settings()
    db = SessionLocal()
    try:
        mission = db.get(Mission, mission_id)
        if mission is None or mission.status != S.RUNNING.value:
            return
        try:
            async with connect(settings.mcp_server_url, token, settings.agent_tool_timeout_seconds) as conn:
                add_event(db, mission, "mcp_connected", f"Connected to MCP server '{conn.server_name}' (protocol {conn.protocol_version})",
                          result={"protocol_version": conn.protocol_version, "tools": sorted(conn.tools)})
                missing = [s["tool"] for s in mission.plan["steps"] if s["tool"] not in conn.tools]
                if missing:
                    add_event(db, mission, "planning_failed", f"Tools no longer advertised: {missing}")
                    return _finish(db, mission, S.FAILED, f"Tools no longer available: {missing}")
                await _execute(db, mission, conn, settings)
        except MCPUnavailable as e:
            add_event(db, mission, "mcp_unavailable", str(e))
            _finish(db, mission, S.FAILED, str(e))
    except Exception as e:
        log.exception("mission %s crashed", mission_id)
        db.rollback()
        m = db.get(Mission, mission_id)
        if m and m.status not in {s.value for s in (S.COMPLETED, S.FAILED, S.PARTIALLY_COMPLETED, S.CANCELLED)}:
            m.status = S.FAILED.value
            m.error = f"Internal error: {type(e).__name__}"
            m.completed_at = utcnow()
            db.commit()
    finally:
        db.close()


async def _execute(db: Session, mission: Mission, conn: MCPConnection, settings: Settings) -> None:
    plan = mission.plan or {}
    outputs: dict[int, dict[str, Any]] = {}
    failed_step: dict | None = None
    failure: str | None = None
    write_succeeded = False
    checks: list[tuple[bool, str]] = []
    try:
        with anyio.fail_after(settings.agent_mission_timeout_seconds):
            for step in plan["steps"]:
                db.refresh(mission)
                if mission.status == S.CANCELLED.value:
                    add_event(db, mission, "cancelled", "Mission cancelled by user; remaining steps skipped")
                    return
                if step["role"] == "verify" and mission.status == S.RUNNING.value:
                    transition(mission, S.VERIFYING)
                    db.commit()
                try:
                    args = _resolve(step["args"], outputs)
                except PlanValidationError as e:
                    failed_step, failure = step, str(e)
                    add_event(db, mission, "tool_failed", f"Step {step['n']}: {e}", tool=step["tool"])
                    break
                props = (conn.tools[step["tool"]].get("input_schema") or {}).get("properties", {})
                if "mission_id" in props:
                    args["mission_id"] = mission.id
                if "idempotency_key" in props and step["tool"] in WRITE_TOOLS:
                    args.setdefault("idempotency_key", f"mission-{mission.id}-step-{step['n']}")
                add_event(db, mission, "tool_invoked", f"Step {step['n']}: calling {step['tool']} — {step['purpose']}", tool=step["tool"], result={"arguments": args})
                res = await _call_with_retry(conn, step, args, db, mission, settings)
                if not res.ok:
                    failed_step, failure = step, res.error
                    break
                outputs[step["n"]] = res.data or {}
                if step["tool"] in WRITE_TOOLS:
                    write_succeeded = True
                add_event(db, mission, "tool_succeeded", f"Step {step['n']}: {_describe(step['tool'], res.data or {})}", tool=step["tool"],
                          result=res.data if step["tool"] != "get_project_context" else _context_digest(res.data or {}))
                if step.get("check"):
                    try:
                        ok, detail = evaluate_check(step["check"], res.data or {}, outputs)
                    except PlanValidationError as e:
                        ok, detail = False, str(e)
                    if step["check"]["type"] == "read_only":
                        add_event(db, mission, "verification", "Read-only step: no state change to verify", verification=VerificationStatus.NOT_APPLICABLE.value)
                    else:
                        checks.append((ok, detail))
                        add_event(db, mission, "verification", f"Verification {'passed' if ok else 'FAILED'}: {detail}", tool=step["tool"],
                                  result=res.data if step["tool"] == "verify_report" else {"detail": detail},
                                  verification=VerificationStatus.PASSED.value if ok else VerificationStatus.FAILED.value)
    except TimeoutError:
        failure = f"timeout: mission exceeded {settings.agent_mission_timeout_seconds}s"
        add_event(db, mission, "tool_failed", failure)

    db.refresh(mission)
    if mission.status == S.CANCELLED.value:
        return
    if failure:
        status = S.PARTIALLY_COMPLETED if write_succeeded else S.FAILED
        where = f"step {failed_step['n']} ({failed_step['tool']})" if failed_step else "execution"
        return _finish(db, mission, status, f"{where} failed: {failure}", outputs)
    if any(not ok for ok, _ in checks):
        status = S.PARTIALLY_COMPLETED if write_succeeded else S.FAILED
        return _finish(db, mission, status, "Operation ran but verification failed: " + "; ".join(d for ok, d in checks if not ok), outputs, has_checks=True)
    if mission.status == S.RUNNING.value:
        transition(mission, S.VERIFYING)
    verified = all(ok for ok, _ in checks)  # True for read-only missions (no state changed)
    return _finish(db, mission, S.COMPLETED, None, outputs, verified=verified, has_checks=bool(checks))


def _summary(mission: Mission, outputs: dict[int, dict[str, Any]]) -> str:
    plan = mission.plan or {}
    first = outputs.get(1, {})
    mtype = plan.get("mission_type", "")
    if mtype.endswith("_report"):
        v = outputs.get(2, {})
        n_ok = sum(1 for c in v.get("checks", []) if c.get("passed"))
        return f"Report #{first.get('report_id')} '{first.get('title')}' saved and verified ({n_ok}/{len(v.get('checks', []))} checks passed)."
    tool = plan["steps"][0]["tool"] if plan.get("steps") else ""
    return _describe(tool, first) + (" and verified." if mtype in ("create_task", "update_task", "record_decision") else ".")


def _finish(db: Session, mission: Mission, status: S, error: str | None, outputs: dict[int, dict[str, Any]] | None = None,
            verified: bool = False, has_checks: bool = False) -> None:
    outputs = outputs or {}
    if status == S.COMPLETED:
        transition(mission, S.COMPLETED, verified=verified)
        mission.result_summary = _summary(mission, outputs)
    else:
        if mission.status in (S.RUNNING.value, S.VERIFYING.value, S.PLANNING.value, S.PENDING.value, S.AWAITING_APPROVAL.value):
            transition(mission, status)
        mission.error = error
        mission.result_summary = {
            S.FAILED: "Mission failed. Nothing was reported as done.",
            S.PARTIALLY_COMPLETED: "Some steps succeeded, but the mission is not complete.",
        }.get(status, status.value)
    if status == S.COMPLETED:
        label = VerificationStatus.PASSED.value if has_checks else VerificationStatus.NOT_APPLICABLE.value
    elif status == S.PARTIALLY_COMPLETED or (error or "").startswith("Operation ran but verification failed"):
        label = VerificationStatus.FAILED.value
    else:
        label = None
    add_event(db, mission, "mission_" + mission.status, mission.result_summary + (f" Reason: {error}" if error else ""), verification=label)
    # Preserve continuity: the outcome becomes episodic memory for future missions.
    memory_svc.create_memory(
        db, mission.project_id,
        content=f"Mission #{mission.id} ({mission.mission_type or 'unplanned'}) {mission.status.replace('_', ' ')}: {mission.result_summary}" + (f" Reason: {error}" if error else ""),
        memory_type=MemoryType.EPISODIC.value, source=f"mission:{mission.id}", tags=["mission", mission.status], mission_id=mission.id,
    )
    db.commit()
    add_event(db, mission, "outcome_recorded", "Outcome stored in project memory for future missions")
