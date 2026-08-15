from __future__ import annotations

from canon.config.settings import InjectionSettings
from canon.core.models import Decision, DecisionStatus
from canon.core.timeutil import utcnow_iso
from canon.integrations.budget import apply_budget, estimate_tokens
from canon.integrations.relevance import rank_decisions
from canon.integrations.render import render_decision_block, render_injection


def _decision(title: str, category: str, ident: int) -> Decision:
    now = utcnow_iso()
    return Decision(
        id=ident,
        title=title,
        body="Confirmed project decision.",
        status=DecisionStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        confirmed_at=now,
        category=category,
        tags=[category],
        evidence=f"PR #{ident}",
    )


def test_budget_caps_decisions() -> None:
    items = [_decision(f"Use thing {i}", "database", i) for i in range(1, 20)]
    blocks = [render_decision_block(item) for item in items]
    settings = InjectionSettings(max_decisions=3, max_chars=4000, max_tokens=1000)
    selected, _blocks, stats = apply_budget(items, blocks, settings)
    assert len(selected) == 3
    assert stats["selected"] == 3


def test_token_estimate_and_render_empty() -> None:
    assert estimate_tokens("abcd") == 1
    text = render_injection([])
    assert "no confirmed decision" in text.lower()


def test_relevance_prefers_matching_category() -> None:
    db = _decision("Use PostgreSQL", "database", 1)
    auth = _decision("Use OAuth 2.1", "auth", 2)
    ranked = rank_decisions([db, auth], changed_files=["src/auth/oauth.py"])
    assert ranked[0].category == "auth"
