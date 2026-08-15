from __future__ import annotations

from dataclasses import dataclass, field

from canon.config.settings import Settings
from canon.core.models import SourceType
from canon.decisions.service import DecisionService
from canon.errors import GitHubError
from canon.githubutil.client import GitHubClient
from canon.gitutil.repo import GitRepo
from canon.mining.extract import extract_body, extract_title
from canon.mining.scoring import score_change


@dataclass(slots=True)
class MineResult:
    created: int = 0
    skipped: int = 0
    inspected: int = 0
    source: str = "git"
    warning: str | None = None
    created_ids: list[int] = field(default_factory=list)


def mine_candidates(
    *,
    repo: GitRepo,
    service: DecisionService,
    settings: Settings,
) -> MineResult:
    result = MineResult()
    github = GitHubClient(repo)
    prs = []
    try:
        if github.status().authenticated:
            prs = github.recent_merged_prs(settings.mining.lookback_prs)
            result.source = "github"
    except GitHubError as exc:
        result.warning = exc.render()
        result.source = "git"

    if prs:
        for pr in prs:
            result.inspected += 1
            score = score_change(
                title=pr.title,
                body=pr.body,
                files=pr.files,
                is_pr=True,
            )
            if score.value < settings.mining.min_score or score.noise:
                result.skipped += 1
                continue
            evidence = f"PR #{pr.number}"
            created = service.create_candidate(
                title=extract_title(pr.title, score.category),
                body=extract_body(pr.body, evidence),
                source_type=SourceType.PR,
                source_repository=pr.repository,
                source_pr=str(pr.number),
                source_commit=pr.merge_commit,
                source_url=pr.url or None,
                source_date=pr.merged_at,
                confidence=score.confidence,
                tags=score.tags,
                category=score.category,
                evidence=evidence,
                extra={"score": score.value, "reasons": score.reasons},
            )
            if created and created.id is not None:
                result.created += 1
                result.created_ids.append(created.id)
            else:
                result.skipped += 1
        return result

    commits = repo.recent_commits(settings.mining.lookback_commits)
    if result.source == "github":
        result.source = "git"
        result.warning = (
            "GitHub returned no merged pull requests. "
            "Canon fell back to local Git history."
        )
    elif result.warning is None:
        result.warning = (
            "GitHub is unavailable. Canon is using local Git history. "
            "Install GitHub CLI and run `gh auth login` for PR provenance."
        )
        result.source = "git"

    for commit in commits:
        result.inspected += 1
        if commit.is_merge and not commit.subject.lower().startswith(
            ("switch", "migrate", "replace", "adopt", "use ", "breaking")
        ):
            result.skipped += 1
            continue
        score = score_change(
            title=commit.subject,
            body=commit.body,
            files=commit.files,
            is_pr=False,
        )
        if score.value < settings.mining.min_score or score.noise:
            result.skipped += 1
            continue
        short = commit.sha[:12]
        evidence = f"Commit {short}"
        created = service.create_candidate(
            title=extract_title(commit.subject, score.category),
            body=extract_body(commit.body, evidence),
            source_type=SourceType.COMMIT,
            source_repository=repo.github_slug() or str(repo.root),
            source_commit=commit.sha,
            source_date=commit.authored_at,
            confidence=score.confidence,
            tags=score.tags,
            category=score.category,
            evidence=evidence,
            extra={"score": score.value, "reasons": score.reasons},
        )
        if created and created.id is not None:
            result.created += 1
            result.created_ids.append(created.id)
        else:
            result.skipped += 1
    return result
