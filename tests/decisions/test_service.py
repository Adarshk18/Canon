from __future__ import annotations

from pathlib import Path

from canon.core.models import DecisionStatus, SourceType
from canon.db.store import Store
from canon.decisions.service import DecisionService
from canon.telemetry.provider import NoOpTelemetry


def test_approve_and_supersede(tmp_path: Path) -> None:
    store = Store(tmp_path / "canon.db")
    service = DecisionService(store, NoOpTelemetry())
    first = service.create_candidate(
        title="Use Redis for caching",
        body="In-memory cache.",
        source_type=SourceType.COMMIT,
        source_commit="aaa111",
        category="performance",
        tags=["cache"],
    )
    assert first is not None
    approved, superseded = service.approve(first.id or 0, confirmed_by="dev@example.com")
    assert approved.status is DecisionStatus.ACTIVE
    assert approved.effective_from == "aaa111"
    assert superseded is None

    second = service.create_candidate(
        title="Use Memcached for caching",
        body="Replace Redis.",
        source_type=SourceType.COMMIT,
        source_commit="bbb222",
        category="performance",
        tags=["cache"],
    )
    assert second is not None
    replacement, old = service.approve(second.id or 0, confirmed_by="dev@example.com")
    assert replacement.status is DecisionStatus.ACTIVE
    assert old is not None
    assert old.status is DecisionStatus.SUPERSEDED
    assert old.superseded_by_id == replacement.id
    history = service.list_decisions(statuses=[DecisionStatus.SUPERSEDED])
    assert history[0].id == first.id
    store.close()


def test_reject_keeps_record(tmp_path: Path) -> None:
    store = Store(tmp_path / "canon.db")
    service = DecisionService(store, NoOpTelemetry())
    item = service.create_candidate(
        title="Use MongoDB",
        body="Document store.",
        source_type=SourceType.COMMIT,
        source_commit="ccc333",
    )
    assert item is not None
    rejected = service.reject(item.id or 0, reason="not a real decision")
    assert rejected.status is DecisionStatus.REJECTED
    assert service.get(item.id or 0).id == item.id
    store.close()


def test_add_manual_approve(tmp_path: Path) -> None:
    store = Store(tmp_path / "canon.db")
    service = DecisionService(store, NoOpTelemetry())
    decision, superseded = service.add_manual(
        title="Keep miner deterministic, no LLM",
        body="Explainable candidates only.",
        confirmed_by="dev@example.com",
        tags=["mining"],
        category="product",
        at_commit="ddd444",
        approve=True,
    )
    assert superseded is None
    assert decision.status is DecisionStatus.ACTIVE
    assert decision.source_type is SourceType.MANUAL
    assert decision.authority == "human"
    store.close()


def test_duplicate_fingerprint_is_ignored(tmp_path: Path) -> None:
    store = Store(tmp_path / "canon.db")
    service = DecisionService(store, NoOpTelemetry())
    first = service.create_candidate(
        title="Use PostgreSQL",
        body="Relational.",
        source_type=SourceType.PR,
        source_pr="184",
    )
    second = service.create_candidate(
        title="Use PostgreSQL again",
        body="Still relational.",
        source_type=SourceType.PR,
        source_pr="184",
    )
    assert first is not None
    assert second is None
    store.close()
