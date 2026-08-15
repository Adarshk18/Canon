from __future__ import annotations

import re
from dataclasses import dataclass, field

from canon.core.models import Confidence

DECISION_PATTERNS = (
    re.compile(r"(?i)\bswitch(?:ed|ing)? to\b"),
    re.compile(r"(?i)\bmigrat(?:e|ed|ing)\b"),
    re.compile(r"(?i)\breplace[sd]?\b.+\bwith\b"),
    re.compile(r"(?i)\badopt(?:ed|ing)?\b"),
    re.compile(r"(?i)\binstead of\b"),
    re.compile(r"(?i)\bdo not use\b"),
    re.compile(r"(?i)\bdon't use\b"),
    re.compile(r"(?i)\bnever use\b"),
    re.compile(r"(?i)\balways use\b"),
    re.compile(r"(?i)\bdecid(?:e|ed|ing) to\b"),
    re.compile(r"(?i)\bbreaking change\b"),
    re.compile(r"(?i)\bwe will use\b"),
    re.compile(r"(?i)\bstandardize on\b"),
    re.compile(r"(?i)\bchose to\b"),
    re.compile(r"(?i)\bprefer(?:ring)?\s+(to use|using)\b"),
    re.compile(r"(?i)\bdrop(?:ped|ping)? support\b"),
    re.compile(r"(?i)\brequire[sd]?\b.+\binstead\b"),
    # Product / policy decisions common in app repos (not stack migrations).
    re.compile(r"(?i)\bdrop(?:ped|ping)?\b.+\b(pages?|feature|flow|agent|analytics)\b"),
    re.compile(r"(?i)\brestore\b.+\b(landing|flow|cta|signup|login|pricing|agent)\b"),
    re.compile(r"(?i)\brename\b.+\bto\b"),
    re.compile(r"(?i)\bshow only\b"),
    re.compile(r"(?i)\bnever hang\b"),
    re.compile(r"(?i)\bstop (ai|invent|inventing|hallucinat)"),
    re.compile(r"(?i)\breject\b.+\bas (questions?|garbage|invalid)\b"),
    re.compile(r"(?i)\bthinking[- ](off|disabled)\b"),
    re.compile(r"(?i)\bskip second (llm|model|call)\b"),
    re.compile(r"(?i)\bhard timeouts?\b"),
    re.compile(r"(?i)\bsingle cta\b"),
    re.compile(r"(?i)\bhonest pricing\b"),
    re.compile(r"(?i)\buses?\b.+\b(fallback|v\d|flash|deepseek|openai|claude)\b"),
)

NOISE_PATTERNS = (
    re.compile(r"(?i)\btypo\b"),
    re.compile(r"(?i)\bformat(ting)?\b"),
    re.compile(r"(?i)\blint(ing)?\b"),
    re.compile(r"(?i)\bprettier\b"),
    re.compile(r"(?i)\beslint\b"),
    re.compile(r"(?i)\bwhitespace\b"),
    re.compile(r"(?i)\bchangelog\b"),
    re.compile(r"(?i)^chore:\s"),
    re.compile(r"(?i)^style:\s"),
    re.compile(r"(?i)^docs:\s"),
    re.compile(r"(?i)^test(s)?:\s"),
    re.compile(r"(?i)\bbump\b.+\bfrom\b"),
    re.compile(r"(?i)\blockfile\b"),
    re.compile(r"(?i)\bpackage-lock\b"),
    re.compile(r"(?i)\byarn\.lock\b"),
    re.compile(r"(?i)\bpnpm-lock\b"),
    re.compile(r"(?i)\brename[sd]?\s+(this\s+)?(file|variable|function|class|import|symbol)\b"),
    re.compile(r"(?i)\bwip\b"),
    re.compile(r"(?i)^merge (pull request|branch)\b"),
    re.compile(r"(?i)^(fix|feat)\(ui\):"),
    re.compile(r"(?i)\bbutton label\b"),
    re.compile(r"(?i)\bricher popup copy\b"),
    re.compile(r"(?i)\buncramp\b"),
)

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "database": (
        "postgres",
        "postgresql",
        "mysql",
        "mongodb",
        "sqlite",
        "redis",
        "dynamodb",
        "prisma",
        "sqlalchemy",
        "drizzle",
        "alembic",
    ),
    "auth": (
        "oauth",
        "oidc",
        "jwt",
        "authentication",
        "authorization",
        "sso",
        "saml",
        "password",
        "session",
    ),
    "architecture": (
        "architecture",
        "monolith",
        "microservice",
        "hexagonal",
        "modular",
        "event-driven",
        "cqrs",
    ),
    "api": ("graphql", "rest", "grpc", "openapi", "endpoint", "api design"),
    "infrastructure": (
        "kubernetes",
        "docker",
        "terraform",
        "deploy",
        "ci",
        "cd",
        "github actions",
        "helm",
    ),
    "security": ("security", "encrypt", "tls", "https", "secret", "csp", "cors"),
    "performance": ("performance", "cache", "latency", "throughput"),
    "compatibility": ("compat", "breaking", "semver", "deprecat"),
    "frontend": ("react", "vue", "svelte", "next.js", "css"),
    "tooling": ("typescript", "eslint config", "bundler", "webpack", "vite"),
    "product": (
        "landing",
        "pricing",
        "onboarding",
        "debrief",
        "analytics",
        "quota",
        "cta",
        "retention",
    ),
    "ai": (
        "deepseek",
        "openai",
        "anthropic",
        "llm",
        "thinking",
        "v4-flash",
        "model fallback",
    ),
}

