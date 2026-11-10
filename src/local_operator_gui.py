"""Offline Tkinter attorney operator: actual mouse/keyboard UI, no HTTP.

All sensitive commands delegate to PrivateAttorneyOperator / SecureCore. The UI
never displays client notes, excerpts, task text, URLs, token or record IDs.
Only experimental local SQLite databases, never real-client production use.
Tkinter is loaded on launch, not during headless test/import.
"""
from dataclasses import dataclass
from pathlib import Path
from getpass import getpass
import argparse

from .private_attorney_operator import PrivateAttorneyOperator
from .secure_engine import SecureCore, Denied, Invalid, Stale
from .research_evidence import EvidenceInvalid
from .attorney_research_workflow import RefreshUnresolved
from .durable_local_write_fence import LocalWriteFence


@dataclass(frozen=True)
class ActionFeedback:
    """Safe UI-facing feedback; custody IDs remain inside the controller."""
    status: str
    message: str


class LocalOperatorController:
    """UI-independent state boundary; no credentials sent to a web client."""

    def __init__(self, core, token, *, durable_fence=None):
        self.operator = PrivateAttorneyOperator(core)
        self._durable_fence = durable_fence
        self._reservation = None  # never exposed in ActionFeedback
        self._token = token
        self._matter_id = None
        self._matters = ()
        self._tasks = ()
        self._reviews = ()
        self._recovery = None
        self._uncertain_task = None  # session-only task identity, never UI output

    def _assert_no_uncertain_review(self):
        if self._uncertain_task is not None:
            self._tasks, self._reviews = (), ()
            raise Invalid('Uncertain task completion; no new writes in this session')
        if self._durable_fence is not None and self._durable_fence.is_pending():
            self._tasks, self._reviews = (), ()
            raise Denied('A write is unresolved. No new write permitted')
        if self._recovery is not None:
            self._tasks, self._reviews = (), ()
            raise Invalid('Resolve pending review using read-only reconciliation first')

    def _clear(self):
        # An in-memory uncertain review retains its exact recovery identity.
        # A different, restarted window may select matters READ-ONLY while
        # the durable global write fence remains pending.
        if self._recovery is not None or self._uncertain_task is not None:
            raise Invalid('Uncertain write; read-only incident review required')
        self._matter_id = None
        self._tasks = ()
        self._reviews = ()

    def list_matters(self):
        # The previous matter list is not authority after a revoked session.
        # Invalidate it before any I/O so failed access cannot reuse stale IDs.
        self._clear()
        self._matters = ()
        index = self.operator.matters(self._token)
        self._matters = tuple(item['matter_id'] for item in index['matters'])
        return len(self._matters)

    def select(self, position):
        # Keep the visible matter list available for a deliberate selection,
        # but no prior task/review selection may survive a failed switch.
        self._clear()
        if type(position) is not int or not 0 <= position < len(self._matters):
            raise Invalid('Invalid matter selection')
        mid = self._matters[position]
        self._matter_id = mid
        return self._load_authorized_work()

    def _load_authorized_work(self):
        # Stage all three reauthorized reads before publishing ANY actionable
        # IDs. A denial after task enumeration must not leave usable task IDs.
        self._tasks, self._reviews = (), ()
        if self._matter_id is None:
            raise Invalid('Matter not selected')
        mid = self._matter_id
        screen = self.operator.select_matter(self._token, mid)
        tasks, reviews = (), ()
        if screen.can_complete_tasks:
            view = self.operator.workflow.journey.workbench.matter(self._token, mid)
            tasks = tuple((item['task_id'], item['version'])
                          for item in view['open_tasks'])
            queue = self.operator.reviewer_inbox(self._token, mid)
            reviews = tuple((item['evidence_id'], item['observation_id'])
                            for item in queue['items'])
        if (self._recovery is not None or self._uncertain_task is not None or
                (self._durable_fence is not None and self._durable_fence.is_pending())):
            # Refresh is allowed for observational purposes only. Pending
            # uncertainty must never repopulate actionable row selections.
            self._tasks, self._reviews = (), ()
        else:
            self._tasks, self._reviews = tasks, reviews
        return screen

    def refresh(self):
        return self._load_authorized_work()

    def counts(self):
        return (len(self._tasks), len(self._reviews))

    def portfolio_summary(self):
        """Fresh authorized private multi-matter counts; never a write grant.

        Hide prior actionable IDs before any portfolio read, even if
        authorization, integrity or reconciliation fails during rendering.
        Preserve unresolved review identity for separate human recovery.
        """
        self._tasks, self._reviews = (), ()
        if self._recovery is None and self._uncertain_task is None:
            self._matter_id = None
            self._matters = ()
        return self.operator.portfolio_summary(self._token)

    def read_only_current_workload(self):
        """Fresh authorized private workload without discarding current matter.

        This observational call never confers write authority; it can be used
        after a confirmed task completion to update the graphical summary.
        """
        return self.operator.portfolio_summary(self._token)

    def has_recovery(self):
        return (self._recovery is not None or self._uncertain_task is not None or (
            self._durable_fence is not None and self._matter_id is not None
            and self._durable_fence.is_pending()))


    def _create_authorized(self, kind, text, *, due_at=None):
        """Explicit local write with persistent conservative no-replay fencing.

        If an outcome or refresh is uncertain, do not clear the pending fence.
        The unknown generic reservation requires authorized incident review.
        """
        self._assert_no_uncertain_review()
        core = self.operator.core
        if self._durable_fence is None:
            raise Denied('Durable local write fence required')
        if not isinstance(text, str) or not text.strip():
            raise Invalid('A title is required')
        if kind == 'task' and self._matter_id is None:
            raise Invalid('Select an authorized matter first')
        with core.lock:
            actor = core._identity(self._token)
            if kind == 'task':
                core._role(actor, self._matter_id, ('owner', 'editor'))
            if not core.verify_audit():
                raise Denied('Local audit verification failed')
        self._reservation = self._durable_fence.begin()
        self._tasks, self._reviews = (), ()
        # The backend independently authorizes under its own transaction.
        # An exception after begin leaves the fence pending, never retries.
        if kind == 'matter':
            created = core.create_matter(self._token, text)
        else:
            created = core.create_task(self._token, self._matter_id, text, due_at)
        try:
            if not core.verify_audit():
                raise Denied('Post-write local audit verification failed')
            if kind == 'matter':
                index = self.operator.matters(self._token)
                if not any(item['matter_id'] == created['id']
                           for item in index['matters']):
                    raise Denied('Created matter not visible after fresh authorization')
            else:
                # Reauthorization and independent local row readback, without
                # exposing task content in the graphical status.
                self.operator.select_matter(self._token, self._matter_id)
                actor = core._identity(self._token)
                core._role(actor, self._matter_id, ('owner', 'editor'))
                row = core.db.execute(
                    'SELECT matter_id FROM tasks WHERE id=?',
                    (created['id'],)).fetchone()
                if row is None or row['matter_id'] != self._matter_id:
                    raise Denied('Created task unavailable after write')
            self._durable_fence.finish_confirmed(
                expected_reservation=self._reservation)
            self._reservation = None
            if kind == 'matter':
                self._clear()
                self._matters = ()
            else:
                self._load_authorized_work()
            return ActionFeedback(kind + '_created',
                                  ('Matter' if kind == 'matter' else 'Task') +
                                  ' saved. Authorized workload refreshed.')
        except Exception:
            # Never imply a safe retry after a successful backend write.
            self._tasks, self._reviews = (), ()
            return ActionFeedback('committed_refresh_unresolved',
                                  'Saved work may exist; confirmation unresolved. '
                                  'Do NOT repeat. Obtain read-only incident review.')

    def create_matter(self, title, confirmed):
        if not confirmed:
            return ActionFeedback('cancelled', 'Cancelled; no write performed.')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:
            raise Invalid('Matter title must be 1–160 characters')
        return self._create_authorized('matter', title.strip())

    def create_task(self, title, due_at, confirmed):
        if not confirmed:
            return ActionFeedback('cancelled', 'Cancelled; no write performed.')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise Invalid('Task text must be 1–200 characters')
        # User typing errors are not uncertain writes; reject BEFORE reserving
        # a crash-durable fence, so a bad timestamp never locks the pilot.
        from datetime import datetime
        if not isinstance(due_at, str):
            raise Invalid('Timezone-aware ISO task date required')
        try:
            timestamp = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                raise ValueError('Missing timezone')
        except ValueError as exc:
            raise Invalid('Timezone-aware ISO task date required') from exc
        return self._create_authorized('task', title.strip(), due_at=due_at)


    def available_research_sources(self):
        """Privacy-safe index of authorized manually entered sources."""
        if self._matter_id is None:
            raise Invalid('Select a matter before reviewing sources')
        sources = self.operator.workflow.evidence.list(self._token, self._matter_id)['sources']
        # IDs stay strictly inside the authenticated controller/dialog.
        return tuple(entry['id'] for entry in sources)

    def _record_manual_research(self, kind, values):
        """One human-confirmed research write, one durable reservation.

        Source and observation are separate commits; never retry an uncertain
        write or pretend both are atomic. A generic pending fence intentionally
        requires independent human incident handling to clear.
        """
        self._assert_no_uncertain_review()
        if self._matter_id is None or self._durable_fence is None:
            raise Denied('Authorized matter and durable local fence required')
        core = self.operator.core
        with core.lock:
            actor = core._identity(self._token)
            core._role(actor, self._matter_id, ('owner','editor'))
            if not core.verify_audit():
                raise Denied('Local audit integrity unavailable')
        self._reservation = self._durable_fence.begin()
        self._tasks, self._reviews = (), ()
        try:
            if kind == 'source':
                title, url, excerpt = values
                made = self.operator.workflow.evidence.add(
                    self._token, self._matter_id, title, url, excerpt)
                record_id = made['id']
                entries = self.available_research_sources()
                if record_id not in entries:
                    raise Denied('Saved source not visible after authorization')
            else:
                source_id, captured, note = values
                made = self.operator.workflow.observations.capture(
                    self._token, self._matter_id, source_id, captured, note)
                record_id = made['observation_id']
                history = self.operator.workflow.observations.history(
                    self._token, self._matter_id, source_id)
                if not any(x['observation_id'] == record_id
                           for x in history['observations']):
                    raise Denied('Saved observation not visible after authorization')
            if not core.verify_audit():
                raise Denied('Local audit check failed after write')
            self._durable_fence.finish_confirmed(
                expected_reservation=self._reservation)
            self._reservation = None
            self._load_authorized_work()
            return ActionFeedback(kind + '_recorded',
                ('Source' if kind == 'source' else 'Manual observation') +
                ' saved. Research is NOT verified legal authority.')
        except Exception:
            # Unknown post-reservation outcome is never a safe replay invitation.
            self._tasks, self._reviews = (), ()
            return ActionFeedback('write_unresolved',
                'Research save outcome is unresolved. Do NOT repeat. '
                'The safety lock remains until authorized incident review.')

    def add_research_source(self, title, url, excerpt, confirmed):
        if not confirmed:
            return ActionFeedback('cancelled','Cancelled; no write performed.')
        # Validate before reserving: ordinary typing errors must not lock work.
        from .research_evidence import ResearchEvidence
        cleaned = ResearchEvidence.clean(title, url, excerpt)
        return self._record_manual_research('source', cleaned)

    def record_research_observation(self, source_id, captured, note, confirmed):
        if not confirmed:
            return ActionFeedback('cancelled','Cancelled; no write performed.')
        if not isinstance(captured,str) or not 1 <= len(captured.strip()) <= 12000:
            raise Invalid('Manual observation text required')
        if not isinstance(note,str) or not 12 <= len(note.strip()) <= 1200:
            raise Invalid('Manual observation note must be 12–1200 characters')
        if source_id not in self.available_research_sources():
            raise Denied('Source is not in currently authorized matter')
        return self._record_manual_research(
            'observation', (source_id, captured.strip(), note.strip()))

    def review(self, position, decision, note, confirmed):
        if not confirmed:
            return ActionFeedback('cancelled', 'Cancelled; no write performed.')
        self._assert_no_uncertain_review()
        if type(position) is not int or not 0 <= position < len(self._reviews):
            raise Invalid('Invalid review selection')
        if decision not in ('corroborated_manually', 'needs_further_review', 'rejected'):
            raise Invalid('Invalid review decision')
        if not isinstance(note, str) or not 15 <= len(note.strip()) <= 1200:
            raise Invalid('Human review note must be 15–1200 characters')
        eid, oid = self._reviews[position]
        if self._durable_fence is not None:
            with self.operator.core.lock:
                actor = self.operator.core._identity(self._token)
                self.operator.core._role(actor, self._matter_id, ('owner', 'editor'))
                tip = self.operator.core.db.execute(
                    'SELECT COALESCE(MAX(seq),0) FROM audit_chain').fetchone()[0]
            self._reservation = self._durable_fence.begin(
                review_identity=(actor['id'], self._matter_id, eid, oid),
                audit_before=tip)  # intent is committed BEFORE the write
        self._recovery = None
        try:
            committed = self.operator.decide_review(self._token, self._matter_id,
                                                    eid, oid, decision, note)
        except RefreshUnresolved as uncertain:
            if uncertain.operation == 'source.second_review' and uncertain.record_id:
                self._recovery = (uncertain.operation, uncertain.record_id)
            self._tasks, self._reviews = (), ()
            return ActionFeedback('committed_refresh_unresolved',
                                  'Review committed, display refresh unresolved. Do NOT repeat.')
        except (Denied, Invalid, Stale, EvidenceInvalid):
            self._tasks, self._reviews = (), ()
            raise
        try:
            self.refresh()
        except Exception:
            # The local second-human review was committed, but a separate
            # authorized display read failed. Preserve BOTH local recovery
            # identity and durable pending reservation across restart.
            self._recovery = ('source.second_review', committed.record_id)
            self._tasks, self._reviews = (), ()
            return ActionFeedback(
                'committed_refresh_unresolved',
                'Review committed, display refresh unresolved. Do NOT repeat.')
        # Clear only the exact reservation AFTER the final authorized read;
        # failed CAS is an incident, never implicit permission to write again.
        if self._durable_fence is not None:
            try:
                self._durable_fence.finish_confirmed(
                    expected_reservation=self._reservation)
            except Exception:
                self._recovery = ('source.second_review', committed.record_id)
                self._tasks, self._reviews = (), ()
                return ActionFeedback(
                    'committed_refresh_unresolved',
                    'Review committed; local write fence unresolved. Do NOT repeat.')
            self._reservation = None
            # The pre-clearance read is deliberately non-actionable while the
            # durable fence is pending. Reauthorize the selectable rows AFTER
            # exact clearance; never replay the previously committed review.
            try:
                self.refresh()
            except Exception:
                self._recovery = ('source.second_review', committed.record_id)
                self._tasks, self._reviews = (), ()
                return ActionFeedback(
                    'committed_refresh_unresolved',
                    'Review committed; final display unavailable. Do NOT repeat.')
        return ActionFeedback('review_committed', 'Review recorded. Readiness refreshed.')

    def complete(self, position, confirmed):
        if not confirmed:
            return ActionFeedback('cancelled', 'Cancelled; no write performed.')
        self._assert_no_uncertain_review()
        if type(position) is not int or not 0 <= position < len(self._tasks):
            raise Invalid('Invalid task selection')
        task_id, version = self._tasks[position]
        if self._durable_fence is not None:
            core=self.operator.core
            with core.lock:
                actor=core._identity(self._token)
                core._role(actor,self._matter_id,('owner','editor'))
                tip=core.db.execute(
                    'SELECT COALESCE(MAX(seq),0) FROM audit_chain').fetchone()[0]
            # Anonymous local fingerprint survives restart. The real write
            # independently reauthorizes under its own SQLite transaction.
            self._reservation = self._durable_fence.begin(
                task_identity=(actor['id'],self._matter_id,task_id,version),
                audit_before=tip)
        self._recovery = None
        # Any exception, ambiguous outcome, or crash leaves the fence pending.
        result = self.operator.complete_task(
            self._token, self._matter_id, task_id, version)
        allowed = {
            'completed_and_refreshed': 'Task completed. Readiness refreshed.',
            'observed_completed_no_write': 'Task already completed; no write performed.',
            'unresolved_no_write': 'Task state changed; no write performed.',
            'committed_refresh_unresolved': 'Task committed; refresh unresolved. Do NOT repeat.'
        }
        if result.status not in allowed:
            raise Invalid('Unrecognized completion state')
        if result.status == 'committed_refresh_unresolved':
            self._uncertain_task = (self._matter_id, task_id, version)
            self._tasks, self._reviews = (), ()
            return ActionFeedback(result.status, allowed[result.status])
        try:
            self.refresh()
        except Exception:
            self._tasks, self._reviews = (), ()
            # Keep the durable sidecar pending across a crash or restart.
            # The write outcome and presentation are not fully reconciled.
            self._uncertain_task = (self._matter_id, task_id, version)
            if result.status == 'completed_and_refreshed':
                return ActionFeedback(
                    'committed_refresh_unresolved',
                    'Task committed; display refresh unresolved. Do NOT repeat.')
            return ActionFeedback('unresolved_no_write',
                                  'Read-only state refresh unresolved; no new write.')
        # Only clear the exact prewrite reservation after successful delegated
        # outcome AND final reauthorized display read. A failed CAS must leave
        # actions unavailable; neither retries nor assumptions are permitted.
        if self._durable_fence is not None:
            try:
                self._durable_fence.finish_confirmed(
                    expected_reservation=self._reservation)
            except Exception:
                self._uncertain_task = (self._matter_id, task_id, version)
                self._tasks, self._reviews = (), ()
                return ActionFeedback(
                    'committed_refresh_unresolved',
                    'Local fence clearance unresolved. Do NOT repeat the write.')
            self._reservation = None
            # A fenced verification read cannot populate selectable actions.
            # Once exact clearance succeeds, independently reauthorize again.
            try:
                self.refresh()
            except Exception:
                self._uncertain_task = (self._matter_id, task_id, version)
                self._tasks, self._reviews = (), ()
                if result.status == 'completed_and_refreshed':
                    return ActionFeedback(
                        'committed_refresh_unresolved',
                        'Task committed; final display unavailable. Do NOT repeat.')
                return ActionFeedback(
                    'unresolved_no_write',
                    'Read-only refresh unavailable. No further write permitted.')
        return ActionFeedback(result.status, allowed[result.status])

    def inspect_uncertain_task_read_only(self):
        """Observe an uncertain local task, without clearing the session fence.

        Only a human-initiated read; local audit is not independent custody.
        No completion replay or renewed write authority is ever issued here.
        """
        if self._uncertain_task is None:
            raise Invalid('No uncertain task in this session')
        self._tasks, self._reviews = (), ()
        matter_id, task_id, version = self._uncertain_task
        result = self.operator.reconcile_task(
            self._token, matter_id, task_id, version)
        return ActionFeedback(
            'observed_local_' + result.status,
            'Local task state: ' + result.status +
            '. Session remains write-fenced. Do NOT repeat the write.')

    def reconcile_pending_task_after_restart(self):
        """Actor-authorized, strictly observational local task readback.

        Do NOT clear the sidecar fence or repeat a write, even when the local
        task/audit show an exact commit. External custody is not established.
        """
        if (self._durable_fence is None or not self._durable_fence.is_pending()
                or self._matter_id is None):
            raise Invalid('No selected task recovery context')
        self._tasks,self._reviews=(),()
        core=self.operator.core
        with core.lock, core.passive_authorization():
            actor=core._identity(self._token)
            core._role(actor,self._matter_id,('owner','editor'))
            if not core.verify_audit():
                raise Denied('Local task audit failed verification')
            rows=core.db.execute(
                'SELECT id,version,completed FROM tasks WHERE matter_id=? '
                'ORDER BY id LIMIT 102',(self._matter_id,)).fetchall()
            if len(rows)>100:
                raise Denied('Task recovery bound exceeded')
            matches=[]
            for row in rows:
                version=row['version']
                completed=row['completed']
                if (type(version) is not int or version<1 or
                        type(completed) is not int or completed not in (0,1)):
                    raise Denied('Invalid task recovery state')
                expected=version-1 if completed else version
                if expected<1:
                    continue
                identity=(actor['id'],self._matter_id,row['id'],expected)
                events=core.db.execute(
                    "SELECT seq,actor_id FROM audit_chain WHERE action='task.complete' "
                    "AND target=?",(row['id'],)).fetchall()
                if completed and (len(events)!=1 or events[0]['actor_id']!=actor['id']):
                    continue
                if not completed and events:
                    continue
                event_seq=events[0]['seq'] if completed else None
                if self._durable_fence.pending_task_matches(identity,event_seq):
                    matches.append('observed_local_commit' if completed
                                   else 'observed_local_no_commit')
            if len(matches)!=1:
                return ActionFeedback('reconciliation_unresolved',
                    'Task reservation cannot be uniquely reconciled. '
                    'Write fence remains pending. Do NOT repeat.')
            if matches[0]=='observed_local_commit':
                return ActionFeedback('observed_local_commit',
                    'Local task completion and matching audit observed. '
                    'Fence remains pending for independent incident review.')
            return ActionFeedback('observed_local_no_commit',
                'Task still open at reserved version. Local no-commit observed; '
                'fence remains pending. Do NOT retry automatically.')

    def reconcile_pending_review_after_restart(self):
        """Human-triggered ONLY, actor-authorized read-only local reconciliation.

        Scan only this actor's own review records in the selected matter; use
        the prewrite fingerprint and monotonic local audit-seq lower bound.
        The local DB and fence can roll back together. No custody proof.
        """
        if (self._durable_fence is None or not self._durable_fence.is_pending()
                or self._matter_id is None):
            raise Invalid('No restart recovery available')
        self._tasks, self._reviews = (), ()
        reservation = self._durable_fence.pending_reservation()
        core = self.operator.core
        with core.lock:
            actor=core._identity(self._token)
            core._role(actor, self._matter_id, ('owner','editor'))
            if not core.verify_audit():
                raise Denied('Local audit not verified')
            rows=core.db.execute(
                '''SELECT id,evidence_id,observation_id FROM source_second_review
                   WHERE matter_id=? AND reviewer_id=?
                   ORDER BY recorded_at,id LIMIT 102''',
                (self._matter_id,actor['id'])).fetchall()
            if len(rows)>100:
                raise Denied('Recovery search limit exceeded')
            matches=[]
            for row in rows:
                events=core.db.execute(
                    '''SELECT seq,actor_id FROM audit_chain
                       WHERE action='research.second_source_review' AND target=?''',
                    (row['id'],)).fetchall()
                if len(events)!=1 or events[0]['actor_id']!=actor['id']:
                    continue
                identity=(actor['id'],self._matter_id,
                          row['evidence_id'],row['observation_id'])
                if self._durable_fence.pending_review_matches(identity,events[0]['seq']):
                    matches.append(row['id'])
            if len(matches)!=1:
                return ActionFeedback(
                    'reconciliation_unresolved',
                    'No unique actor-authorized local review commit observed. '
                    'Write fence remains pending; do NOT repeat.')
            # Only this actor-scoped research history check can confirm the
            # matching local review. Never trust the fingerprint in isolation.
            result=self.operator.reconcile_research(
                self._token,self._matter_id,'source.second_review',matches[0])
            if result.status!='observed_local_commit':
                return ActionFeedback(
                    'reconciliation_unresolved',
                    'Review reconciliation unresolved; no write permitted.')
            self._durable_fence.finish_confirmed(
                expected_reservation=reservation)
            self._recovery=None
        try:
            self.refresh()
        except Exception:
            self._tasks,self._reviews=(),()
            return ActionFeedback(
                'observed_local_commit_refresh_unresolved',
                'Local review commit observed; display unresolved. '
                'Independent custody not verified. Do NOT repeat.')
        return ActionFeedback(
            'observed_local_commit',
            'Local review commit observed after restart; '
            'independent custody not verified.')

    def reconcile_last_review(self):
        if self._recovery is None and self._durable_fence is not None:
            return self.reconcile_pending_review_after_restart()
        if self._recovery is None or self._matter_id is None:
            raise Invalid('No uncertain review to reconcile')
        operation, record_id = self._recovery
        result = self.operator.reconcile_research(
            self._token, self._matter_id, operation, record_id)
        # Only an authenticated, independently scoped reconciliation response
        # may resolve uncertainty. Refreshing the visible task list is a
        # separate read and must never reverse the observed recovery result.
        if result.status != 'observed_local_commit':
            self._tasks, self._reviews = (), ()
            return ActionFeedback(
                'reconciliation_unresolved',
                'Review reconciliation unresolved. Do NOT repeat the write.')
        self._recovery = None
        if self._durable_fence is not None and self._durable_fence.is_pending():
            self._durable_fence.finish_confirmed(
                expected_reservation=self._reservation)
            self._reservation = None
        try:
            self.refresh()
        except Exception:
            self._tasks, self._reviews = (), ()
            return ActionFeedback(
                'observed_local_commit_refresh_unresolved',
                'Local review commit observed; display still unresolved. '
                'Independent custody not verified. Do NOT repeat.')
        return ActionFeedback('observed_local_commit',
                              'Local review commit observed; independent custody not verified.')


