from __future__ import annotations

from canon.core.models import DecisionStatus
from canon.errors import UsageError

_ALLOWED: dict[DecisionStatus, frozenset[DecisionStatus]] = {
    DecisionStatus.CANDIDATE: frozenset(
        {DecisionStatus.ACTIVE, DecisionStatus.REJECTED}
    ),
    DecisionStatus.ACTIVE: frozenset({DecisionStatus.SUPERSEDED}),
    DecisionStatus.REJECTED: frozenset(),
    DecisionStatus.SUPERSEDED: frozenset(),
}


def can_transition(current: DecisionStatus, target: DecisionStatus) -> bool:
    return target in _ALLOWED[current]


def require_transition(current: DecisionStatus, target: DecisionStatus) -> None:
    if can_transition(current, target):
        return
    raise UsageError(
        f"Cannot change a {current.value} decision to {target.value}.",
        "Active decisions are superseded by approving a replacement. "
        "Rejected and superseded records are kept for history and are never deleted.",
    )
