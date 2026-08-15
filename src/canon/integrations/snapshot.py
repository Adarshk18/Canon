from __future__ import annotations

from pathlib import Path

from canon.config.paths import ProjectPaths
from canon.config.settings import Settings
from canon.core.models import Decision, DecisionStatus
from canon.db.store import Store
from canon.gitutil.repo import GitRepo
from canon.integrations.budget import apply_budget
from canon.integrations.relevance import rank_decisions
from canon.integrations.render import render_decision_block, render_injection


def select_for_injection(
    store: Store,
    repo: GitRepo,
    settings: Settings,
    *,
    query: str | None = None,
) -> tuple[list[Decision], dict[str, int], str]:
    active = store.list(statuses=[DecisionStatus.ACTIVE])
    ranked = rank_decisions(active, changed_files=repo.changed_files(), query=query)
    blocks = [render_decision_block(item) for item in ranked]
    selected, selected_blocks, stats = apply_budget(ranked, blocks, settings.injection)
    text = render_injection(selected)
    return selected, stats, text


def refresh_injection_files(
    paths: ProjectPaths,
    store: Store,
    repo: GitRepo,
    settings: Settings,
) -> Path:
    _selected, _stats, text = select_for_injection(store, repo, settings)
    paths.canon_dir.mkdir(parents=True, exist_ok=True)
    paths.injection_file.write_text(text, encoding="utf-8")
    return paths.injection_file
