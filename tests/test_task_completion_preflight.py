"""Real SecureCore adversarial checks for confidential preflight; fictional data."""
import tempfile
import unittest
from pathlib import Path
from src.secure_engine import SecureCore, Denied, Invalid, Stale
from src.task_completion_preflight import prepare_completion


class CompletionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Fictional Legal Group')
        self.owner, self.token = self.core.provision_user(firm, 'Fictional Attorney')
        self.viewer, self.viewer_token = self.core.provision_user(firm, 'Viewer')
        self.editor, self.editor_token = self.core.provision_user(firm, 'Editor')
        other = self.core.provision_firm('Outside Fictional Firm')
        _, self.outsider = self.core.provision_user(other, 'Outsider')
        self.mid = self.core.create_matter(self.token, 'SECRET MATTER NAME')['id']
        self.core.grant(self.token, self.mid, self.viewer, 'viewer', 1)
        self.core.grant(self.token, self.mid, self.editor, 'editor', 2)
        self.task = self.core.create_task(self.token, self.mid, 'SECRET TASK TEXT',
                                           '2026-10-01T00:00:00+00:00')
        self.tid = self.task['id']

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def preflight(self, token=None, matter=None, task=None, version=1):
        return prepare_completion(self.core, self.token if token is None else token,
                                  self.mid if matter is None else matter,
                                  self.tid if task is None else task, version)

    def test_ready_with_minimal_output_and_no_task_write(self):
        before = self.core.db.execute("SELECT count(*) FROM audit_chain").fetchone()[0]
        result = self.preflight()
        self.assertEqual((result.status, result.observed_version,
                          result.can_attempt_completion), ('ready_to_attempt', 1, True))
        self.assertFalse(result.legal_deadlines_verified)
        self.assertFalse(result.court_filing_approved)
        self.assertFalse(result.official_law_verified)
        self.assertNotIn('SECRET', repr(result))
        self.assertNotIn(self.tid, repr(result))
        self.assertEqual(before, self.core.db.execute(
            "SELECT count(*) FROM audit_chain").fetchone()[0])

    def test_editor_ready_viewer_denied(self):
        self.assertTrue(self.preflight(self.editor_token).can_attempt_completion)
        with self.assertRaises(Denied):
            self.preflight(self.viewer_token)

    def test_completion_then_preflight_cannot_authorize_replay(self):
        self.assertTrue(self.preflight().can_attempt_completion)
        self.core.complete_task(self.token, self.tid, 1)
        after = self.preflight()
        self.assertEqual(after.status, 'already_completed')
        self.assertFalse(after.can_attempt_completion)
        with self.assertRaises(Stale):
            self.core.complete_task(self.token, self.tid, 1)

    def test_wrong_matter_cross_firm_and_revoked_denied(self):
        second = self.core.create_matter(self.token, 'Unrelated private matter')['id']
        with self.assertRaises(Denied): self.preflight(matter=second)
        with self.assertRaises(Denied): self.preflight(self.outsider)
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied): self.preflight()

    def test_bad_version_and_stale_state_are_not_actionable(self):
        with self.assertRaises(Invalid): self.preflight(version=True)
        with self.assertRaises(Invalid): self.preflight(version=0)
        stale = self.preflight(version=2)
        self.assertEqual(stale.status, 'unresolved')
        self.assertFalse(stale.can_attempt_completion)

    def test_tampered_state_and_local_audit_fail_closed(self):
        self.core.db.execute('UPDATE tasks SET completed=1,version=2 WHERE id=?',
                             (self.tid,))
        with self.assertRaises(Invalid): self.preflight()
        self.core.db.execute('UPDATE tasks SET completed=0,version=1 WHERE id=?',
                             (self.tid,))
        self.core.db.execute("UPDATE audit_chain SET row_hash='BAD' WHERE seq=1")
        with self.assertRaises(Invalid): self.preflight()


if __name__ == '__main__':
    unittest.main()
