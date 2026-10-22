"""Mission state machine. All status changes go through `transition`."""
from app.models import Mission, MissionStatus as S, utcnow

ALLOWED: dict[S, set[S]] = {
    S.PENDING: {S.PLANNING, S.FAILED, S.CANCELLED},
    S.PLANNING: {S.AWAITING_APPROVAL, S.RUNNING, S.FAILED, S.CANCELLED},
    S.AWAITING_APPROVAL: {S.RUNNING, S.CANCELLED, S.FAILED},
    S.RUNNING: {S.VERIFYING, S.FAILED, S.PARTIALLY_COMPLETED, S.CANCELLED},
    S.VERIFYING: {S.COMPLETED, S.FAILED, S.PARTIALLY_COMPLETED},
    S.COMPLETED: set(),
    S.FAILED: set(),
    S.PARTIALLY_COMPLETED: set(),
    S.CANCELLED: set(),
}


class InvalidTransition(Exception):
    pass


def transition(mission: Mission, new: S, *, verified: bool = False) -> None:
    cur = S(mission.status)
    if new not in ALLOWED[cur]:
        raise InvalidTransition(f"Mission #{mission.id}: {cur.value} -> {new.value} is not allowed.")
    if new == S.COMPLETED and not verified:
        # Invariant: a mission can only be completed with verification evidence.
        raise InvalidTransition(f"Mission #{mission.id} cannot be completed without passing verification.")
    mission.status = new.value
    if new == S.RUNNING and mission.started_at is None:
        mission.started_at = utcnow()
    if new in (S.COMPLETED, S.FAILED, S.PARTIALLY_COMPLETED, S.CANCELLED):
        mission.completed_at = utcnow()
