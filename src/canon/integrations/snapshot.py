from __future__ import annotations

import json
from pathlib import Path

from canon.config.paths import ProjectPaths
from canon.config.settings import Settings
from canon.core.effective import visible_at_head
from canon.core.models import Decision, DecisionStatus
from canon.db.store import Store
from canon.gitutil.repo import GitRepo
from canon.integrations.budget import apply_budget
from canon.integrations.relevance import rank_decisions
from canon.integrations.render import render_decision_block, render_injection
from canon.integrations.wire import sync_all


def select_for_injection(
    store: Store,
    repo: GitRepo,
    settings: Settings,
    *,
    query: str | None = None,
) -> tuple[list[Decision], dict[str, int], str]:
    active = store.list(statuses=[DecisionStatus.ACTIVE])
    current = [item for item in active if visible_at_head(repo, item)]
    ranked = rank_decisions(current, changed_files=repo.changed_files(), query=query)
    blocks = [render_decision_block(item) for item in ranked]
    selected, selected_blocks, stats = apply_budget(ranked, blocks, settings.injection)
    stats["available"] = len(active)
    stats["current"] = len(current)
    stats["skipped_not_on_head"] = len(active) - len(current)
    text = render_injection(selected)
    return selected, stats, text


def _team_snapshot(store: Store, settings: Settings) -> str:
    """Active decisions for the repo, not filtered by this checkout's HEAD."""
    active = store.list(statuses=[DecisionStatus.ACTIVE])
    ranked = rank_decisions(active, changed_files=[], query=None)
    blocks = [render_decision_block(item) for item in ranked]
    selected, _selected_blocks, _stats = apply_budget(ranked, blocks, settings.injection)
    return render_injection(selected)


def write_team_export(store: Store, path: Path) -> Path:
    payload = store.export_payload()
    payload["decisions"] = [
        item
        for item in payload["decisions"]
        if item.get("status") != DecisionStatus.CANDIDATE.value
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def refresh_injection_files(
    paths: ProjectPaths,
    store: Store,
    repo: GitRepo,
    settings: Settings,
) -> Path:
    _selected, _stats, local_text = select_for_injection(store, repo, settings)
    team_text = _team_snapshot(store, settings)
    paths.canon_dir.mkdir(parents=True, exist_ok=True)
    paths.injection_file.write_text(local_text, encoding="utf-8")
    paths.canon_md_file.write_text(team_text, encoding="utf-8")
    write_team_export(store, paths.decisions_file)
    sync_all(paths.repo_root, settings.integrations, team_text)
    return paths.injection_file
