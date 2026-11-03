"""Read-only uncertain-task recovery with real local authenticated core; fictional only."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from pathlib import Path
from src.secure_engine import SecureCore, Denied, Invalid, Stale
from src.task_reconciliation import reconcile_task


class TaskReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        self.firm = self.core.provision_firm('Fictional Firm')
        self.owner, self.token = self.core.provision_user(self.firm, 'Fictional Counsel')
        self.viewer, self.view_token = self.core.provision_user(self.firm, 'Read Only')
        self.other_firm = self.core.provision_firm('Unrelated Fictional Firm')
        _, self.other_token = self.core.provision_user(self.other_firm, 'Outsider')
        self.mid = self.core.create_matter(self.token, 'Fictional Matter')['id']
        self.core.grant(self.token, self.mid, self.viewer, 'viewer', 1)
        self.task = self.core.create_task(self.token, self.mid, 'Fictional task',
                                          '2026-10-01T00:00:00+00:00')
        self.tid = self.task['id']

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def observe(self, token=None, matter_id=None, task_id=None, version=1):
        return reconcile_task(self.core, token or self.token, matter_id or self.mid,
                              task_id or self.tid, version)

    def test_pre_commit_open_and_no_writes(self):
        before = self.core.db.execute('SELECT count(*) FROM audit_chain').fetchone()[0]
        out = self.observe()
        self.assertEqual((out.status, out.observed_version), ('still_open', 1))
        self.assertFalse(out.legal_deadlines_verified)
        self.assertFalse(out.court_filing_approved)
        self.assertFalse(out.independent_audit_verified)
        self.assertEqual(self.core.db.execute('SELECT count(*) FROM audit_chain').fetchone()[0], before)

    def test_post_commit_observation_does_not_replay(self):
        self.core.complete_task(self.token, self.tid, 1)
        before = self.core.db.execute("SELECT count(*) FROM audit_chain WHERE action='task.complete'").fetchone()[0]
        self.assertEqual(self.observe().status, 'observed_completed')
        self.assertEqual(self.observe().status, 'observed_completed')
        self.assertEqual(self.core.db.execute("SELECT count(*) FROM audit_chain WHERE action='task.complete'").fetchone()[0], before)
        with self.assertRaises(Stale):
            self.core.complete_task(self.token, self.tid, 1)

    def test_viewer_can_reconcile_but_cannot_complete(self):
        self.assertEqual(self.observe(self.view_token).status, 'still_open')
        with self.assertRaises(Denied):
            self.core.complete_task(self.view_token, self.tid, 1)

    def test_cross_firm_wrong_matter_and_revoked_denied(self):
        with self.assertRaises(Denied):
            self.observe(self.other_token)
        second = self.core.create_matter(self.token, 'Another matter')['id']
        with self.assertRaises(Denied):
            self.observe(matter_id=second)
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):
            self.observe()

    def test_unresolved_version_and_corrupt_state(self):
        self.assertEqual(self.observe(version=2).status, 'unresolved')
        self.core.db.execute('UPDATE tasks SET version=4 WHERE id=?', (self.tid,))
        self.assertEqual(self.observe().status, 'unresolved')
        self.core.db.execute('UPDATE tasks SET completed=7 WHERE id=?', (self.tid,))
        with self.assertRaises(Invalid):
            self.observe()

    def test_tampered_local_audit_fails_closed(self):
        self.core.db.execute('UPDATE audit_chain SET row_hash=? WHERE seq=1', ('0'*64,))
        with self.assertRaises(Invalid):
            self.observe()

    def test_concurrent_writers_one_completion_and_consistent_reconciliation(self):
        barrier = Barrier(2)
        def attempt(_):
            barrier.wait(timeout=5)
            try:
                self.core.complete_task(self.token, self.tid, 1)
                return 'committed'
            except Stale:
                return 'stale'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, range(2)))
        self.assertCountEqual(outcomes, ['committed', 'stale'])
        self.assertEqual(self.observe().status, 'observed_completed')
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0], 1)
        self.assertTrue(self.core.verify_audit())

    def test_no_bool_versions(self):
        with self.assertRaises(Invalid):
            self.observe(version=True)


if __name__ == '__main__':
    unittest.main()
