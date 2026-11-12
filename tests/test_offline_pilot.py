"""End-to-end offline fictional pilot lifecycle using real SQLite/SecureCore.

No mocked research source, no browser, no network server or real client data.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest

from src.offline_pilot import initialize_fictional_pilot, open_fictional_pilot, inspect_fictional_pilot, main
from src.secure_engine import SecureCore, Denied
from src.durable_local_write_fence import LocalWriteFence
from src.local_operator_gui import LocalOperatorController


class OfflinePilotLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fictional-pilot.sqlite3'

    def tearDown(self):
        self.tmp.cleanup()

    def initialize(self):
        return initialize_fictional_pilot(self.path)

    def test_new_pilot_contains_real_authorized_research_and_task(self):
        credentials = self.initialize()
        self.assertTrue(self.path.is_file())
        self.assertTrue(LocalWriteFence(self.path).path.is_file())
        with _closing_core(self.path) as core:
            editor = LocalOperatorController(
                core, credentials['editor_token'],
                durable_fence=LocalWriteFence(self.path))
            self.assertEqual(editor.list_matters(), 1)
            editor.select(0)
            # An evidence author cannot serve as their own second-human reviewer.
            self.assertEqual(editor.counts(), (1, 0))
            reviewer = LocalOperatorController(
                core, credentials['reviewer_token'],
                durable_fence=LocalWriteFence(self.path))
            self.assertEqual(reviewer.list_matters(), 1)
            reviewer.select(0)
            self.assertEqual(reviewer.counts(), (1, 1))
            self.assertTrue(core.verify_audit())
        if os.name == 'posix':
            self.assertEqual(self.path.stat().st_mode & 0o077, 0)
            self.assertEqual(LocalWriteFence(self.path).path.stat().st_mode & 0o077, 0)

    def test_reinitialize_refuses_overwrite_and_preserves_original_bytes(self):
        original = self.initialize()
        before = self.path.read_bytes()
        with self.assertRaises(Denied):
            self.initialize()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(original['database'], self.path)

    def test_missing_parent_and_existing_symlink_denied(self):
        with self.assertRaises(Denied):
            initialize_fictional_pilot(self.path.parent / 'absent' / 'pilot.db')
        if hasattr(os, 'symlink'):
            other = self.path.parent / 'existing.txt'
            other.write_text('untouched')
            os.symlink(other, self.path)
            with self.assertRaises(Denied):
                self.initialize()
            self.assertEqual(other.read_text(), 'untouched')

    def test_first_desktop_login_survives_onboarding_delay_but_idle_stays_strict(self):
        credentials = self.initialize()
        token = credentials['editor_token']
        digest = sha256(token.encode()).hexdigest()
        stale = (datetime.now(timezone.utc) - timedelta(seconds=SecureCore.IDLE_SECONDS + 60)).isoformat()
        with _closing_core(self.path) as core:
            core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
                            (stale, digest))
        # The operator can spend minutes copying the displayed one-time code.
        with patch('src.local_operator_gui.launch_gui', return_value=None) as gui:
            open_fictional_pilot(self.path, token)
            gui.assert_called_once()
        with _closing_core(self.path) as core:
            state = core.db.execute(
                'SELECT first_pilot_login_pending FROM credentials WHERE token_digest=?',
                (digest,)).fetchone()
            self.assertEqual(state['first_pilot_login_pending'], 0)
            core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
                            (stale, digest))
        with patch('src.local_operator_gui.launch_gui') as gui:
            with self.assertRaises(Denied):
                open_fictional_pilot(self.path, token)
            gui.assert_not_called()

    def test_first_desktop_login_still_denies_expired_and_revoked_codes(self):
        credentials = self.initialize()
        token = credentials['editor_token']
        digest = sha256(token.encode()).hexdigest()
        with _closing_core(self.path) as core:
            expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
            core.db.execute('UPDATE credentials SET expires_at=? WHERE token_digest=?',
                            (expired, digest))
        with patch('src.local_operator_gui.launch_gui') as gui:
            with self.assertRaises(Denied):
                open_fictional_pilot(self.path, token)
            gui.assert_not_called()
        reviewer = credentials['reviewer_token']
        with _closing_core(self.path) as core:
            core.db.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',
                            (sha256(reviewer.encode()).hexdigest(),))
        with patch('src.local_operator_gui.launch_gui') as gui:
            with self.assertRaises(Denied):
                open_fictional_pilot(self.path, reviewer)
            gui.assert_not_called()

    def test_invalid_token_fails_before_graphical_window_creation(self):
        self.initialize()
        with patch('src.local_operator_gui.launch_gui') as gui:
            with self.assertRaises(Denied):
                open_fictional_pilot(self.path, 'fictional-invalid-credential')
            gui.assert_not_called()

    def test_one_authorized_session_review_completion_and_restart(self):
        credentials = self.initialize()
        with _closing_core(self.path) as core:
            fence = LocalWriteFence(self.path)
            client = LocalOperatorController(
                core, credentials['reviewer_token'], durable_fence=fence)
            self.assertEqual(client.list_matters(), 1)
            client.select(0)
            self.assertEqual(client.counts(), (1, 1))
            consent = client.review(
                0, 'corroborated_manually',
                'Independent fictional human reviewed invented evidence', True)
            self.assertEqual(consent.status, 'review_committed')
            self.assertEqual(client.counts(), (1, 0))
            self.assertEqual(client.complete(0, True).status,
                             'completed_and_refreshed')
            self.assertFalse(fence.is_pending())
            self.assertIn('Open user-entered tasks: 0',
                          client.read_only_current_workload())
            self.assertTrue(core.verify_audit())
        # A new SecureCore and GUI controller see committed state, not stale IDs.
        with _closing_core(self.path) as core:
            reopened = LocalOperatorController(
                core, credentials['reviewer_token'],
                durable_fence=LocalWriteFence(self.path))
            self.assertEqual(reopened.list_matters(), 1)
            reopened.select(0)
            self.assertEqual(reopened.counts(), (0, 0))
            self.assertEqual(core.db.execute(
                "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
            ).fetchone()[0], 1)

    def test_lost_completion_readback_survives_reopened_database(self):
        credentials = self.initialize()
        with _closing_core(self.path) as core:
            client = LocalOperatorController(
                core, credentials['reviewer_token'],
                durable_fence=LocalWriteFence(self.path))
            client.list_matters()
            client.select(0)
            with patch.object(client, 'refresh',
                              side_effect=RuntimeError('fictional lost GUI read')):
                result = client.complete(0, True)
            self.assertEqual(result.status, 'committed_refresh_unresolved')
            self.assertTrue(LocalWriteFence(self.path).is_pending())
        with _closing_core(self.path) as core:
            restarted = LocalOperatorController(
                core, credentials['reviewer_token'],
                durable_fence=LocalWriteFence(self.path))
            restarted.list_matters()
            restarted.select(0)
            self.assertEqual(restarted.counts(), (0, 0))
            self.assertEqual(restarted.reconcile_pending_task_after_restart().status,
                             'observed_local_commit')
            self.assertTrue(LocalWriteFence(self.path).is_pending())
            with self.assertRaises(Denied):
                restarted.complete(0, True)
            self.assertEqual(core.db.execute(
                "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
            ).fetchone()[0], 1)


    def test_view_only_status_after_restart_and_no_audit_write(self):
        credentials = self.initialize()
        with _closing_core(self.path) as core:
            before = core.db.execute('SELECT count(*) FROM audit_chain').fetchone()[0]
            self.assertTrue(core.verify_audit())
        report = inspect_fictional_pilot(self.path, credentials['reviewer_token'])
        self.assertIn('Open user-entered tasks: 1', report['summary'])
        self.assertIn('Second-human reviews waiting: 1', report['summary'])
        self.assertNotIn('Fictional Research Matter', report['summary'])
        self.assertFalse(report['write_unresolved'])
        with _closing_core(self.path) as core:
            self.assertEqual(core.db.execute('SELECT count(*) FROM audit_chain').fetchone()[0],before)

    def test_view_only_status_revoked_denied_and_no_gui(self):
        credentials = self.initialize()
        with _closing_core(self.path) as core:
            core.revoke_token(credentials['reviewer_token'])
        with patch('src.local_operator_gui.launch_gui') as gui:
            with self.assertRaises(Denied):
                inspect_fictional_pilot(self.path,credentials['reviewer_token'])
            gui.assert_not_called()

    def test_view_only_status_never_clears_pending_fence(self):
        credentials = self.initialize()
        fence = LocalWriteFence(self.path)
        fence.begin()
        report = inspect_fictional_pilot(self.path,credentials['reviewer_token'])
        self.assertTrue(report['write_unresolved'])
        self.assertTrue(fence.is_pending())

    def test_view_only_cli_masks_credential_and_denies_invalid_token(self):
        credentials = self.initialize()
        from io import StringIO
        from contextlib import redirect_stdout
        with patch('src.offline_pilot.getpass',return_value=credentials['reviewer_token']), redirect_stdout(StringIO()) as out:
            self.assertEqual(main(['status','--database',str(self.path)]),0)
        self.assertIn('PRIVATE ATTORNEY MATTER PORTFOLIO',out.getvalue())
        self.assertNotIn(credentials['reviewer_token'],out.getvalue())
        with patch('src.offline_pilot.getpass',return_value='invalid'),redirect_stdout(StringIO()) as denied:
            self.assertEqual(main(['status','--database',str(self.path)]),1)
        self.assertNotIn('Fictional Research Matter',denied.getvalue())


class _closing_core:
    def __init__(self, path):
        self.core = SecureCore(path)

    def __enter__(self):
        return self.core

    def __exit__(self, *args):
        self.core.close()


if __name__ == '__main__':
    unittest.main()
