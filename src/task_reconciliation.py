"""Read-only, locally verified task-state reconciliation after an uncertain response.

This does not prove which caller completed a task, nor provide an independent
rollback-resistant audit checkpoint. It never issues a task completion command.
"""
from dataclasses import dataclass
from .secure_engine import Denied, Invalid


@dataclass(frozen=True)
class TaskReconciliation:
    status: str
    observed_version: int
    legal_deadlines_verified: bool = False
    court_filing_approved: bool = False
    independent_audit_verified: bool = False


def reconcile_task(core, token, matter_id, task_id, expected_version):
    """Observe current authorized task state without replaying a write.

    observed_completed: task is complete at exactly the expected next version,
    not proof that this caller performed the completion.
    still_open: task remains open at the submitted version.
    unresolved: changed version/state; human inspection is required.
    """
    if (not isinstance(matter_id, str) or not 1 <= len(matter_id) <= 64
            or not isinstance(task_id, str) or not 1 <= len(task_id) <= 64
            or type(expected_version) is not int or expected_version < 1):
        raise Invalid('Invalid task reconciliation request')
    with core.authorized_transaction():
        actor = core._identity(token)
        core._role(actor, matter_id, ('owner', 'editor', 'viewer'))
        row = core.db.execute(
            'SELECT matter_id,version,completed FROM tasks WHERE id=? AND matter_id=?',
            (task_id, matter_id)).fetchone()
        if row is None:
            raise Denied('Access denied')
        # The local audit chain must be consistent, but this alone cannot
        # authenticate independently retained history.
        if not core.verify_audit():
            raise Invalid('Local audit verification failed')
        version = row['version']
        completed = row['completed']
        if type(version) is not int or type(completed) is not int or completed not in (0, 1):
            raise Invalid('Invalid stored task state')
        # Require the task-specific completion event as well as a coherent
        # audit chain. This remains only local evidence, not independent custody.
        matching = core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action=? AND target=?",
            ('task.complete', task_id)).fetchone()[0]
        if ((completed == 1 and matching != 1)
                or (completed == 0 and matching != 0)):
            raise Invalid('Task state and local completion audit disagree')
        if completed == 1 and version == expected_version + 1:
            status = 'observed_completed'
        elif completed == 0 and version == expected_version:
            status = 'still_open'
        else:
            status = 'unresolved'
        return TaskReconciliation(status, version)