PATH_HINTS: dict[str, tuple[str, ...]] = {
    "database": ("alembic", "prisma", "migrations", "schema.sql", "models/"),
    "auth": ("auth/", "oauth", "security/"),
    "infrastructure": (
        "dockerfile",
        "docker-compose",
        "terraform",
        ".github/workflows",
        "k8s/",
        "helm/",
    ),
    "security": ("security/", ".well-known"),
}

NOISE_PATHS = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "cargo.lock",
    "go.sum",
    ".svg",
    ".map",
    "generated/",
    "__snapshots__/",
)


@dataclass(slots=True)
class Score:
    value: int
    reasons: list[str] = field(default_factory=list)
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    noise: bool = False

    @property
    def confidence(self) -> Confidence:
        if self.value >= 9:
            return Confidence.HIGH
        if self.value >= 6:
            return Confidence.MEDIUM
        return Confidence.LOW


def _haystack(title: str, body: str, files: tuple[str, ...]) -> str:
    return f"{title}\n{body}\n" + "\n".join(files)


def score_change(
    *,
    title: str,
    body: str,
    files: tuple[str, ...],
    is_pr: bool,
) -> Score:
    result = Score(value=0)
    text = _haystack(title, body, files)
    lowered_files = tuple(path.lower() for path in files)

    if any(pattern.search(title) or pattern.search(body) for pattern in NOISE_PATTERNS):
        result.value -= 5
        result.noise = True
        result.reasons.append("Looks like a mechanical or formatting change")

    if files and all(
        any(marker in path for marker in NOISE_PATHS) or path.endswith((".md", ".txt"))
        for path in lowered_files
    ):
        result.value -= 3
        result.noise = True
        result.reasons.append("Touches only docs, lockfiles, or generated paths")

    if files and all(
        "/test" in path or path.startswith("test") or path.endswith("_test.py")
        or path.endswith(".test.ts")
        or path.endswith("_test.go")
        for path in lowered_files
    ):
        result.value -= 3
        result.reasons.append("Test-only change")

    decided = any(pattern.search(title) or pattern.search(body) for pattern in DECISION_PATTERNS)
    if decided:
        result.value += 4
        result.reasons.append("Explicit decision language")

    if re.search(r"(?i)\bbecause\b|\bso that\b|\bin order to\b|\brationale\b", body):
        result.value += 2
        result.reasons.append("Includes rationale")

    if re.search(r"(?i)breaking change|feat!", title + "\n" + body):
        result.value += 2
        result.reasons.append("Marked as breaking")

    if is_pr:
        result.value += 2
        result.reasons.append("Sourced from a merged pull request")

    best_category: str | None = None
    best_hits = 0
    lowered = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for word in keywords if word in lowered)
        path_hits = sum(
            1 for hint in PATH_HINTS.get(category, ()) if any(hint in path for path in lowered_files)
        )
        total = hits + path_hits
        if total > best_hits:
            best_hits = total
            best_category = category
    if best_category and best_hits:
        result.category = best_category
        result.tags.append(best_category)
        bonus = min(3, best_hits)
        if decided and bonus < 2:
            bonus = 2
        result.value += bonus
        result.reasons.append(f"Matches {best_category} signals")

    if result.value < 0:
        result.value = 0
    return result
