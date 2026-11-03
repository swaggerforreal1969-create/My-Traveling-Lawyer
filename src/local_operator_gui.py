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


@dataclass(frozen=True)
class ActionFeedback:
    """Safe UI-facing feedback; custody IDs remain inside the controller."""
    status: str
    message: str


class LocalOperatorController:
    """UI-independent state boundary; no credentials sent to a web client."""

    def __init__(self, core, token):
        self.operator = PrivateAttorneyOperator(core)
        self._token = token
        self._matter_id = None
        self._matters = ()
        self._tasks = ()
        self._reviews = ()
        self._recovery = None

    def _clear(self):
        self._matter_id = None
        self._tasks = ()
        self._reviews = ()
        self._recovery = None

    def list_matters(self):
        self._clear()
        index = self.operator.matters(self._token)
        self._matters = tuple(item['matter_id'] for item in index['matters'])
        return len(self._matters)

    def select(self, position):
        self._clear()
        if type(position) is not int or not 0 <= position < len(self._matters):
            raise Invalid('Invalid matter selection')
        mid = self._matters[position]
        screen = self.operator.select_matter(self._token, mid)
        self._matter_id = mid
        self._load_authorized_work()
        return screen

    def _load_authorized_work(self):
        if self._matter_id is None:
            raise Invalid('Matter not selected')
        mid = self._matter_id
        # Each operation freshly authenticates through SecureCore.
        screen = self.operator.select_matter(self._token, mid)
        if screen.can_complete_tasks:
            view = self.operator.workflow.journey.workbench.matter(self._token, mid)
            self._tasks = tuple((item['task_id'], item['version'])
                                for item in view['open_tasks'])
            queue = self.operator.reviewer_inbox(self._token, mid)
            self._reviews = tuple((item['evidence_id'], item['observation_id'])
                                  for item in queue['items'])
        else:
            self._tasks = ()
            self._reviews = ()
        return screen

    def refresh(self):
        return self._load_authorized_work()

    def counts(self):
        return (len(self._tasks), len(self._reviews))

    def has_recovery(self):
        return self._recovery is not None

    def review(self, position, decision, note, confirmed):
        if not confirmed:
            return ActionFeedback('cancelled', 'Cancelled; no write performed.')
        if type(position) is not int or not 0 <= position < len(self._reviews):
            raise Invalid('Invalid review selection')
        if decision not in ('corroborated_manually', 'needs_further_review', 'rejected'):
            raise Invalid('Invalid review decision')
        if not isinstance(note, str) or not 15 <= len(note.strip()) <= 1200:
            raise Invalid('Human review note must be 15–1200 characters')
        eid, oid = self._reviews[position]
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
        if type(position) is not int or not 0 <= position < len(self._tasks):
            raise Invalid('Invalid task selection')
        task_id, version = self._tasks[position]
        self._recovery = None
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

    def reconcile_last_review(self):
        if self._recovery is None or self._matter_id is None:
            raise Invalid('No uncertain review to reconcile')
        operation, record_id = self._recovery
        result = self.operator.reconcile_research(
            self._token, self._matter_id, operation, record_id)
        self._recovery = None
        self.refresh()
        return ActionFeedback('observed_local_commit',
                              'Local review commit observed; independent custody not verified.')


def launch_gui(core, token, *, run_mainloop=True):
    """Real Tk controls. Disabled write buttons until a current row selected."""
    import tkinter as tk
    from tkinter import ttk, messagebox
    controller = LocalOperatorController(core, token)
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

    def refresh_lists():
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
            matter_list.delete(0,'end')
        update_controls()

    def select_matter():
        if not matter_list.curselection():
            return
        try:
            controller.select(matter_list.curselection()[0])
            display_counts()
        except (Denied, Invalid, Stale, EvidenceInvalid):
            status.set('Matter access denied. Reauthenticate before continuing.')
            review_list.delete(0,'end')
            task_list.delete(0,'end')
        update_controls()

    def display_counts():
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
            clear_stale_actions()
        update_controls()

    def clear_stale_actions():
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

    def submit_review():
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
        if not messagebox.askyesno('Confirm second-human review',
                                   'Record this one review? No automatic retry.'):
            status.set('Cancelled; no write performed.')
            return
        try:
            result=controller.review(review_list.curselection()[0], choice.get(),
                                     human_note, True)
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

    def submit_task():
        if not task_list.curselection(): return
        if not messagebox.askyesno('Confirm task completion',
                                   'Complete this one task? No automatic retry.'):
            status.set('Cancelled; no write performed.')
            return
        try:
            result=controller.complete(task_list.curselection()[0], True)
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

    def recover():
        try:
            result=controller.reconcile_last_review()
            display_counts()
            status.set(result.message)
            update_controls()
        except (Denied, Invalid, Stale, EvidenceInvalid):
            status.set('Read-only recovery unresolved. Do NOT repeat the write.')
            update_controls()

    select_button = ttk.Button(buttons,text='Select matter',command=select_matter)
    refresh_button = ttk.Button(buttons,text='Refresh',command=display_counts)
    review_button = ttk.Button(buttons,text='Record review',command=submit_review)
    task_button = ttk.Button(buttons,text='Complete task',command=submit_task)
    recovery_button = ttk.Button(buttons,text='Recover review',command=recover)
    # Two rows preserve button reachability at the minimum 580px window.
    # Each button stays in tab order; no horizontal scrolling is needed.
    for i, button in enumerate((select_button, refresh_button, review_button,
                                task_button, recovery_button)):
        button.grid(row=i // 3, column=i % 3, sticky='ew', padx=3, pady=3)
    # Standard Tab and arrow navigation remain intact. Named keyboard
    # shortcuts offer direct access without inventing active web controls.
    ttk.Label(outer, text='Keyboard: Alt+M matter, Alt+R reviews, '
              'Alt+T tasks, Alt+N note, Alt+V record review, '
              'Alt+K complete task, Alt+F refresh.',
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
