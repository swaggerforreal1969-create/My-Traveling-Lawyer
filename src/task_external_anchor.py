"""Read-only task/audit consistency against a separately pinned signed checkpoint.

This adapter never contacts a provider, persists secrets, modifies task state,
or clears a local write fence. Caller must supply independent trust/configuration.
A synthetic provider cannot confer production custody or release authority.
"""
from dataclasses import dataclass

from .independent_checkpoint_boundary import CheckpointReadbackBoundary, _digest
from .secure_engine import Denied
from .task_reconciliation import reconcile_task


@dataclass(frozen=True)
class TaskAnchorObservation:
    status: str
    checkpoint_sequence: int
    independently_custodied: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


def compare_task_to_checkpoint(core, token, matter_id, task_id,
                               expected_version, *, reservation, boundary):
    """Prove consistency with one externally *pinned* exact event.

    The signed event commits to a task-specific audit record plus a complete
    local audit head at one moment. A rolled-back local database fails when
    compared with the independently retained signed head. This only holds
    when the provider, signer trust root and predecessor pin are genuine and
    separately controlled. Return observation alone, never authorization.
    """
    if not isinstance(boundary, CheckpointReadbackBoundary):
        raise Denied('Independent readback verifier required')
    with core.lock, core.passive_authorization():
        actor=core._identity(token)
        core._role(actor,matter_id,('owner','editor'))
        observed=reconcile_task(core,token,matter_id,task_id,expected_version)
        if observed.status!='observed_completed':
            raise Denied('Local task completion cannot be established')
        events=core.db.execute(
            "SELECT seq,row_hash,actor_id FROM audit_chain "
            "WHERE action='task.complete' AND target=?",(task_id,)).fetchall()
        if len(events)!=1 or events[0]['actor_id']!=actor['id']:
            raise Denied('Task completion is not uniquely actor-scoped')
        local_head=core.audit_head()
        if (type(events[0]['seq']) is not int or
                not isinstance(events[0]['row_hash'],str) or
                len(events[0]['row_hash'])!=64 or
                type(local_head['seq']) is not int or
                not isinstance(local_head['row_hash'],str) or
                len(local_head['row_hash'])!=64):
            raise Denied('Invalid local audit anchor')
        intent={
            'schema':'mtl.task.audit.anchor.v1',
            'matter_id':matter_id,
            'task_id':task_id,
            'expected_version':expected_version,
            'task_event_seq':events[0]['seq'],
            'task_event_hash':events[0]['row_hash'],
            'audit_head_seq':local_head['seq'],
            'audit_head_hash':local_head['row_hash'],
        }
        event_digest=_digest(intent)
    # Never hold SecureCore's lock across a potentially slow or untrusted
    # provider readback. The digest is a frozen local observation, NOT a lease.
    # It may become stale immediately; caller receives no clearance authority.
    verified=boundary.verify(reservation=reservation,event_digest=event_digest)
    # Untrusted readback may yield control to competing local writers or ACL
    # changes. Revalidate the exact actor, permission and committed task/audit
    # snapshot after readback, without extending the session idle lifetime.
    # An observation is not safe to display as CURRENT if local state drifted.
    with core.lock, core.passive_authorization():
        current_actor=core._identity(token)
        core._role(current_actor,matter_id,('owner','editor'))
        if current_actor['id'] != actor['id']:
            raise Denied('Task actor changed during checkpoint readback')
        second=reconcile_task(core,token,matter_id,task_id,expected_version)
        if second.status!='observed_completed':
            raise Denied('Task state changed during checkpoint readback')
        post_events=core.db.execute(
            "SELECT seq,row_hash,actor_id FROM audit_chain "
            "WHERE action='task.complete' AND target=?",(task_id,)).fetchall()
        if (len(post_events)!=1 or
                post_events[0]['seq']!=events[0]['seq'] or
                post_events[0]['row_hash']!=events[0]['row_hash'] or
                post_events[0]['actor_id']!=actor['id']):
            raise Denied('Task audit changed during checkpoint readback')
        post_head=core.audit_head()
        if (post_head['seq'] != local_head['seq'] or
                post_head['row_hash'] != local_head['row_hash']):
            raise Denied('Local audit head changed during checkpoint readback')
    return TaskAnchorObservation(
        'local_and_signed_checkpoint_consistent',verified.sequence)
