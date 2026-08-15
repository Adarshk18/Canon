from __future__ import annotations

from collections.abc import Sequence

from canon.core.models import Decision
from canon.core.timeutil import parse_iso


def _file_hints(files: Sequence[str]) -> set[str]:
    hints: set[str] = set()
    mapping = {
        "database": ("db", "sql", "prisma", "alembic", "migration", "model"),
        "auth": ("auth", "oauth", "session", "login"),
        "infrastructure": ("docker", "terraform", "k8s", "deploy", "workflow", "helm"),
        "security": ("security", "crypto", "tls"),
        "api": ("api", "graphql", "openapi", "route"),
        "frontend": ("tsx", "vue", "css", "component"),
        "tooling": ("eslint", "webpack", "vite", "tsconfig"),
    }
    joined = " ".join(files).lower()
    for category, needles in mapping.items():
        if any(needle in joined for needle in needles):
            hints.add(category)
    return hints


def rank_decisions(
    decisions: Sequence[Decision],
    *,
    changed_files: Sequence[str],
    query: str | None = None,
) -> list[Decision]:
    hints = _file_hints(changed_files)
    query_text = (query or "").lower()

    def key(item: Decision) -> tuple[int, int, str]:
        score = 1
        if item.category and item.category in hints:
            score += 4
        if item.tags and any(tag in hints for tag in item.tags):
            score += 2
        if query_text:
            blob = f"{item.title} {item.body} {item.category or ''} {' '.join(item.tags)}".lower()
            if query_text in blob:
                score += 3
        confirmed = parse_iso(item.confirmed_at)
        recency = int(confirmed.timestamp()) if confirmed else 0
        return (score, recency, item.title)

    return sorted(decisions, key=key, reverse=True)
