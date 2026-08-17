from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DecisionStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class SourceType(StrEnum):
    PR = "pr"
    COMMIT = "commit"
    MANUAL = "manual"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def _as_status(value: str | DecisionStatus) -> DecisionStatus:
    return value if isinstance(value, DecisionStatus) else DecisionStatus(value)


def _as_source(value: str | SourceType | None) -> SourceType | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, SourceType) else SourceType(value)


def _as_confidence(value: str | Confidence | None) -> Confidence | None:
    if value is None or value == "":
        return None
    return value if isinstance(value, Confidence) else Confidence(value)


@dataclass(slots=True)
class Decision:
    id: int | None
    title: str
    body: str
    status: DecisionStatus
    created_at: str
    updated_at: str
    confirmed_at: str | None = None
    confirmed_by: str | None = None
    source_type: SourceType | None = None
    source_repository: str | None = None
    source_pr: str | None = None
    source_commit: str | None = None
    source_url: str | None = None
    source_date: str | None = None
    effective_from: str | None = None
    effective_until: str | None = None
    supersedes_id: int | None = None
    superseded_by_id: int | None = None
    superseded_at: str | None = None
    rejected_at: str | None = None
    rejection_reason: str | None = None
    confidence: Confidence | None = None
    authority: str | None = None
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    evidence: str | None = None
    fingerprint: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status is DecisionStatus.ACTIVE

    def provenance_lines(self) -> list[str]:
        lines = ["Source:"]
        lines.append(f"Repository: {self.source_repository or 'unavailable'}")
        if self.source_type is SourceType.PR:
            lines.append(f"PR: {self.source_pr or 'unavailable'}")
        if self.source_commit:
            short = self.source_commit[:12]
            lines.append(f"Commit: {short}")
        if self.source_url:
            lines.append(f"URL: {self.source_url}")
        lines.append(f"Source date: {self.source_date or 'unavailable'}")
        if self.confirmed_at:
            lines.append(f"Confirmed: {self.confirmed_at}")
        if self.confirmed_by:
            lines.append(f"Confirmed by: {self.confirmed_by}")
        if self.effective_from:
            lines.append(f"Effective from: {self.effective_from[:12]}")
        if self.effective_until:
            lines.append(f"Effective until: {self.effective_until[:12]}")
        return lines

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "status": str(self.status),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "confirmed_at": self.confirmed_at,
            "confirmed_by": self.confirmed_by,
            "source_type": str(self.source_type) if self.source_type else None,
            "source_repository": self.source_repository,
            "source_pr": self.source_pr,
            "source_commit": self.source_commit,
            "source_url": self.source_url,
            "source_date": self.source_date,
            "effective_from": self.effective_from,
            "effective_until": self.effective_until,
            "supersedes_id": self.supersedes_id,
            "superseded_by_id": self.superseded_by_id,
            "superseded_at": self.superseded_at,
            "rejected_at": self.rejected_at,
            "rejection_reason": self.rejection_reason,
            "confidence": str(self.confidence) if self.confidence else None,
            "authority": self.authority,
            "tags": list(self.tags),
            "category": self.category,
            "evidence": self.evidence,
            "fingerprint": self.fingerprint,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Decision:
        tags = row.get("tags") or []
        if isinstance(tags, str):
            import json

            tags = json.loads(tags) if tags else []
        extra = row.get("extra") or {}
        if isinstance(extra, str):
            import json

            extra = json.loads(extra) if extra else {}
        return cls(
            id=row.get("id"),
            title=row["title"],
            body=row["body"],
            status=_as_status(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            confirmed_at=row.get("confirmed_at"),
            confirmed_by=row.get("confirmed_by"),
            source_type=_as_source(row.get("source_type")),
            source_repository=row.get("source_repository"),
            source_pr=row.get("source_pr"),
            source_commit=row.get("source_commit"),
            source_url=row.get("source_url"),
            source_date=row.get("source_date"),
            effective_from=row.get("effective_from"),
            effective_until=row.get("effective_until"),
            supersedes_id=row.get("supersedes_id"),
            superseded_by_id=row.get("superseded_by_id"),
            superseded_at=row.get("superseded_at"),
            rejected_at=row.get("rejected_at"),
            rejection_reason=row.get("rejection_reason"),
            confidence=_as_confidence(row.get("confidence")),
            authority=row.get("authority"),
            tags=list(tags),
            category=row.get("category"),
            evidence=row.get("evidence"),
            fingerprint=row.get("fingerprint"),
            extra=dict(extra),
        )
