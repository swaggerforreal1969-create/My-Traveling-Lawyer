"""End-to-end local operator action against real SecureCore and readiness. Fictional only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest
from src.secure_engine import SecureCore, Denied, Invalid
from src.attorney_research_workflow import AttorneyResearchWorkflow


class OperatorActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.temp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Fictional Legal Practice')
        self.owner, self.token = self.core.provision_user(firm, 'Fictional Lawyer')
        self.viewer_id, self.viewer = self.core.provision_user(firm, 'Fictional Viewer')
        other_firm = self.core.provision_firm('Unrelated Fictional Practice')
        _, self.other = self.core.provision_user(other_firm, 'Outsider')
        self.mid = self.core.create_matter(self.token, 'PRIVATE FICTIONAL MATTER')['id']
        self.core.grant(self.token, self.mid, self.viewer_id, 'viewer', 1)
        self.task = self.core.create_task(self.token, self.mid, 'SECRET TASK BODY',
                                          '2026-10-01T00:00:00+00:00')
        self.workflow = AttorneyResearchWorkflow(self.core)
        self.now = datetime(2026, 11, 3, tzinfo=timezone.utc)

    def tearDown(self):
        self.core.close()
        self.temp.cleanup()

    def act(self, token=None, matter=None, task=None, version=1):
        return self.workflow.complete_if_ready(
            self.token if token is None else token,
            self.mid if matter is None else matter,
            self.task['id'] if task is None else task,
            version, now=self.now)

    def audit_completions(self):
        return self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0]

    def test_completed_and_private_refreshed_readiness(self):
        outcome = self.act()
        self.assertEqual(outcome.status, 'completed_and_refreshed')
        self.assertEqual(outcome.snapshot.workbench['open_tasks'], [])
        self.assertIn(b'Open tasks</span><strong>0', outcome.snapshot.readiness_html)
        for secret in (b'PRIVATE FICTIONAL MATTER', b'SECRET TASK BODY',
                       self.mid.encode(), self.task['id'].encode()):
            self.assertNotIn(secret, outcome.snapshot.readiness_html)
        self.assertFalse(outcome.legal_deadlines_verified)
        self.assertFalse(outcome.court_filing_approved)
        self.assertFalse(outcome.independent_audit_verified)
        self.assertEqual(self.audit_completions(), 1)
        self.assertTrue(self.core.verify_audit())

    def test_repeated_submission_reports_observed_not_repeat_write(self):
        self.assertEqual(self.act().status, 'completed_and_refreshed')
        second = self.act()
        self.assertEqual(second.status, 'observed_completed_no_write')
        self.assertIsNone(second.snapshot)
        self.assertEqual(self.audit_completions(), 1)

    def test_stale_expected_version_fails_without_write(self):
        result = self.act(version=2)
        self.assertEqual(result.status, 'unresolved_no_write')
        self.assertIsNone(result.snapshot)
        self.assertEqual(self.audit_completions(), 0)

    def test_viewer_outsider_wrong_matter_and_revocation_denied(self):
        with self.assertRaises(Denied): self.act(token=self.viewer)
        with self.assertRaises(Denied): self.act(token=self.other)
        other = self.core.create_matter(self.token, 'Second fictional case')['id']
        with self.assertRaises(Denied): self.act(matter=other)
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied): self.act()
        self.assertEqual(self.audit_completions(), 0)

    def test_committed_refresh_failure_yields_no_retry_status(self):
        with patch.object(self.workflow, 'open',
                          side_effect=RuntimeError('Fictional read failure')):
            result = self.act()
        self.assertEqual(result.status, 'committed_refresh_unresolved')
        self.assertIsNone(result.snapshot)
        self.assertEqual(self.audit_completions(), 1)
        self.assertEqual(self.act().status, 'observed_completed_no_write')
        self.assertEqual(self.audit_completions(), 1)

    def test_tampered_audit_and_task_state_fail_closed(self):
        self.core.db.execute('UPDATE tasks SET completed=1,version=2 WHERE id=?',
                             (self.task['id'],))
        with self.assertRaises(Invalid): self.act()
        self.core.db.execute('UPDATE tasks SET completed=0,version=1 WHERE id=?',
                             (self.task['id'],))
        self.core.db.execute("UPDATE audit_chain SET row_hash='forged' WHERE seq=1")
        with self.assertRaises(Invalid): self.act()
        self.assertEqual(self.audit_completions(), 0)

    def test_two_simultaneous_operator_actions_commit_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: self.act().status, range(2)))
        self.assertCountEqual(
            statuses, ['completed_and_refreshed', 'observed_completed_no_write'])
        self.assertEqual(self.audit_completions(), 1)
        self.assertTrue(self.core.verify_audit())

    def test_preflight_is_not_one_time_credential(self):
        prior = self.workflow.completion_preflight(
            self.token, self.mid, self.task['id'], 1)
        self.assertTrue(prior.can_attempt_completion)
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied): self.act()
        self.assertEqual(self.audit_completions(), 0)


if __name__ == '__main__':
    unittest.main()
