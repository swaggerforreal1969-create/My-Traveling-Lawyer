"""Full local confidential attorney operator entry journey (fictional data)."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from src.secure_engine import SecureCore, Denied
from src.private_attorney_operator import PrivateAttorneyOperator
from src.attorney_research_workflow import RefreshUnresolved
from src.research_evidence import EvidenceInvalid


class PrivateOperatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Fictional Legal Firm')
        self.author_id, self.author = self.core.provision_user(firm, 'Fictional Author')
        self.reviewer_id, self.reviewer = self.core.provision_user(firm, 'Fictional Reviewer')
        self.viewer_id, self.viewer = self.core.provision_user(firm, 'Fictional Viewer')
        other = self.core.provision_firm('Other Fictional Firm')
        _, self.outside = self.core.provision_user(other, 'Outsider')
        self.mid = self.core.create_matter(self.author, 'SECRET CLIENT MATTER')['id']
        self.core.grant(self.author, self.mid, self.reviewer_id, 'editor', 1)
        self.core.grant(self.author, self.mid, self.viewer_id, 'viewer', 2)
        self.task = self.core.create_task(self.author, self.mid,
            'SECRET WORK TASK', '2026-10-01T00:00:00Z')
        self.operator = PrivateAttorneyOperator(self.core)
        self.now = datetime(2026, 11, 3, tzinfo=timezone.utc)
        self.eid = self.operator.workflow.evidence.add(
            self.author, self.mid, 'SECRET SOURCE TITLE',
            'https://example.org/invented', 'SECRET SOURCE EXCERPT')['id']
        self.oid = self.operator.workflow.observations.capture(
            self.author, self.mid, self.eid, 'Fictional observation',
            'Author manually observed fake evidence')['observation_id']

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def screen(self, token=None):
        return self.operator.select_matter(
            self.reviewer if token is None else token, self.mid, now=self.now)

    def test_index_selection_review_task_and_private_refreshed_readiness(self):
        index = self.operator.matters(self.reviewer)
        self.assertEqual([m['matter_id'] for m in index['matters']], [self.mid])
        screen = self.screen()
        self.assertEqual(screen.schema, 'mtl.private.operator.screen.v1')
        self.assertEqual((screen.open_task_count, screen.pending_second_review_count), (1, 1))
        self.assertTrue(screen.can_complete_tasks)
        for private in (b'SECRET CLIENT MATTER', b'SECRET SOURCE TITLE',
                        b'SECRET SOURCE EXCERPT', b'SECRET WORK TASK',
                        self.mid.encode(), self.eid.encode()):
            self.assertNotIn(private, screen.readiness_html)
        self.assertFalse(screen.official_law_verified)
        self.assertFalse(screen.court_filing_approved)
        self.assertFalse(screen.external_ai_transmission)
        inbox = self.operator.reviewer_inbox(self.reviewer, self.mid)
        self.assertEqual(inbox['items'][0]['observation_id'], self.oid)
        result = self.operator.decide_review(self.reviewer, self.mid, self.eid,
            self.oid, 'corroborated_manually', 'Second human checked fake source',
            now=self.now)
        self.assertIn(b'Two people reviewed; law unverified', result.snapshot.readiness_html)
        self.assertEqual(self.screen().pending_second_review_count, 0)
        done = self.operator.complete_task(self.reviewer, self.mid,
            self.task['id'], 1, now=self.now)
        self.assertEqual(done.status, 'completed_and_refreshed')
        self.assertEqual(self.screen().open_task_count, 0)
        self.assertTrue(self.core.verify_audit())

    def test_full_review_completion_refreshes_private_portfolio(self):
        # Real fictional SecureCore -> review inbox -> human review -> task
        # completion -> private portfolio. No fixture-only readiness provider.
        prior=self.operator.portfolio(self.reviewer,now=self.now)
        self.assertEqual((prior.total_open_tasks,prior.total_second_reviews),(1,1))
        inbox=self.operator.reviewer_inbox(self.reviewer,self.mid)
        self.assertEqual(len(inbox['items']),1)
        self.operator.decide_review(self.reviewer,self.mid,self.eid,self.oid,
            'corroborated_manually','Fictional independent manual review',
            now=self.now)
        reviewed=self.operator.portfolio(self.reviewer,now=self.now)
        self.assertEqual((reviewed.total_open_tasks,
                          reviewed.total_second_reviews),(1,0))
        completed=self.operator.complete_task(self.reviewer,self.mid,
            self.task['id'],1,now=self.now)
        self.assertEqual(completed.status,'completed_and_refreshed')
        screen=self.screen()
        self.assertEqual((screen.open_task_count,
                          screen.pending_second_review_count),(0,0))
        final=self.operator.portfolio(self.reviewer,now=self.now)
        self.assertEqual((final.total_open_tasks,
                          final.total_second_reviews),(0,0))
        summary=self.operator.portfolio_summary(self.reviewer,now=self.now)
        self.assertIn('Open user-entered tasks: 0',summary)
        for secret in ('SECRET CLIENT MATTER','SECRET SOURCE TITLE',
                       'SECRET SOURCE EXCERPT','SECRET WORK TASK',
                       self.mid,self.eid,self.reviewer):
            self.assertNotIn(secret,summary)
        self.assertEqual(self.operator.portfolio(self.outside,now=self.now)
                         .total_open_tasks,0)
        self.assertTrue(self.core.verify_audit())

    def test_committed_completion_lost_refresh_reconciles_without_replay(self):
        self.assertEqual(self.operator.portfolio(self.reviewer,now=self.now)
                         .total_open_tasks,1)
        with patch.object(self.operator.workflow,'open',
                          side_effect=RuntimeError('fictional lost refresh')):
            result=self.operator.complete_task(self.reviewer,self.mid,
                self.task['id'],1,now=self.now)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertEqual(self.operator.portfolio(self.reviewer,now=self.now)
                         .total_open_tasks,0)
        state=self.operator.reconcile_task(self.reviewer,self.mid,
                                           self.task['id'],1)
        self.assertEqual(state.status,'observed_completed')
        self.assertEqual(self.operator.complete_task(self.reviewer,self.mid,
            self.task['id'],1,now=self.now).status,
            'observed_completed_no_write')
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0],1)
        self.assertTrue(self.core.verify_audit())

    def test_viewer_can_open_minimal_readiness_but_never_review_or_complete(self):
        view = self.screen(self.viewer)
        self.assertFalse(view.can_complete_tasks)
        self.assertEqual(view.pending_second_review_count, 0)
        with self.assertRaises(Denied):
            self.operator.reviewer_inbox(self.viewer, self.mid)
        with self.assertRaises(Denied):
            self.operator.complete_task(self.viewer, self.mid, self.task['id'], 1, now=self.now)

    def test_other_firm_unrelated_matter_and_revoked_access_denied(self):
        with self.assertRaises(Denied):
            self.operator.select_matter(self.outside, self.mid, now=self.now)
        other = self.core.create_matter(self.author, 'Second secret matter')['id']
        with self.assertRaises(Denied):
            self.operator.select_matter(self.reviewer, other, now=self.now)
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):
            self.screen()
        with self.assertRaises(Denied):
            self.operator.decide_review(self.reviewer, self.mid, self.eid,
                self.oid, 'corroborated_manually',
                'Revoked user cannot review fictional evidence', now=self.now)

    def test_lost_refresh_recovery_without_replay(self):
        with patch.object(self.operator.workflow, 'open',
                          side_effect=RuntimeError('Lost local refresh')):
            with self.assertRaises(RefreshUnresolved) as raised:
                self.operator.decide_review(self.reviewer, self.mid, self.eid, self.oid,
                    'corroborated_manually', 'Second human checked fake source',
                    now=self.now)
        exc = raised.exception
        state = self.operator.reconcile_research(
            self.reviewer, self.mid, exc.operation, exc.record_id)
        self.assertEqual(state.status, 'observed_local_commit')
        self.assertFalse(state.independent_audit_verified)
        with self.assertRaises(EvidenceInvalid):
            self.operator.decide_review(self.reviewer, self.mid, self.eid, self.oid,
                'corroborated_manually', 'Duplicate review must be denied',
                now=self.now)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='research.second_source_review'"
        ).fetchone()[0], 1)

    def test_stale_reviewer_selection_and_task_repeat_do_not_write(self):
        old = self.operator.reviewer_inbox(self.reviewer, self.mid)['items'][0]
        self.operator.workflow.observations.capture(self.author, self.mid, self.eid,
            'New fictional observation', 'New manual source observation note')
        with self.assertRaises(EvidenceInvalid):
            self.operator.decide_review(self.reviewer, self.mid, old['evidence_id'],
                old['observation_id'], 'corroborated_manually',
                'Old review must be rejected', now=self.now)
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0], 0)
        self.operator.complete_task(self.reviewer, self.mid, self.task['id'], 1, now=self.now)
        self.assertEqual(self.operator.complete_task(self.reviewer, self.mid,
            self.task['id'], 1, now=self.now).status, 'observed_completed_no_write')
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
        ).fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
