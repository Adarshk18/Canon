from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from canon.core.lifecycle import require_transition
from canon.core.models import Confidence, Decision, DecisionStatus, SourceType
from canon.core.timeutil import utcnow_iso
from canon.db.store import Store
from canon.decisions.validation import (
    fingerprint,
    normalize_body,
    normalize_tags,
    normalize_title,
)
from canon.errors import UsageError
from canon.telemetry.provider import TelemetryProvider


class DecisionService:
    def __init__(self, store: Store, telemetry: TelemetryProvider) -> None:
        self.store = store
        self.telemetry = telemetry

    def get(self, decision_id: int) -> Decision:
        return self.store.get(decision_id)

    def list_decisions(
        self,
        *,
        statuses: Sequence[DecisionStatus] | None = None,
        tag: str | None = None,
        category: str | None = None,
    ) -> list[Decision]:
        return self.store.list(statuses=statuses, tag=tag, category=category)

    def create_candidate(
        self,
        *,
        title: str,
        body: str,
        source_type: SourceType | None = None,
        source_repository: str | None = None,
        source_pr: str | None = None,
        source_commit: str | None = None,
        source_url: str | None = None,
        source_date: str | None = None,
        confidence: Confidence | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
        evidence: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> Decision | None:
        title = normalize_title(title)
        body = normalize_body(body)
        tags = normalize_tags(tags or [])
        fp = fingerprint(
            source_type=str(source_type) if source_type else None,
            source_pr=source_pr,
            source_commit=source_commit,
            title=title,
        )
        if self.store.find_by_fingerprint(fp) is not None:
            return None
        now = utcnow_iso()
        decision = Decision(
            id=None,
            title=title,
            body=body,
            status=DecisionStatus.CANDIDATE,
            created_at=now,
            updated_at=now,
            source_type=source_type,
            source_repository=source_repository,
            source_pr=source_pr,
            source_commit=source_commit,
            source_url=source_url,
            source_date=source_date,
            confidence=confidence,
            authority="suggested",
            tags=tags,
            category=category,
            evidence=evidence,
            fingerprint=fp,
            extra=extra or {},
            effective_from=source_commit,
        )
        created = self.store.insert(decision)
        self.store.record_event("suggestion_created", {"id": created.id})
        self.telemetry.record("suggestions_generated", {"count": 1})
        return created

    def approve(
        self,
        decision_id: int,
        *,
        confirmed_by: str,
        supersedes_id: int | None = None,
        at_commit: str | None = None,
    ) -> tuple[Decision, Decision | None]:
        decision = self.store.get(decision_id)
        require_transition(decision.status, DecisionStatus.ACTIVE)
        now = utcnow_iso()
        superseded: Decision | None = None
        target = supersedes_id
        if target is None:
            target = self.suggest_supersession(decision)
        if target is not None:
            superseded = self._supersede(
                target,
                replacement_id=decision_id,
                when=now,
                until_commit=at_commit,
            )
            decision.supersedes_id = target
        decision.status = DecisionStatus.ACTIVE
        decision.confirmed_at = now
        decision.confirmed_by = confirmed_by
        decision.authority = "human"
        if not decision.effective_from:
            decision.effective_from = decision.source_commit or at_commit
        updated = self.store.update(decision)
        self.store.record_event(
            "suggestion_approved",
            {"id": updated.id, "supersedes": target},
        )
        self.telemetry.record("suggestion_approved", {"id": updated.id})
        return updated, superseded

    def add_manual(
        self,
        *,
        title: str,
        body: str,
        confirmed_by: str,
        tags: list[str] | None = None,
        category: str | None = None,
        at_commit: str | None = None,
        approve: bool = False,
    ) -> tuple[Decision, Decision | None]:
        created = self.create_candidate(
            title=title,
            body=body,
            source_type=SourceType.MANUAL,
            source_commit=at_commit,
            source_date=utcnow_iso(),
            confidence=Confidence.HIGH,
            tags=tags,
            category=category,
            evidence="manual",
            extra={"origin": "canon add"},
        )
        if created is None:
            existing = self.store.find_by_fingerprint(
                fingerprint(
                    source_type="manual",
                    source_pr=None,
                    source_commit=None,
                    title=normalize_title(title),
                )
            )
            if existing is None:
                raise UsageError("Could not record that decision.")
            if approve and existing.status is DecisionStatus.CANDIDATE:
                return self.approve(
                    existing.id or 0,
                    confirmed_by=confirmed_by,
                    at_commit=at_commit,
                )
            raise UsageError(
                f"A decision with this title already exists "
                f"(#{existing.id}, {existing.status.value})."
            )
        if approve:
            return self.approve(
                created.id or 0,
                confirmed_by=confirmed_by,
                at_commit=at_commit,
            )
        return created, None

    def reject(self, decision_id: int, *, reason: str | None = None) -> Decision:
        decision = self.store.get(decision_id)
        require_transition(decision.status, DecisionStatus.REJECTED)
        decision.status = DecisionStatus.REJECTED
        decision.rejected_at = utcnow_iso()
        decision.rejection_reason = (reason or "").strip() or None
        updated = self.store.update(decision)
        self.store.record_event("suggestion_rejected", {"id": updated.id})
        self.telemetry.record("suggestion_rejected", {"id": updated.id})
        return updated

    def suggest_supersession(self, incoming: Decision) -> int | None:
        if incoming.category is None:
            return None
        actives = self.list_decisions(
            statuses=[DecisionStatus.ACTIVE], category=incoming.category
        )
        incoming_tags = {tag.lower() for tag in incoming.tags}
        for existing in actives:
            existing_tags = {tag.lower() for tag in existing.tags}
            if incoming_tags and existing_tags and incoming_tags & existing_tags:
                return existing.id
        return actives[-1].id if len(actives) == 1 else None

    def _supersede(
        self,
        old_id: int,
        *,
        replacement_id: int,
        when: str,
        until_commit: str | None = None,
    ) -> Decision:
        old = self.store.get(old_id)
        if old.status is DecisionStatus.SUPERSEDED:
            return old
        if old.status is not DecisionStatus.ACTIVE:
            raise UsageError(
                f"Decision #{old_id} is {old.status.value} and cannot be superseded.",
                "Only active decisions can be superseded.",
            )
        old.status = DecisionStatus.SUPERSEDED
        old.superseded_by_id = replacement_id
        old.superseded_at = when
        if until_commit and not old.effective_until:
            old.effective_until = until_commit
        return self.store.update(old)

    def import_decisions(self, payload: dict[str, object], *, overwrite: bool = False) -> int:
        if payload.get("format") != "canon-export":
            raise UsageError("This file is not a Canon export.")
        raw_items = payload.get("decisions")
        if not isinstance(raw_items, list):
            raise UsageError("Export is missing a decisions list.")
        count = 0
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise UsageError("Export contains a malformed decision.")
            try:
                decision = Decision.from_row(raw)
            except (KeyError, ValueError) as exc:
                raise UsageError("Export contains a malformed decision.") from exc
            decision.title = normalize_title(decision.title)
            decision.body = normalize_body(decision.body)
            decision.tags = normalize_tags(decision.tags)
            existing = (
                self.store.find_by_fingerprint(decision.fingerprint)
                if decision.fingerprint
                else None
            )
            if existing is not None:
                if not overwrite:
                    continue
                decision.id = existing.id
                self.store.update(decision)
            else:
                decision.id = None
                self.store.insert(decision)
            count += 1
        return count

    def write_export(self, path: Path) -> Path:
        import json

        payload = self.store.export_payload()
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path
