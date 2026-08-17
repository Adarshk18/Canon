"""Whether a stored decision is current at HEAD.

This is git ancestry, not agent memory. Claude auto-memory and Cursor
memories are model-written notes. Canon only serves a decision if the
commit that made it law is already in this checkout, and a revert or
supersede commit has not landed yet.
"""

from __future__ import annotations

from canon.core.models import Decision
from canon.gitutil.repo import GitRepo


def visible_at_head(repo: GitRepo, decision: Decision) -> bool:
    """True if this checkout is inside the decision's effective commit range."""
    head = repo.head_sha()
    if head is None:
        return False
    start = decision.effective_from or decision.source_commit
    if start:
        if not repo.commit_exists(start):
            return False
        if not repo.is_ancestor(start, head):
            return False
        revert = repo.find_revert_commit(start)
        if revert and repo.is_ancestor(revert, head):
            return False
    end = decision.effective_until
    if end:
        if repo.commit_exists(end) and repo.is_ancestor(end, head):
            return False
    return True
