from __future__ import annotations

from collections.abc import Sequence

from canon.config.settings import InjectionSettings
from canon.core.models import Decision


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def apply_budget(
    decisions: Sequence[Decision],
    rendered_blocks: Sequence[str],
    settings: InjectionSettings,
) -> tuple[list[Decision], list[str], dict[str, int]]:
    kept_decisions: list[Decision] = []
    kept_blocks: list[str] = []
    chars = 0
    tokens = 0
    for decision, block in zip(decisions, rendered_blocks, strict=True):
        if len(kept_decisions) >= settings.max_decisions:
            break
        block_chars = len(block)
        block_tokens = estimate_tokens(block)
        if chars + block_chars > settings.max_chars:
            break
        if tokens + block_tokens > settings.max_tokens:
            break
        kept_decisions.append(decision)
        kept_blocks.append(block)
        chars += block_chars
        tokens += block_tokens
    stats = {
        "selected": len(kept_decisions),
        "available": len(decisions),
        "chars": chars,
        "tokens": tokens,
        "max_decisions": settings.max_decisions,
        "max_chars": settings.max_chars,
        "max_tokens": settings.max_tokens,
    }
    return kept_decisions, kept_blocks, stats
