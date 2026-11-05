"""Real Tk widget acceptance under an authorized X display; fictional local data.

This is genuine native-window inspection, NOT a human visual/screen-reader
certification. No browser, HTTP listener, network or source-gate bypass.
"""
from pathlib import Path
import tempfile
import os
import tkinter as tk
from tkinter import ttk, messagebox
from unittest.mock import patch
import unittest

from src.secure_engine import SecureCore
from src.local_operator_gui import launch_gui, LocalOperatorController, ActionFeedback


def descendants(widget):
    result = []
    for child in widget.winfo_children():
        result.append(child)
        result.extend(descendants(child))
    return result


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Native Tk requires an authorized graphical display')
class NativeTkOperatorAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Fictional Legal Office')
        _, self.author = self.core.provision_user(firm, 'Author')
        reviewer_id, self.reviewer = self.core.provision_user(firm, 'Reviewer')
        viewer_id, self.viewer = self.core.provision_user(firm, 'Reader')
        self.mid = self.core.create_matter(self.author, 'PRIVATE FICTITIOUS CASE')['id']
        self.core.grant(self.author, self.mid, reviewer_id, 'editor', 1)
        self.core.grant(self.author, self.mid, viewer_id, 'viewer', 2)
        task = self.core.create_task(self.author, self.mid, 'SECRET PRIVATE TASK',
                                     '2026-10-01T00:00:00Z')
        from src.attorney_research_workflow import AttorneyResearchWorkflow
        wf = AttorneyResearchWorkflow(self.core)
        eid = wf.evidence.add(self.author, self.mid, 'SECRET SOURCE',
              'https://example.org/fictional', 'SECRET EXCERPT')['id']
        wf.observations.capture(self.author, self.mid, eid, 'SECRET CAPTURE',
                                'Manually checked fictitious authority')
        self.root = None

    def tearDown(self):
        if self.root is not None:
            self.root.destroy()
        self.core.close()
        self.tmp.cleanup()

    def open(self, token=None):
        self.root = launch_gui(self.core, self.reviewer if token is None else token,
                               run_mainloop=False)
        self.root.update()
        self.widgets = descendants(self.root)
        self.buttons = {w.cget('text'): w for w in self.widgets
                        if isinstance(w, ttk.Button)}
        self.listboxes = [w for w in self.widgets if isinstance(w, tk.Listbox)]
        self.texts = [w for w in self.widgets if isinstance(w, tk.Text)]
        self.statuses = [w for w in self.widgets
                         if isinstance(w, ttk.Label)
                         and isinstance(w.cget('textvariable'), str)
                         and w.cget('textvariable')]
        self.assertEqual(len(self.listboxes), 3)
        self.assertEqual(len(self.texts), 2)
        self.assertEqual(len(self.buttons), 6)

    def select_matter(self):
        self.listboxes[0].selection_set(0)
        self.listboxes[0].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.buttons['Select matter'].invoke()
        self.root.update()

    def test_offline_pilot_opens_real_tk_window_after_database_restart(self):
        from src.offline_pilot import initialize_fictional_pilot, open_fictional_pilot
        path=Path(self.tmp.name)/'fresh-pilot.sqlite3'
        credentials=initialize_fictional_pilot(path)
        for attempt in range(2):
            root, opened_core=open_fictional_pilot(
                path,credentials['reviewer_token'],run_mainloop=False)
            try:
                root.update()
                self.assertIn('Local Operator',root.title())
                elements=descendants(root)
                buttons={w.cget('text'):w for w in elements
                         if isinstance(w,ttk.Button)}
                self.assertIn('Workload (read only)',buttons)
                buttons['Workload (read only)'].invoke()
                root.update()
                private=[w.get('1.0','end-1c') for w in elements
                         if isinstance(w,tk.Text)]
                self.assertTrue(any('Open user-entered tasks: 1' in s
                                    for s in private))
                self.assertTrue(all('Fictional Research Matter' not in s
                                    for s in private))
            finally:
                root.destroy()
                opened_core.close()

    def test_real_widget_layout_focus_and_enabled_actions(self):
        self.open()
        self.assertGreaterEqual(self.root.winfo_width(), 580)
        self.assertGreaterEqual(self.root.winfo_height(), 520)
        self.assertEqual(str(self.buttons['Record review'].cget('state')), 'disabled')
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'disabled')
        self.assertEqual(str(self.buttons['Recover write'].cget('state')), 'disabled')
        self.select_matter()
        self.assertEqual(self.listboxes[1].size(), 1)
        self.assertEqual(self.listboxes[2].size(), 1)
        self.listboxes[1].selection_set(0)
        self.listboxes[1].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.assertEqual(str(self.buttons['Record review'].cget('state')), 'normal')
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'disabled')
        self.assertNotIn('PRIVATE FICTITIOUS CASE',
                         ' '.join(w.get(0, 'end')[0] for w in self.listboxes if w.size()))
        self.assertNotIn('SECRET PRIVATE TASK', self.root.title())

    def test_read_only_workload_button_reauthorizes_and_hides_selection(self):
        self.open()
        self.select_matter()
        self.assertEqual(self.listboxes[2].size(), 1)
        self.buttons['Workload (read only)'].invoke()
        self.root.update()
        self.assertEqual(self.listboxes[2].size(), 0)
        self.assertEqual(self.listboxes[1].size(), 0)
        self.assertEqual(self.listboxes[0].size(), 0)
        summary=self.texts[1].get('1.0','end-1c')
        self.assertIn('Open user-entered tasks: 1',summary)
        self.assertIn('PRIVATE ATTORNEY MATTER PORTFOLIO',summary)
        for secret in ('PRIVATE FICTITIOUS CASE','SECRET PRIVATE TASK',
                       'SECRET SOURCE',self.mid,self.reviewer):
            self.assertNotIn(secret,summary)
        self.assertEqual(str(self.buttons['Complete task'].cget('state')),'disabled')
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0],0)
        self.buttons['Refresh'].invoke() if str(self.buttons['Refresh'].cget('state'))!='disabled' else None

    def test_revoked_session_clears_prior_workload_without_leak(self):
        self.open()
        self.buttons['Workload (read only)'].invoke()
        self.assertIn('Open user-entered tasks: 1',self.texts[1].get('1.0','end-1c'))
        self.core.revoke_token(self.reviewer)
        self.buttons['Workload (read only)'].invoke()
        self.root.update()
        self.assertEqual(self.texts[1].get('1.0','end-1c'),'')
        self.assertEqual(self.listboxes[0].size(),0)
        self.assertEqual(self.listboxes[1].size(),0)
        self.assertEqual(self.listboxes[2].size(),0)

    def test_passive_watch_does_not_extend_idle_session(self):
        self.open()
        from hashlib import sha256
        from datetime import datetime, timezone, timedelta
        digest = sha256(self.reviewer.encode()).hexdigest()
        frozen = (datetime.now(timezone.utc) -
                  timedelta(seconds=self.core.IDLE_SECONDS - 30)).isoformat()
        self.core.db.execute(
            'UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
            (frozen, digest))
        self.buttons['Workload (read only)'].invoke()
        # A deliberate workload button is user activity.
        self.core.db.execute(
            'UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
            (frozen, digest))
        self.root.privacy_check()
        stored = self.core.db.execute(
            'SELECT last_seen_at FROM credentials WHERE token_digest=?',
            (digest,)).fetchone()['last_seen_at']
        self.assertEqual(stored, frozen)
        expired = (datetime.now(timezone.utc) -
                   timedelta(seconds=self.core.IDLE_SECONDS + 1)).isoformat()
        self.core.db.execute(
            'UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
            (expired, digest))
        self.root.privacy_check()
        self.assertEqual(self.texts[1].get('1.0', 'end-1c'), '')
        self.assertEqual(self.core.db.execute(
            'SELECT last_seen_at FROM credentials WHERE token_digest=?',
            (digest,)).fetchone()['last_seen_at'], expired)

    def test_idle_revocation_hides_open_portfolio_and_disables_actions(self):
        self.open()
        self.buttons['Workload (read only)'].invoke()
        self.assertIn('Open user-entered tasks: 1',
                      self.texts[1].get('1.0', 'end-1c'))
        self.core.revoke_token(self.reviewer)
        self.root.privacy_check()
        self.assertEqual(self.texts[1].get('1.0', 'end-1c'), '')
        self.assertTrue(all(widget.size() == 0 for widget in self.listboxes))
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'disabled')

    def test_idle_matter_change_clears_previous_counts(self):
        self.open()
        self.buttons['Workload (read only)'].invoke()
        before = self.texts[1].get('1.0', 'end-1c')
        self.core.create_task(self.author, self.mid, 'Fictional additional task',
                              '2026-10-01T00:00:00Z')
        self.root.privacy_check()
        after = self.texts[1].get('1.0', 'end-1c')
        self.assertNotEqual(before, after)
        self.assertIn('Open user-entered tasks: 2', after)
        self.assertNotIn('SECRET PRIVATE TASK', after)

    def test_raised_authorization_error_hides_stale_window_content(self):
        self.open()
        self.buttons['Workload (read only)'].invoke()
        from src.secure_engine import Denied
        with patch.object(self.core, '_identity', side_effect=Denied('revoked')):
            self.root.privacy_check()
        self.assertEqual(self.texts[1].get('1.0', 'end-1c'), '')
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'disabled')

    def test_idle_revocation_removes_uncommitted_private_review_draft(self):
        self.open()
        self.select_matter()
        self.texts[0].insert('1.0', 'CONFIDENTIAL FICTIONAL HUMAN REVIEW DRAFT')
        self.core.revoke_token(self.reviewer)
        self.root.privacy_check()
        self.assertEqual(self.texts[0].get('1.0', 'end-1c'), '')
        self.assertTrue(all(w.size() == 0 for w in self.listboxes))
        self.assertEqual(str(self.buttons['Record review'].cget('state')), 'disabled')

    def test_private_draft_purged_on_portfolio_navigation(self):
        self.open()
        self.select_matter()
        self.texts[0].insert('1.0', 'PRIVATE FICTIONAL DRAFT NEVER SUBMITTED')
        before = self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0]
        self.buttons['Workload (read only)'].invoke()
        self.assertEqual(self.texts[0].get('1.0', 'end-1c'), '')
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0], before)

    def test_hidden_window_draft_purge_keeps_no_write(self):
        self.open()
        self.select_matter()
        self.texts[0].insert('1.0', 'PRIVATE FICTIONAL DRAFT')
        self.root.withdraw()
        self.root.update()
        self.assertEqual(self.texts[0].get('1.0', 'end-1c'), '')
        self.assertTrue(all(w.size() == 0 for w in self.listboxes))
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0], 0)

    def test_revoked_selected_matter_clears_draft_and_actions(self):
        self.open()
        self.select_matter()
        self.texts[0].insert('1.0', 'SECRET PRIVATE REVIEW DRAFT')
        self.core.revoke_token(self.reviewer)
        self.root.privacy_check()
        self.assertEqual(self.texts[0].get('1.0', 'end-1c'), '')
        self.assertTrue(all(box.size() == 0 for box in self.listboxes))
        self.assertEqual(str(self.buttons['Record review'].cget('state')), 'disabled')

    def test_concurrent_task_change_invalidates_selected_action(self):
        self.open()
        self.select_matter()
        self.assertEqual(self.listboxes[2].size(), 1)
        self.texts[0].insert('1.0', 'FICTIONAL UNSENT DRAFT')
        self.core.create_task(self.author, self.mid, 'Second fictional task',
                              '2026-10-01T00:00:00Z')
        self.root.privacy_check()
        self.assertEqual(self.listboxes[2].size(), 0)
        self.assertEqual(self.texts[0].get('1.0', 'end-1c'), '')
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'disabled')

    def test_reselect_matter_never_carries_private_review_note(self):
        self.open()
        self.select_matter()
        self.texts[0].insert('1.0', 'FICTIONAL WRONG MATTER DRAFT')
        self.buttons['Workload (read only)'].invoke()
        self.buttons['Refresh'].invoke() if str(self.buttons['Refresh'].cget('state')) != 'disabled' else None
        # Rebuild authorized list and select again without replaying a write.
        self.root.privacy_check()
        self.assertEqual(self.texts[0].get('1.0', 'end-1c'), '')
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0], 0)

    def test_alt_p_keyboard_shortcut_opens_portfolio(self):
        self.open()
        self.root.focus_force()
        self.root.update()
        self.root.event_generate('<Alt-p>')
        self.root.update()
        self.assertIn('PRIVATE ATTORNEY MATTER PORTFOLIO',
                      self.texts[1].get('1.0','end-1c'))
        self.assertEqual(self.root.focus_get(),self.texts[1])

    def test_task_confirm_revocation_during_modal_has_no_write(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        def revoke(*args, **kwargs):
            self.core.revoke_token(self.reviewer)
            self.root.privacy_check()
            return True
        with patch.object(messagebox, 'askyesno', side_effect=revoke):
            self.buttons['Complete task'].invoke()
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0], 0)
        self.assertEqual(self.listboxes[2].size(), 0)

    def test_review_confirm_changed_decision_during_modal_has_no_write(self):
        self.open()
        self.select_matter()
        self.listboxes[1].selection_set(0)
        self.listboxes[1].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.texts[0].insert('1.0', 'Fictional reviewed legal source carefully')
        decisions = [w for w in self.widgets if isinstance(w, ttk.Combobox)]
        self.assertEqual(len(decisions), 1)
        def change_decision(*args, **kwargs):
            decisions[0].set('rejected')
            return True
        with patch.object(messagebox, 'askyesno', side_effect=change_decision):
            self.buttons['Record review'].invoke()
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0], 0)

    def test_task_confirm_selection_removed_during_modal_has_no_write(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        def alter(*args, **kwargs):
            self.listboxes[2].selection_clear(0, 'end')
            return True
        with patch.object(messagebox, 'askyesno', side_effect=alter):
            self.buttons['Complete task'].invoke()
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0], 0)

    def test_nested_task_confirmation_cannot_open_second_confirmation(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        counter = []
        def nested(*args, **kwargs):
            counter.append('first')
            self.buttons['Complete task'].invoke()
            return False
        with patch.object(messagebox, 'askyesno', side_effect=nested):
            self.buttons['Complete task'].invoke()
        self.assertEqual(counter, ['first'])
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0], 0)

    def test_review_confirmation_blocks_nested_task_confirmation(self):
        self.open()
        self.select_matter()
        self.listboxes[1].selection_set(0)
        self.listboxes[1].event_generate('<<ListboxSelect>>')
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.texts[0].insert('1.0', 'Fictional reviewer note for testing only')
        count = []
        def nested(*args, **kwargs):
            count.append('review')
            self.buttons['Complete task'].invoke()
            return False
        with patch.object(messagebox, 'askyesno', side_effect=nested):
            self.buttons['Record review'].invoke()
        self.assertEqual(count, ['review'])
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0], 0)
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0], 0)

    def test_native_task_completion_shows_fresh_private_workload(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        with patch.object(messagebox,'askyesno',return_value=True):
            self.buttons['Complete task'].invoke()
        self.root.update()
        summary=self.texts[1].get('1.0','end-1c')
        self.assertIn('PRIVATE ATTORNEY MATTER PORTFOLIO',summary)
        self.assertIn('Open user-entered tasks: 0',summary)
        for secret in ('PRIVATE FICTITIOUS CASE','SECRET PRIVATE TASK',
                       'SECRET SOURCE','SECRET EXCERPT',self.mid,self.reviewer):
            self.assertNotIn(secret,summary)
        self.assertEqual(self.listboxes[2].size(),0)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0],1)

    def test_native_failed_postcommit_workload_read_clears_private_ui(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        with (
            patch.object(messagebox,'askyesno',return_value=True),
            patch.object(LocalOperatorController,'read_only_current_workload',
                         side_effect=RuntimeError('fictional display failure')),
            patch.object(messagebox,'showwarning') as warning,
        ):
            self.buttons['Complete task'].invoke()
        self.root.update()
        self.assertEqual(warning.call_count,1)
        self.assertEqual(self.texts[1].get('1.0','end-1c'),'')
        self.assertEqual(self.listboxes[2].size(),0)
        self.assertEqual(self.listboxes[1].size(),0)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0],1)

    def test_native_uncertain_completion_stays_write_fenced_after_refresh(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        controller=self.root.controller if hasattr(self.root,'controller') else None
        # The GUI uses actual SecureCore plus LocalOperatorController; inject
        # only the post-commit presentation failure.
        original=LocalOperatorController.refresh
        times=[0]
        def fail_once(instance):
            times[0]+=1
            if times[0] == 1:
                raise RuntimeError('synthetic postcommit GUI refresh loss')
            return original(instance)
        with (patch.object(messagebox,'askyesno',return_value=True),
              patch.object(messagebox,'showwarning'),
              patch.object(LocalOperatorController,'refresh',fail_once)):
            self.buttons['Complete task'].invoke()
        self.root.update()
        self.assertEqual(self.listboxes[2].size(),0)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0],1)
        self.buttons['Refresh'].invoke() if str(self.buttons['Refresh'].cget('state')) != 'disabled' else None
        self.root.update()
        self.assertEqual(self.listboxes[2].size(),0)
        self.assertEqual(str(self.buttons['Complete task'].cget('state')),'disabled')
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0],1)

    def test_native_end_to_end_review_completion_private_workload(self):
        self.open()
        self.select_matter()
        self.assertEqual(self.listboxes[1].size(),1)
        self.assertEqual(self.listboxes[2].size(),1)
        self.listboxes[1].selection_set(0)
        self.listboxes[1].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.texts[0].insert('1.0',
            'Independent human reviewed fictional source and observation')
        with patch.object(messagebox,'askyesno',return_value=True) as consent:
            self.buttons['Record review'].invoke()
        self.root.update()
        self.assertEqual(consent.call_count,1)
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0],1)
        self.assertEqual(self.listboxes[1].size(),0)
        self.assertEqual(self.listboxes[2].size(),1)
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        with patch.object(messagebox,'askyesno',return_value=True) as consent:
            self.buttons['Complete task'].invoke()
        self.root.update()
        self.assertEqual(consent.call_count,1)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0],1)
        self.assertEqual(self.listboxes[2].size(),0)
        summary=self.texts[1].get('1.0','end-1c')
        self.assertIn('Open user-entered tasks: 0',summary)
        self.assertIn('Second-human reviews waiting: 0',summary)
        for secret in ('PRIVATE FICTITIOUS CASE','SECRET PRIVATE TASK',
                       'SECRET SOURCE','SECRET EXCERPT',self.mid,self.reviewer):
            self.assertNotIn(secret,summary)
        self.assertTrue(self.core.verify_audit())

    def test_real_confirm_dialog_rejection_has_zero_writes(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'normal')
        with patch.object(messagebox, 'askyesno', return_value=False) as ask:
            self.buttons['Complete task'].invoke()
        self.assertEqual(ask.call_count, 1)
        row = self.core.db.execute('SELECT count(*) FROM tasks WHERE completed=1').fetchone()
        self.assertEqual(row[0], 0)

    def test_real_keyboard_focus_and_selection(self):
        self.open()
        self.root.focus_force()
        self.root.update()
        self.listboxes[0].selection_set(0)
        self.root.update()
        self.root.event_generate('<Alt-m>')
        self.root.update()
        self.assertEqual(self.root.focus_get(), self.listboxes[0])
        self.listboxes[0].event_generate('<Return>')
        self.root.update()
        self.assertEqual(self.listboxes[2].size(), 1)
        self.root.event_generate('<Alt-n>')
        self.root.update()
        self.assertEqual(self.root.focus_get(), self.texts[0])

    def test_minimum_and_wide_window_keep_all_actions_inside_view(self):
        self.open()
        for width, height in ((580, 520), (760, 650), (1024, 768)):
            with self.subTest(window=(width, height)):
                self.root.geometry(f'{width}x{height}+0+0')
                self.root.update()
                available = self.root.winfo_width()
                self.assertGreaterEqual(available, width)
                for label, button in self.buttons.items():
                    self.assertTrue(button.winfo_ismapped(), label)
                    self.assertGreaterEqual(button.winfo_rootx(),
                                            self.root.winfo_rootx(), label)
                    self.assertLessEqual(
                        button.winfo_rootx() + button.winfo_width(),
                        self.root.winfo_rootx() + available, label)
                    self.assertGreaterEqual(button.winfo_width(), 70, label)
                    # A mapped button may still lie below the clipped window:
                    # inspect vertical screen coordinates, not just mapped state.
                    self.assertGreaterEqual(button.winfo_rooty(),
                                            self.root.winfo_rooty(), label)
                    self.assertLessEqual(
                        button.winfo_rooty() + button.winfo_height(),
                        self.root.winfo_rooty() + self.root.winfo_height(), label)
                for widget in self.widgets:
                    if isinstance(widget, ttk.Label) and (
                        'EXPERIMENTAL WORKFLOW' in str(widget.cget('text')) or
                        'Keyboard:' in str(widget.cget('text'))
                    ):
                        self.assertLessEqual(
                            widget.winfo_rooty() + widget.winfo_height(),
                            self.root.winfo_rooty() + self.root.winfo_height())
                        self.assertLessEqual(
                            widget.winfo_rootx() + widget.winfo_width(),
                            self.root.winfo_rootx() + self.root.winfo_width())

    def test_native_confidentiality_and_no_raw_case_text(self):
        self.open()
        self.select_matter()
        visible = [self.root.title()]
        for widget in self.widgets:
            if isinstance(widget, (ttk.Label, ttk.Button)):
                visible.append(str(widget.cget('text')))
            elif isinstance(widget, tk.Listbox):
                visible.extend(widget.get(0, 'end'))
        flat = ' '.join(visible)
        for secret in ('PRIVATE FICTITIOUS CASE', 'SECRET PRIVATE TASK',
                       'SECRET SOURCE', 'SECRET EXCERPT',
                       self.mid, self.reviewer):
            self.assertNotIn(secret, flat)
        self.assertIn('OFFLINE EXPERIMENTAL WORKFLOW', flat)

    def test_revocation_during_native_confirm_denies_without_write(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'normal')
        def revoke_on_confirm(*args, **kwargs):
            self.core.revoke_token(self.reviewer)
            return True
        with patch.object(messagebox, 'askyesno', side_effect=revoke_on_confirm):
            self.buttons['Complete task'].invoke()
        completed = self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0]
        self.assertEqual(completed, 0)
        self.assertEqual(self.listboxes[1].size(), 0)
        self.assertEqual(self.listboxes[2].size(), 0)
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'disabled')

    def test_native_modal_warns_after_uncertain_committed_operation(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        # The controller's actual write/recovery is covered by separate
        # real SecureCore tests; this verifies the real Tk modal presentation.
        with (
            patch.object(messagebox, 'askyesno', return_value=True),
            patch.object(LocalOperatorController, 'complete',
                         return_value=ActionFeedback(
                             'committed_refresh_unresolved',
                             'Task committed; display refresh unresolved. Do NOT repeat.')),
            patch.object(messagebox, 'showwarning') as warning,
        ):
            self.buttons['Complete task'].invoke()
        self.assertEqual(warning.call_count, 1)
        self.assertIn('Do not repeat', warning.call_args.args[1])
        self.assertEqual(self.listboxes[2].size(), 0)
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'disabled')

    def test_invalid_review_note_focuses_input_before_any_confirm(self):
        self.open()
        self.select_matter()
        self.listboxes[1].selection_set(0)
        self.listboxes[1].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.assertEqual(str(self.buttons['Record review'].cget('state')), 'normal')
        with patch.object(messagebox, 'askyesno') as confirm:
            self.buttons['Record review'].invoke()
        confirm.assert_not_called()
        self.assertEqual(self.root.focus_get(), self.texts[0])
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0], 0)

    def test_keyboard_only_review_requires_user_confirmation(self):
        self.open()
        self.select_matter()
        self.listboxes[1].selection_set(0)
        self.listboxes[1].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.texts[0].insert('1.0', 'Human reviewer checked fictional evidence manually')
        self.root.focus_force()
        self.root.update()
        with patch.object(messagebox, 'askyesno', return_value=False) as confirm:
            self.root.event_generate('<Alt-v>')
            self.root.update()
        self.assertEqual(confirm.call_count, 1)
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0], 0)

    def test_keyboard_only_task_shortcut_requires_user_confirmation(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.listboxes[2].event_generate('<<ListboxSelect>>')
        self.root.update()
        self.root.focus_force()
        self.root.update()
        with patch.object(messagebox, 'askyesno', return_value=False) as confirm:
            self.root.event_generate('<Alt-k>')
            self.root.update()
        self.assertEqual(confirm.call_count, 1)
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0], 0)

    def test_reviewer_viewer_native_action_control_disabled(self):
        self.open(self.viewer)
        self.select_matter()
        self.assertEqual(self.listboxes[1].size(), 0)
        self.assertEqual(self.listboxes[2].size(), 0)
        self.assertEqual(str(self.buttons['Record review'].cget('state')), 'disabled')
        self.assertEqual(str(self.buttons['Complete task'].cget('state')), 'disabled')


if __name__ == '__main__':
    unittest.main()
