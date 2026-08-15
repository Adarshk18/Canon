from __future__ import annotations

import pytest

from canon.core.lifecycle import can_transition, require_transition
from canon.core.models import DecisionStatus
from canon.errors import UsageError


def test_allowed_transitions() -> None:
    assert can_transition(DecisionStatus.CANDIDATE, DecisionStatus.ACTIVE)
    assert can_transition(DecisionStatus.CANDIDATE, DecisionStatus.REJECTED)
    assert can_transition(DecisionStatus.ACTIVE, DecisionStatus.SUPERSEDED)
    assert not can_transition(DecisionStatus.REJECTED, DecisionStatus.ACTIVE)
    assert not can_transition(DecisionStatus.SUPERSEDED, DecisionStatus.ACTIVE)


def test_require_transition_rejects_illegal() -> None:
    with pytest.raises(UsageError):
        require_transition(DecisionStatus.REJECTED, DecisionStatus.ACTIVE)
