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

    def _assert_no_uncertain_review(self):
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
        if self._recovery is not None:
            raise Invalid('Reconcile the current review before switching matters')
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
        if (self._recovery is not None or
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
        if self._recovery is None:
            self._matter_id = None
            self._matters = ()
        return self.operator.portfolio_summary(self._token)

    def has_recovery(self):
        return (self._recovery is not None or (
            self._durable_fence is not None and self._matter_id is not None
            and self._durable_fence.is_pending()))

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
        if self._durable_fence is not None:
            self._durable_fence.finish_confirmed(
                expected_reservation=self._reservation)
            self._reservation = None
        try:
            self.refresh()
        except Exception:
            # The delegated operation committed. A later presentation read
            # must not turn success into an apparent failed write. Preserve the
            # exact record for one optional actor-authorized read-only check.
            self._recovery = ('source.second_review', committed.record_id)
            self._tasks, self._reviews = (), ()
            return ActionFeedback(
                'committed_refresh_unresolved',
                'Review committed, display refresh unresolved. Do NOT repeat.')
        return ActionFeedback('review_committed', 'Review recorded. Readiness refreshed.')

    def complete(self, position, confirmed):
        if not confirmed:
            return ActionFeedback('cancelled', 'Cancelled; no write performed.')
        self._assert_no_uncertain_review()
        if type(position) is not int or not 0 <= position < len(self._tasks):
            raise Invalid('Invalid task selection')
        task_id, version = self._tasks[position]
        if self._durable_fence is not None:
            self._reservation = self._durable_fence.begin()  # before write
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
            self._tasks, self._reviews = (), ()
            return ActionFeedback(result.status, allowed[result.status])
        if self._durable_fence is not None:
            self._durable_fence.finish_confirmed(
                expected_reservation=self._reservation)
            self._reservation = None
        try:
            self.refresh()
        except Exception:
            self._tasks, self._reviews = (), ()
            if result.status == 'completed_and_refreshed':
                return ActionFeedback(
                    'committed_refresh_unresolved',
                    'Task committed; display refresh unresolved. Do NOT repeat.')
            return ActionFeedback('unresolved_no_write',
                                  'Read-only state refresh unresolved; no new write.')
        return ActionFeedback(result.status, allowed[result.status])

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
    root.title('Private Attorney — Local Operator')
    root.geometry('760x650')
    root.minsize(580, 520)
    outer = ttk.Frame(root, padding=14)
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
    portfolio_text = tk.Text(portfolio_panel, height=3, wrap='word',
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

    def privacy_tick():
        if not root.winfo_exists():
            return
        privacy_check()
        root.after(2000, privacy_tick)

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
    root.after(2000, privacy_tick)

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
                note.focus_set()
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
                if result.status != 'committed_refresh_unresolved':
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

    portfolio_button = ttk.Button(buttons,text='Workload (read only)',
                                  command=show_portfolio)
    select_button = ttk.Button(buttons,text='Select matter',command=select_matter)
    refresh_button = ttk.Button(buttons,text='Refresh',command=display_counts)
    review_button = ttk.Button(buttons,text='Record review',command=submit_review)
    task_button = ttk.Button(buttons,text='Complete task',command=submit_task)
    recovery_button = ttk.Button(buttons,text='Recover review',command=recover)
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
