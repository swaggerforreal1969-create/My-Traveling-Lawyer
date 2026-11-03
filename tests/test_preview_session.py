"""Fictional-only tests of durable one-use mobile preview session boundary."""
import hashlib
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.secure_engine import SecureCore, Denied
from src.preview_session import PreviewSessionBroker, TicketRejected
from src.research_evidence import ResearchEvidence
from src.authority_review import AuthorityReview


class PreviewSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fictional.sqlite3'
        self.core = SecureCore(self.path)
        firm = self.core.provision_firm('Fictional Practice')
        self.uid, self.token = self.core.provision_user(firm, 'Fictional Lawyer')
        _, self.another_token = self.core.provision_user(firm, 'Invented Colleague')
        outsider = self.core.provision_firm('Different Imagined Firm')
        _, self.outsider_token = self.core.provision_user(outsider, 'Imagined Outsider')
        self.mid = self.core.create_matter(self.token, 'Fictional matter')['id']
        self.other_mid = self.core.create_matter(self.token, 'Another fictional matter')['id']
        self.broker = PreviewSessionBroker(self.core)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def ticket(self):
        return self.broker.issue(self.token, self.mid)['ticket']

    def test_genuine_authorized_preview(self):
        response = self.broker.consume(self.token, self.mid, self.ticket())
        self.assertEqual(200, response.status)
        self.assertIn(b'Fictional matter', response.body)
        self.assertEqual('DENY', dict(response.headers)['X-Frame-Options'])

    def test_single_use_replay_rejected(self):
        ticket = self.ticket()
        self.broker.consume(self.token, self.mid, ticket)
        with self.assertRaises(TicketRejected):
            self.broker.consume(self.token, self.mid, ticket)

    def test_wrong_matter_does_not_burn_ticket(self):
        ticket = self.ticket()
        with self.assertRaises(TicketRejected):
            self.broker.consume(self.token, self.other_mid, ticket)
        self.assertEqual(200, self.broker.consume(self.token, self.mid, ticket).status)

    def test_wrong_token_fails_closed(self):
        ticket = self.ticket()
        with self.assertRaises(Denied):
            self.broker.consume(self.another_token, self.mid, ticket)
        self.assertEqual(200, self.broker.consume(self.token, self.mid, ticket).status)

    def test_cross_firm_denied(self):
        with self.assertRaises(Denied):
            self.broker.issue(self.outsider_token, self.mid)
        with self.assertRaises(Denied):
            self.broker.consume(self.outsider_token, self.mid, self.ticket())

    def test_token_revocation_before_consumption(self):
        ticket = self.ticket()
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):
            self.broker.consume(self.token, self.mid, ticket)

    def test_expired_ticket_rejected(self):
        ticket = self.ticket()
        self.core.db.execute('UPDATE preview_ticket SET expires_at=?',
                             ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),))
        with self.assertRaises(TicketRejected):
            self.broker.consume(self.token, self.mid, ticket)

    def test_ticket_not_cleartext_in_storage(self):
        ticket = self.ticket()
        row = self.core.db.execute('SELECT * FROM preview_ticket').fetchone()
        self.assertNotIn(ticket, repr(tuple(row)))
        self.assertNotIn(self.token, repr(tuple(row)))
        self.assertEqual(hashlib.sha256(ticket.encode()).hexdigest(), row['ticket_digest'])

    def test_rejects_unsafe_ttl(self):
        for value in (0, -1, 121, True, 3.2):
            with self.subTest(value=value), self.assertRaises(TicketRejected):
                self.broker.issue(self.token, self.mid, ttl_seconds=value)

    def test_durable_replay_denial_across_restart(self):
        ticket = self.ticket()
        self.broker.consume(self.token, self.mid, ticket)
        self.core.close()
        self.core = SecureCore(self.path)
        self.broker = PreviewSessionBroker(self.core)
        with self.assertRaises(TicketRejected):
            self.broker.consume(self.token, self.mid, ticket)

    def test_concurrent_consume_one_success(self):
        ticket = self.ticket()
        barrier = threading.Barrier(2)
        def consume():
            barrier.wait()
            try:
                self.broker.consume(self.token, self.mid, ticket)
                return 'ok'
            except TicketRejected:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: consume(), range(2)))
        self.assertEqual(['ok', 'rejected'], sorted(results))

    def test_failed_render_burns_ticket(self):
        ticket = self.ticket()
        with patch.object(self.broker.gateway, 'renderer', side_effect=RuntimeError('local rendering error')):
            with self.assertRaises(RuntimeError):
                self.broker.consume(self.token, self.mid, ticket)
        with self.assertRaises(TicketRejected):
            self.broker.consume(self.token, self.mid, ticket)

    def test_no_network_attempt(self):
        import socket
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
            self.assertEqual(200, self.broker.consume(self.token, self.mid, self.ticket()).status)

    def test_viewer_can_issue_not_change_matter(self):
        viewer_id, viewer_token = self.core.provision_user(self.core._identity(self.token)['firm_id'], 'Viewer')
        self.core.grant(self.token, self.mid, viewer_id, 'viewer', 1)
        ticket = self.broker.issue(viewer_token, self.mid)['ticket']
        self.assertEqual(200, self.broker.consume(viewer_token, self.mid, ticket).status)
        with self.assertRaises(Denied):
            self.core.add_note(viewer_token, self.mid, 'Forbidden')

    def test_bad_ticket_and_time_validation(self):
        for ticket in (None, '', 3):
            with self.assertRaises(TicketRejected):
                self.broker.consume(self.token, self.mid, ticket)
        with self.assertRaises(TicketRejected):
            self.broker.consume(self.token, self.mid, self.ticket(), now=datetime(2026,11,3))


if __name__ == '__main__':
    unittest.main()