def launch_gui(core, token, *, run_mainloop=True):
    """Real Tk controls. Disabled write buttons until a current row selected."""
    import tkinter as tk
    from tkinter import ttk, messagebox
    db_path = core.db.execute('PRAGMA database_list').fetchone()['file']
    controller = LocalOperatorController(
        core, token, durable_fence=LocalWriteFence(db_path) if db_path else None)
    root = tk.Tk()
    private_forms = []  # confidential transient entry forms owned by this window
    root.title('Private Attorney — Local Operator')
    root.geometry('760x650')
    root.minsize(580, 520)
    outer = ttk.Frame(root, padding=10)
    outer.pack(fill='both', expand=True)
    ttk.Label(outer, text='Private attorney operator',
              font=('TkDefaultFont', 18, 'bold')).pack(anchor='w')
    ttk.Label(outer, text='OFFLINE EXPERIMENTAL WORKFLOW — NOT VERIFIED LAW OR FILING APPROVAL',
              wraplength=500).pack(anchor='w', pady=(2, 5))
    status = tk.StringVar(value='Select a matter. No credentials or client text shown.')
    ttk.Label(outer, textvariable=status, wraplength=500).pack(anchor='w')
    panels = ttk.Frame(outer)
    panels.pack(fill='both', expand=True, pady=4)
    panels.columnconfigure((0,1,2), weight=1, uniform='private-work')
    panels.rowconfigure(1,weight=1)
    ttk.Label(panels,text='Authorized matters').grid(row=0,column=0,sticky='w')
    ttk.Label(panels,text='Second-human reviews').grid(row=0,column=1,sticky='w')
    ttk.Label(panels,text='Open tasks').grid(row=0,column=2,sticky='w')
    matter_list = tk.Listbox(panels, exportselection=False, height=4, font=('TkDefaultFont',12))
    review_list = tk.Listbox(panels, exportselection=False, height=4, font=('TkDefaultFont',12))
    task_list = tk.Listbox(panels, exportselection=False, height=4, font=('TkDefaultFont',12))
    for col, control in enumerate((matter_list,review_list,task_list)):
        control.grid(row=1,column=col,sticky='nsew',padx=4)
    actions = ttk.Frame(outer)
    actions.pack(fill='x')
    choice = tk.StringVar(value='corroborated_manually')
    ttk.Label(actions,text='Review decision').pack(anchor='w')
    decisions = ttk.Combobox(actions, textvariable=choice, state='readonly',
        values=('corroborated_manually','needs_further_review','rejected'))
    decisions.pack(fill='x')
    ttk.Label(actions,text='Second-human note (15–1200 characters)').pack(anchor='w',pady=(8,0))
    note = tk.Text(actions,height=2,wrap='word')
    note.pack(fill='x')
    # Privacy-safe observational panel. No case data, tokens or internal IDs.
    portfolio_panel = ttk.LabelFrame(outer, text='Authorized workload — read only')
    portfolio_panel.pack(fill='x', pady=(4, 2))
    portfolio_text = tk.Text(portfolio_panel, height=2, wrap='word',
                             font=('TkDefaultFont', 11), takefocus=True)
    portfolio_text.pack(fill='x')
    portfolio_text.insert('1.0', 'Select Workload to reauthorize current counts.')
    portfolio_text.configure(state='disabled')
    buttons = ttk.Frame(actions)
    buttons.pack(fill='x', pady=3)
    buttons.columnconfigure((0, 1, 2), weight=1)

    def update_controls():
        # The GUI has no authority of its own; this only prevents misleading
        # clicks. Every operation still reauthorizes in the backend.
        select_button.configure(state='normal' if matter_list.curselection() else 'disabled')
        refresh_button.configure(state='normal' if controller._matter_id is not None else 'disabled')
        review_button.configure(state='normal' if review_list.curselection() else 'disabled')
        task_button.configure(state='normal' if task_list.curselection() else 'disabled')
        recovery_button.configure(state='normal' if controller.has_recovery() else 'disabled')

    def clear_portfolio():
        portfolio_text.configure(state='normal')
        portfolio_text.delete('1.0', 'end')
        portfolio_text.configure(state='disabled')

    def clear_all_visible_work():
        # Close confidential unsubmitted forms when access/window is hidden.
        for private_form in private_forms[:]:
            try:
                if private_form.winfo_exists():
                    private_form.destroy()
            except tk.TclError:
                pass
        private_forms[:] = [p for p in private_forms if p.winfo_exists()]
        # A human review draft is private even before it is committed.
        # Never retain it through logout, revoked access, failed refresh,
        # navigation to the portfolio, or a hidden/minimized window.
        note.delete('1.0', 'end')
        clear_portfolio()
        matter_list.delete(0, 'end')
        review_list.delete(0, 'end')
        task_list.delete(0, 'end')
        controller._tasks, controller._reviews = (), ()
        controller._matters = ()
        # Forget the selected matter on ordinary privacy invalidation; a
        # revoked view must never regain actionable IDs through Refresh alone.
        # Pending review recovery retains its exact matter and reservation.
        if not controller.has_recovery():
            controller._matter_id = None
        update_controls()

    def display_private_workload(summary):
        # No raw client text, case identifiers, tokens or notes are supplied.
        portfolio_text.configure(state='normal')
        portfolio_text.delete('1.0', 'end')
        portfolio_text.insert('1.0', summary)
        portfolio_text.configure(state='disabled')

    def show_portfolio():
        # Never leave stale aggregate counts visible after failed authorization.
        clear_all_visible_work()
        try:
            summary = controller.portfolio_summary()
            portfolio_text.configure(state='normal')
            portfolio_text.insert('1.0', summary)
            portfolio_text.configure(state='disabled')
            status.set('Read-only workload refreshed. Select Refresh matters to return.')
            portfolio_text.focus_set()
        except (Denied, Invalid, Stale, EvidenceInvalid):
            clear_all_visible_work()
            status.set('Workload unavailable or access changed. Reauthenticate.')
        update_controls()

    def privacy_check():
        """Periodic authorization is observational; a denial removes visible work.

        This is a bounded local visibility measure, not instantaneous
        revocation, an external custody assertion, or a new write grant.
        """
        try:
            # Passive observations must NEVER refresh session idle lifetime.
            with core.passive_authorization():
                return privacy_check_passive()
        except Exception:
            clear_all_visible_work()
            status.set('Private work hidden. Reauthenticate before continuing.')
            update_controls()

    def privacy_check_passive():
        try:
            current = controller.operator.portfolio_summary(controller._token)
            # Authorization for the overall portfolio is not a lease on an
            # existing selected matter. Reconcile fresh action identities on
            # every tick; invalidate rather than silently repoint a selection
            # after ACL changes or concurrent task/review mutations.
            if controller._matter_id is not None:
                old_tasks = controller._tasks
                old_reviews = controller._reviews
                controller._load_authorized_work()
                if (controller._tasks != old_tasks or
                        controller._reviews != old_reviews):
                    clear_all_visible_work()
                    status.set('Matter changed. Select it again after reauthorization.')
                    return
            # An already displayed portfolio must not retain old counts after
            # an authorized matter-index/task-count change.
            existing = portfolio_text.get('1.0', 'end-1c')
            if existing.startswith('PRIVATE ATTORNEY MATTER PORTFOLIO'):
                if current != existing:
                    clear_all_visible_work()
                    portfolio_text.configure(state='normal')
                    portfolio_text.insert('1.0', current)
                    portfolio_text.configure(state='disabled')
        except Exception:
            # Unexpected failures are denial for display purposes. Preserve
            # the controller's durable and in-memory recovery identity.
            clear_all_visible_work()
            status.set('Private work hidden. Reauthenticate before continuing.')
        update_controls()

    # Tk's after callbacks outlive individual destroyed windows unless
    # explicitly cancelled. Keep one owned timer per root and cancel it on
    # destruction, avoiding stale Tcl callback invocations on Windows.
    privacy_timer = {'id': None, 'closed': False}

    def privacy_tick():
        privacy_timer['id'] = None
        if privacy_timer['closed'] or not root.winfo_exists():
            return
        privacy_check()
        if not privacy_timer['closed'] and root.winfo_exists():
            privacy_timer['id'] = root.after(2000, privacy_tick)

    def privacy_window_destroyed(event):
        if event.widget is not root:
            return
        privacy_timer['closed'] = True
        pending = privacy_timer['id']
        privacy_timer['id'] = None
        if pending is not None:
            try:
                root.after_cancel(pending)
            except tk.TclError:
                pass

    def privacy_window_hidden(event):
        # Toplevel unmapping/minimizing invalidates the visible session.
        # Ordinary focus changes among child controls must NOT clear data.
        if event.widget is root:
            clear_all_visible_work()
            status.set('Private work hidden while window is not visible.')

    # Exposed solely for deterministic native GUI acceptance without waiting
    # on wall-clock timers. Every invocation performs real backend checking.
    root.privacy_check = privacy_check
    root.bind('<Unmap>', privacy_window_hidden, add='+')
    root.bind('<Destroy>', privacy_window_destroyed, add='+')
    privacy_timer['id'] = root.after(2000, privacy_tick)

    def refresh_lists():
        # Rebuilding the matter index invalidates the review-note context.
        note.delete('1.0', 'end')
        clear_portfolio()
        try:
            number = controller.list_matters()
            matter_list.delete(0,'end')
            for i in range(number):
                matter_list.insert('end', 'Matter '+str(i+1))
            review_list.delete(0,'end')
            task_list.delete(0,'end')
            status.set('Select a matter. No client names or IDs shown.')
            matter_list.focus_set()
        except (Denied, Invalid, Stale, EvidenceInvalid):
            status.set('Access denied or state changed. Close and reauthenticate.')
            clear_all_visible_work()
        update_controls()

    def select_matter():
        # A draft belongs to its previous matter; never carry it across.
        note.delete('1.0', 'end')
        clear_portfolio()
        if not matter_list.curselection():
            return
        try:
            controller.select(matter_list.curselection()[0])
            display_counts()
        except (Denied, Invalid, Stale, EvidenceInvalid):
            status.set('Matter access denied. Reauthenticate before continuing.')
            clear_all_visible_work()
        update_controls()

    def display_counts():
        clear_portfolio()
        try:
            screen=controller.refresh()
            tasks,reviews=controller.counts()
            task_list.delete(0,'end')
            review_list.delete(0,'end')
            for i in range(tasks): task_list.insert('end','Open task '+str(i+1))
            for i in range(reviews): review_list.insert('end','Review '+str(i+1))
            status.set('Open tasks: '+str(screen.open_task_count)+
                       ' • reviews awaiting a second human: '+str(screen.pending_second_review_count))
        except (Denied, Invalid, Stale, EvidenceInvalid):
            status.set('Authorization or state changed. Reauthenticate.')
            clear_all_visible_work()
        update_controls()

    def clear_stale_actions():
        note.delete('1.0', 'end')
        clear_portfolio()
        # Reject stale on-screen selections after any denied action. A user's
        # next attempt must begin with a separately authorized refresh.
        review_list.delete(0, 'end')
        task_list.delete(0, 'end')
        update_controls()

    def notify_uncertain_result(result):
        if result.status == 'committed_refresh_unresolved':
            # A modal acknowledgement makes an irreversible committed outcome
            # visible and keyboard-accessible without automatically replaying.
            messagebox.showwarning(
                'Write committed — refresh unresolved',
                result.message + '\\nDo not repeat the action. '
                'Use authorized read-only recovery if available.',
                parent=root)

    def confirmation_still_current(kind, position, original_matter, identity):
        """After modal event processing, require the exact authorized target.

        Modal dialogs run nested Tk events; selection, ACL and source state
        can change before the user's confirmation returns. Recheck before
        issuing a write, with backend authorization still authoritative.
        """
        if controller._matter_id != original_matter:
            raise Denied('Matter changed during confirmation')
        controller._load_authorized_work()
        if controller._matter_id != original_matter:
            raise Denied('Matter changed during confirmation')
        identities = controller._reviews if kind == 'review' else controller._tasks
        widget = review_list if kind == 'review' else task_list
        if (type(position) is not int or position < 0 or
                position >= len(identities) or
                identities[position] != identity or
                tuple(widget.curselection()) != (position,)):
            raise Stale('Selected action changed during confirmation')

    # One in-flight human confirmation per window, including nested Tk events.
    write_confirmation = {'active': False}

    def submit_review():
        if write_confirmation['active']:
            status.set('An authorization confirmation is already active. No new write.')
            return
        write_confirmation['active'] = True
        try:
            if not review_list.curselection():
                status.set('Select a current human-review item before continuing.')
                review_list.focus_set()
                return
            human_note = note.get('1.0', 'end-1c')
            # Reject incomplete notes before soliciting a legally consequential
            # confirmation. The backend retains its independent validation.
            if not 15 <= len(human_note.strip()) <= 1200:
                status.set('Review note must contain 15–1200 characters. No write performed.')
                # An explicit invalid-note button action must focus this field
                # even when the native runner currently has no focused window.
                note.focus_force()
                return
            position = review_list.curselection()[0]
            original_matter = controller._matter_id
            try:
                identity = controller._reviews[position]
            except (IndexError, TypeError):
                clear_stale_actions()
                return
            decision = choice.get()
            if not messagebox.askyesno('Confirm second-human review',
                                       'Record this one review? No automatic retry.'):
                status.set('Cancelled; no write performed.')
                return
            try:
                confirmation_still_current('review', position, original_matter, identity)
                if choice.get() != decision or note.get('1.0', 'end-1c') != human_note:
                    raise Stale('Human review input changed during confirmation')
                result=controller.review(position, decision, human_note, True)
                note.delete('1.0','end')
                if result.status == 'review_committed':
                    display_counts()
                else:
                    review_list.delete(0,'end')
                    task_list.delete(0,'end')
                status.set(result.message)
                update_controls()
                notify_uncertain_result(result)
            except (Denied, Invalid, Stale, EvidenceInvalid):
                status.set('Review rejected: stale, unauthorized or invalid; no retry.')
                clear_stale_actions()
                review_list.focus_set()
    
        finally:
            write_confirmation['active'] = False

    def submit_task():
        if write_confirmation['active']:
            status.set('An authorization confirmation is already active. No new write.')
            return
        write_confirmation['active'] = True
        try:
            if not task_list.curselection(): return
            position = task_list.curselection()[0]
            original_matter = controller._matter_id
            try:
                identity = controller._tasks[position]
            except (IndexError, TypeError):
                clear_stale_actions()
                return
            if not messagebox.askyesno('Confirm task completion',
                                       'Complete this one task? No automatic retry.'):
                status.set('Cancelled; no write performed.')
                return
            try:
                confirmation_still_current('task', position, original_matter, identity)
                result=controller.complete(position, True)
                if result.status == 'completed_and_refreshed':
                    # Refresh actionable rows, then separately reauthorize the
                    # GUI's read-only portfolio. Do not turn a committed task
                    # into an apparent failed write or replay on read failure.
                    display_counts()
                    try:
                        summary=controller.read_only_current_workload()
                        display_private_workload(summary)
                    except Exception:
                        clear_all_visible_work()
                        status.set('Task may be committed; workload refresh unresolved. '
                                   'Do NOT repeat. Reopen read-only.')
                        messagebox.showwarning(
                            'Workload refresh unresolved',
                            'Task completion was acknowledged, but the private '
                            'workload could not be refreshed. Do NOT repeat.',
                            parent=root)
                        return
                elif result.status != 'committed_refresh_unresolved':
                    display_counts()
                else:
                    task_list.delete(0,'end')
                    review_list.delete(0,'end')
                status.set(result.message)
                update_controls()
                notify_uncertain_result(result)
            except (Denied, Invalid, Stale, EvidenceInvalid):
                status.set('Task rejected: unauthorized or stale. Reopen read-only.')
                clear_stale_actions()
    
        finally:
            write_confirmation['active'] = False

    def recover():
        try:
            if controller._uncertain_task is not None:
                result=controller.inspect_uncertain_task_read_only()
            elif (controller._durable_fence is not None and
                    controller._durable_fence.is_pending() and
                    controller._durable_fence.pending_kind()=='task'):
                result=controller.reconcile_pending_task_after_restart()
            else:
                result=controller.reconcile_last_review()
            display_counts()
            status.set(result.message)
            update_controls()
            if result.status in (
                    'reconciliation_unresolved',
                    'observed_local_commit_refresh_unresolved'):
                messagebox.showwarning(
                    'Review recovery requires attention',
                    result.message, parent=root)
        except (Denied, Invalid, Stale, EvidenceInvalid):
            status.set('Read-only recovery unresolved. Do NOT repeat the write.')
            update_controls()


    def create_record(kind):
        """A single deliberate, confidential local desktop create action."""
        if write_confirmation['active']:
            status.set('Another confirmation is active. No new write.')
            return
        if kind == 'task' and controller._matter_id is None:
            status.set('Select a current matter before adding a task.')
            return
        if controller.has_recovery():
            status.set('A write is unresolved. No new write permitted.')
            return
        dialog = tk.Toplevel(root)
        dialog.title('New fictional matter' if kind == 'matter' else 'New fictional task')
        dialog.transient(root)
        dialog.resizable(False, False)
        form = ttk.Frame(dialog, padding=12)
        form.pack(fill='both', expand=True)
        ttk.Label(form, text='Private title (not displayed after saving)').pack(anchor='w')
        title_input = ttk.Entry(form, width=48)
        title_input.pack(fill='x')
        due_input = None
        if kind == 'task':
            ttk.Label(form, text='User-entered UTC date and time, e.g. 2030-01-01T00:00:00Z').pack(anchor='w')
            due_input = ttk.Entry(form, width=48)
            due_input.insert(0, '2030-01-01T00:00:00Z')
            due_input.pack(fill='x')
        before = controller._matter_id
        def submit():
            if write_confirmation['active']:
                return
            title = title_input.get()
            due = due_input.get() if due_input is not None else None
            if not title.strip() or len(title.strip()) > (160 if kind == 'matter' else 200):
                status.set('Enter a valid private title; no write performed.')
                title_input.focus_set()
                return
            write_confirmation['active'] = True
            try:
                if not messagebox.askyesno('Confirm save',
                    'Save this one fictional ' + kind + '? No automatic retry.',
                    parent=dialog):
                    return
                if kind == 'task' and controller._matter_id != before:
                    raise Denied('Matter changed during confirmation')
                if controller.has_recovery():
                    raise Denied('A prior write remains unresolved')
                result = (controller.create_matter(title, True) if kind == 'matter'
                          else controller.create_task(title, due, True))
                title_input.delete(0, 'end')
                if due_input is not None:
                    due_input.delete(0, 'end')
                dialog.destroy()
                status.set(result.message)
                if result.status == 'matter_created':
                    refresh_lists()
                elif result.status == 'task_created':
                    display_counts()
                else:
                    clear_stale_actions()
                    messagebox.showwarning('Save unresolved', result.message,
                                           parent=root)
            except (Denied, Invalid, Stale, EvidenceInvalid):
                status.set('Save denied or uncertain. Do not repeat without review.')
                clear_stale_actions()
            finally:
                write_confirmation['active'] = False
                update_controls()
        ttk.Button(form, text='Save ' + kind, command=submit).pack(side='left', pady=8)
        ttk.Button(form, text='Cancel', command=dialog.destroy).pack(side='right', pady=8)
        dialog.protocol('WM_DELETE_WINDOW', dialog.destroy)
        title_input.focus_set()

    create_menu = tk.Menu(root, tearoff=False)
    create_menu.add_command(label='New matter', command=lambda: create_record('matter'))
    create_menu.add_command(label='New task', command=lambda: create_record('task'))
    root_menu = tk.Menu(root, tearoff=False)
    root_menu.add_cascade(label='Create', menu=create_menu)
    root.configure(menu=root_menu)


    def research_entry(kind):
        """Private local manual-source forms. No external fetches or AI calls."""
        if write_confirmation['active'] or controller.has_recovery():
            status.set('A write is unresolved or confirmation active. No write.')
            return
        if controller._matter_id is None:
            status.set('Select an authorized matter before adding research.')
            return
        try:
            sources = controller.available_research_sources()
        except (Denied,Invalid,Stale,EvidenceInvalid):
            clear_all_visible_work()
            status.set('Research access denied. Reauthenticate.')
            return
        if kind == 'observation' and not sources:
            status.set('Add a source first; no manual source is available.')
            return
        dialog = tk.Toplevel(root)
        dialog.title('Fictional research source' if kind=='source'
                     else 'Manual source observation')
        dialog.transient(root)
        dialog.resizable(False,False)
        private_forms.append(dialog)
        form = ttk.Frame(dialog,padding=10)
        form.pack(fill='both',expand=True)
        fields = {}
        if kind == 'source':
            specifications=(('title','Source title, fictional only'),
                            ('url','HTTPS source URL (not fetched)'),
                            ('excerpt','Manually entered excerpt'))
        else:
            ttk.Label(form,text='Source number (no confidential title shown)').pack(anchor='w')
            chosen = ttk.Combobox(form,state='readonly',
                     values=tuple('Source '+str(i+1) for i in range(len(sources))))
            chosen.current(0)
            chosen.pack(fill='x')
            specifications=(('captured','Manually observed source text'),
                            ('note','Human observation note (12–1200 characters)'))
        for key,title in specifications:
            ttk.Label(form,text=title).pack(anchor='w')
            field = ttk.Entry(form,width=55)
            field.pack(fill='x')
            fields[key]=field
        original_matter=controller._matter_id
        def save():
            if write_confirmation['active']:
                return
            values={name:item.get() for name,item in fields.items()}
            # Revalidate current account, matter and exact source selection
            # after the native modal's nested Tk event processing.
            write_confirmation['active']=True
            try:
                if not messagebox.askyesno('Confirm manual research entry',
                    'Save this fictional manual research entry? Not verified law.',
                    parent=dialog):
                    return
                if controller._matter_id!=original_matter or controller.has_recovery():
                    raise Denied('Matter or safety status changed')
                if kind=='source':
                    result=controller.add_research_source(
                        values['title'],values['url'],values['excerpt'],True)
                else:
                    idx=chosen.current()
                    if idx<0 or idx>=len(sources) or (
                            sources!=controller.available_research_sources()):
                        raise Stale('Source list changed')
                    result=controller.record_research_observation(
                        sources[idx],values['captured'],values['note'],True)
                for input_field in fields.values():
                    input_field.delete(0,'end')
                dialog.destroy()
                status.set(result.message)
                if result.status in ('source_recorded','observation_recorded'):
                    display_counts()
                    status.set(result.message)
                else:
                    clear_stale_actions()
                    messagebox.showwarning('Research save unresolved',
                        result.message,parent=root)
            except (Denied,Invalid,Stale,EvidenceInvalid):
                status.set('Research entry rejected. No new write authorized.')
                # Do not erase an already entered draft on a validation error.
            finally:
                write_confirmation['active']=False
                update_controls()
        ttk.Button(form,text='Save manual entry',command=save).pack(side='left',pady=8)
        ttk.Button(form,text='Cancel',command=dialog.destroy).pack(side='right',pady=8)
        dialog.protocol('WM_DELETE_WINDOW',dialog.destroy)
        fields[specifications[0][0]].focus_set()

    research_menu=tk.Menu(root,tearoff=False)
    research_menu.add_command(label='Add manual source',
        command=lambda: research_entry('source'))
    research_menu.add_command(label='Record manual observation',
        command=lambda: research_entry('observation'))
    root_menu.add_cascade(label='Research',menu=research_menu)

    portfolio_button = ttk.Button(buttons,text='Workload (read only)',
                                  command=show_portfolio)
    select_button = ttk.Button(buttons,text='Select matter',command=select_matter)
    refresh_button = ttk.Button(buttons,text='Refresh',command=display_counts)
    review_button = ttk.Button(buttons,text='Record review',command=submit_review)
    task_button = ttk.Button(buttons,text='Complete task',command=submit_task)
    recovery_button = ttk.Button(buttons,text='Recover write',command=recover)
    # Two rows preserve button reachability at the minimum 580px window.
    # Each button stays in tab order; no horizontal scrolling is needed.
    for i, button in enumerate((select_button, refresh_button, review_button,
                                task_button, recovery_button, portfolio_button)):
        button.grid(row=i // 3, column=i % 3, sticky='ew', padx=3, pady=3)
    # Standard Tab and arrow navigation remain intact. Named keyboard
    # shortcuts offer direct access without inventing active web controls.
    ttk.Label(outer, text='Keyboard: Alt+M matter, Alt+R reviews, '
              'Alt+T tasks, Alt+N note, Alt+V record review, '
              'Alt+K complete task, Alt+F refresh, Alt+P workload.',
              wraplength=500).pack(anchor='w')
    matter_list.bind('<<ListboxSelect>>', lambda event: update_controls())
    review_list.bind('<<ListboxSelect>>', lambda event: update_controls())
    task_list.bind('<<ListboxSelect>>', lambda event: update_controls())
    root.bind('<Alt-m>', lambda event: matter_list.focus_set())
    root.bind('<Alt-r>', lambda event: review_list.focus_set())
    root.bind('<Alt-t>', lambda event: task_list.focus_set())
    root.bind('<Alt-n>', lambda event: note.focus_set())
    root.bind('<Alt-v>', lambda event: submit_review()
              if str(review_button.cget('state')) != 'disabled' else None)
    root.bind('<Alt-k>', lambda event: submit_task()
              if str(task_button.cget('state')) != 'disabled' else None)
    root.bind('<Alt-f>', lambda event: display_counts()
              if str(refresh_button.cget('state')) != 'disabled' else None)
    root.bind('<Alt-p>', lambda event: show_portfolio())
    matter_list.bind('<Return>', lambda event: select_matter())
    refresh_lists()
    update_controls()
    if run_mainloop:
        root.mainloop()
    return root


def main():
    parser=argparse.ArgumentParser(description='Offline experimental local attorney graphical operator')
    parser.add_argument('--database',required=True)
    args=parser.parse_args()
    path=Path(args.database)
    if not path.is_file():
        parser.error('Existing experimental SQLite database required')
    # Credentials never accepted through CLI flags or shown in title/status.
    token=getpass('Local bearer token (hidden): ')
    core=SecureCore(path)
    try:
        launch_gui(core,token)
    finally:
        core.close()


if __name__=='__main__':
    main()
