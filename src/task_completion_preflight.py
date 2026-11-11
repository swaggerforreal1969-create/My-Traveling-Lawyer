"""Local-only task completion preflight; no reservation or write authority.

Shows whether a specific authorized editor can attempt one version-checked task
completion. This check is advisory: the eventual atomic completion reauthorizes,
and a concurrent writer may change state after this function returns.
"""
from dataclasses import dataclass
from .secure_engine import Invalid
from .task_reconciliation import reconcile_task


@dataclass(frozen=True)
class CompletionPreflight:
    status: str
    observed_version: int
    can_attempt_completion: bool
    legal_deadlines_verified: bool = False
    court_filing_approved: bool = False
    official_law_verified: bool = False


def prepare_completion(core, token, matter_id, task_id, expected_version):
    """Authorize the editor and reconcile audited task state under one local lock.

    No matter title, task text, due date, legal assertion, or credential is
    returned. A preflight never constitutes one-use authorization or a lock.
    """
    with core.authorized_transaction():
        if (not isinstance(matter_id, str) or not 1 <= len(matter_id) <= 64
                or not isinstance(task_id, str) or not 1 <= len(task_id) <= 64
                or type(expected_version) is not int or expected_version < 1):
            raise Invalid('Invalid completion preflight')
        actor = core._identity(token)
        core._role(actor, matter_id, ('owner', 'editor'))
        state = reconcile_task(core, token, matter_id, task_id, expected_version)
        if state.status == 'still_open':
            status = 'ready_to_attempt'
        elif state.status == 'observed_completed':
            status = 'already_completed'
        else:
            status = 'unresolved'
        return CompletionPreflight(
            status=status,
            observed_version=state.observed_version,
            can_attempt_completion=(status == 'ready_to_attempt'),
        )
