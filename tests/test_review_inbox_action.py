"""Confidential review inbox -> atomic decision -> readiness. Fictional SecureCore only."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from src.secure_engine import SecureCore, Denied
from src.research_evidence import EvidenceInvalid
from src.attorney_research_workflow import AttorneyResearchWorkflow, RefreshUnresolved


class ReviewInboxActionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Fictional Legal Practice')
        self.author_id, self.author = self.core.provision_user(firm, 'Author')
        self.reviewer_id, self.reviewer = self.core.provision_user(firm, 'Second Human')
        self.reviewer2_id, self.reviewer2 = self.core.provision_user(firm, 'Third Human')
        self.viewer_id, self.viewer = self.core.provision_user(firm, 'Viewer')
        outside = self.core.provision_firm('Unrelated Firm')
        _, self.outside = self.core.provision_user(outside, 'Outsider')
        self.mid = self.core.create_matter(self.author, 'SECRET MATTER')['id']
        self.core.grant(self.author, self.mid, self.reviewer_id, 'editor', 1)
        self.core.grant(self.author, self.mid, self.reviewer2_id, 'editor', 2)
        self.core.grant(self.author, self.mid, self.viewer_id, 'viewer', 3)
        self.workflow = AttorneyResearchWorkflow(self.core)
        self.eid = self.workflow.evidence.add(self.author, self.mid,
            'SECRET SOURCE', 'https://example.org/fake', 'SECRET EXCERPT')['id']
        self.oid = self.observe('First imaginary observation')
        self.now = datetime(2026, 11, 3, tzinfo=timezone.utc)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def observe(self, text):
        return self.workflow.observations.capture(
            self.author, self.mid, self.eid, text,
            'Manual fictional observation note')['observation_id']

    def submit(self, token=None, observation=None, decision='corroborated_manually'):
        return self.workflow.review_from_inbox(
            self.reviewer if token is None else token,
            self.mid, self.eid, self.oid if observation is None else observation,
            decision, 'Second human reviewed fictional evidence', now=self.now)

    def audit_count(self):
        return self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='research.second_source_review'"
        ).fetchone()[0]

    def test_review_then_private_readiness_and_no_repeat_write(self):
        result = self.submit()
        self.assertEqual(result.operation, 'source.second_review')
        self.assertEqual(len(result.record_id), 32)
        self.assertIn(b'Two people reviewed; law unverified', result.snapshot.readiness_html)
        for secret in (b'SECRET MATTER', b'SECRET SOURCE', b'SECRET EXCERPT',
                       self.mid.encode(), self.eid.encode()):
            self.assertNotIn(secret, result.snapshot.readiness_html)
        self.assertEqual(self.workflow.pending_second_reviews(
            self.reviewer2, self.mid)['items'], [])
        with self.assertRaises(EvidenceInvalid):
            self.submit()
        self.assertEqual(self.audit_count(), 1)

    def test_stale_inbox_item_denied_and_new_item_accepted(self):
        old = self.oid
        current = self.observe('Newer imaginary source')
        with self.assertRaises(EvidenceInvalid):
            self.submit(observation=old)
        self.assertEqual(self.audit_count(), 0)
        result = self.submit(observation=current, decision='needs_further_review')
        self.assertIn(b'Additional human review required', result.snapshot.readiness_html)
        self.assertEqual(self.audit_count(), 1)

    def test_viewer_self_reviewer_cross_firm_and_revoked_denied(self):
        for token in (self.viewer, self.author, self.outside):
            with self.assertRaises((Denied, EvidenceInvalid)):
                self.submit(token=token)
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):
            self.submit()
        self.assertEqual(self.audit_count(), 0)

    def test_uncertain_refresh_exposes_record_for_read_only_reconciliation(self):
        with patch.object(self.workflow, 'open',
                          side_effect=RuntimeError('Fictional lost refresh')):
            with self.assertRaises(RefreshUnresolved) as result:
                self.submit()
        failure = result.exception
        self.assertEqual(failure.operation, 'source.second_review')
        self.assertEqual(len(failure.record_id), 32)
        recovered = self.workflow.reconcile_research(
            self.reviewer, self.mid, failure.operation, failure.record_id)
        self.assertEqual(recovered.status, 'observed_local_commit')
        self.assertFalse(recovered.independent_audit_verified)
        self.assertEqual(self.audit_count(), 1)
        with self.assertRaises(EvidenceInvalid):
            self.submit()
        self.assertEqual(self.audit_count(), 1)

    def test_two_reviewers_cannot_both_commit_same_inbox_item(self):
        def attempt(token):
            try:
                self.submit(token=token)
                return 'committed'
            except EvidenceInvalid:
                return 'denied'
        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(attempt, (self.reviewer, self.reviewer2)))
        self.assertCountEqual(result, ['committed', 'denied'])
        self.assertEqual(self.audit_count(), 1)
        self.assertTrue(self.core.verify_audit())


if __name__ == '__main__':
    unittest.main()
