"""Real Tk widget acceptance under an authorized X display; fictional local data.

This is genuine native-window inspection, NOT a human visual/screen-reader
certification. No browser, HTTP listener, network or source-gate bypass.
"""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox
from unittest.mock import patch
import unittest

from src.secure_engine import SecureCore
from src.local_operator_gui import launch_gui


def descendants(widget):
    result = []
    for child in widget.winfo_children():
        result.append(child)
        result.extend(descendants(child))
    return result


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
        self.assertEqual(len(self.texts), 1)
        self.assertEqual(len(self.buttons), 5)

    def select_matter(self):
        self.listboxes[0].selection_set(0)
        self.root.update()
        self.buttons['Select matter'].invoke()
        self.root.update()

    def test_real_widget_layout_focus_and_enabled_actions(self):
        self.open()
        self.assertGreaterEqual(self.root.winfo_width(), 580)
        self.assertGreaterEqual(self.root.winfo_height(), 520)
        self.assertEqual(str(self.buttons['Record review'].cget('state'))), 'disabled')
        self.assertEqual(str(self.buttons['Complete task'].cget('state'))), 'disabled')
        self.assertEqual(str(self.buttons['Recover review'].cget('state'))), 'disabled')
        self.select_matter()
        self.assertEqual(self.listboxes[1].size(), 1)
        self.assertEqual(self.listboxes[2].size(), 1)
        self.listboxes[1].selection_set(0)
        self.root.update()
        self.assertEqual(str(self.buttons['Record review'].cget('state'))), 'normal')
        self.assertEqual(str(self.buttons['Complete task'].cget('state'))), 'disabled')
        self.assertNotIn('PRIVATE FICTITIOUS CASE',
                         ' '.join(w.get(0, 'end')[0] for w in self.listboxes if w.size()))
        self.assertNotIn('SECRET PRIVATE TASK', self.root.title())

    def test_real_confirm_dialog_rejection_has_zero_writes(self):
        self.open()
        self.select_matter()
        self.listboxes[2].selection_set(0)
        self.root.update()
        self.assertEqual(str(self.buttons['Complete task'].cget('state'))), 'normal')
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

    def test_reviewer_viewer_native_action_control_disabled(self):
        self.open(self.viewer)
        self.select_matter()
        self.assertEqual(self.listboxes[1].size(), 0)
        self.assertEqual(self.listboxes[2].size(), 0)
        self.assertEqual(str(self.buttons['Record review'].cget('state'))), 'disabled')
        self.assertEqual(str(self.buttons['Complete task'].cget('state'))), 'disabled')


if __name__ == '__main__':
    unittest.main()
