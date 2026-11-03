"""End-to-end real-core transactional procedural review journey; fictional data only."""
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from src.secure_engine import SecureCore, Denied, Stale
from src.research_evidence import EvidenceInvalid
from src.attorney_research_workflow import AttorneyResearchWorkflow, RefreshUnresolved


class WorkflowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name)/'fictional.sqlite3')
        firm = self.core.provision_firm('Invented Firm')
        self.owner, self.token = self.core.provision_user(firm, 'Owner')
        self.second_id, self.second = self.core.provision_user(firm, 'Second Human')
        self.viewer_id, self.viewer = self.core.provision_user(firm, 'Reader')
        other_firm = self.core.provision_firm('Other Invented Firm')
        _, self.other = self.core.provision_user(other_firm, 'Other Reader')
        self.mid = self.core.create_matter(self.token, 'PRIVATE MATTER NAME')['id']
        self.core.grant(self.token, self.mid, self.second_id, 'editor', 1)
        self.core.grant(self.token, self.mid, self.viewer_id, 'viewer', 2)
        self.core.add_note(self.token, self.mid, 'SECRET ATTORNEY NOTE')
        self.task = self.core.create_task(self.token, self.mid, 'PRIVATE TASK BODY', '2026-10-01T00:00:00Z')
        self.workflow = AttorneyResearchWorkflow(self.core)
        self.now = datetime(2026, 11, 3, tzinfo=timezone.utc)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def assert_private(self, snap):
        html=snap.readiness_html
        for private in (b'PRIVATE MATTER NAME',b'PRIVATE TASK BODY', b'SECRET ATTORNEY NOTE', self.mid.encode()):
            self.assertNotIn(private, html)
        self.assertIn(b'Not legal advice', html)
        self.assertIn(b'No AI transmission', html)

    def add(self):
        return self.workflow.add_source(self.token, self.mid,'CONFIDENTIAL SOURCE',
            'https://example.org/fictional-page','PRIVATE EXCERPT',now=self.now)

    def test_complete_human_review_and_task_journey(self):
        self.assertEqual(len(self.workflow.matters(self.token)['matters']), 1)
        start=self.workflow.open(self.token,self.mid,now=self.now)
        self.assert_private(start)
        added=self.add()
        self.assertIn(b'First source observation required',added.snapshot.readiness_html)
        observed=self.workflow.observe(self.token,self.mid,added.record_id,
            'Human-authored fictional observation', 'First user made local manual observation',now=self.now)
        self.assertIn(b'Second human review required',observed.snapshot.readiness_html)
        with self.assertRaises(EvidenceInvalid):
            self.workflow.second_review(self.token,self.mid,added.record_id,observed.record_id,
                 'corroborated_manually','Cannot review my own statement',now=self.now)
        reviewed=self.workflow.second_review(self.second,self.mid,added.record_id,observed.record_id,
             'corroborated_manually','Second lawyer checked fictional source text',now=self.now)
        self.assertIn(b'Two people reviewed; law unverified',reviewed.snapshot.readiness_html)
        self.assert_private(reviewed.snapshot)
        self.assertNotIn(b'PRIVATE EXCERPT',reviewed.snapshot.readiness_html)
        complete=self.workflow.complete_task(self.token,self.mid,self.task['id'],1,now=self.now)
        self.assertEqual(len(complete.workbench['open_tasks']),0)
        self.assertIn(b'Open tasks</span><strong>0',complete.readiness_html)
        self.assertTrue(self.core.verify_audit())
        with self.assertRaises(Stale):
            self.workflow.complete_task(self.token,self.mid,self.task['id'],1,now=self.now)

    def test_second_observation_makes_prior_review_stale(self):
        added=self.add()
        observed=self.workflow.observe(self.token,self.mid,added.record_id,'Initial test observation',
                         'First manual observation record',now=self.now)
        reviewed=self.workflow.second_review(self.second,self.mid,added.record_id,observed.record_id,
                   'corroborated_manually','Independent review of fictional observation',now=self.now)
        self.assertIn(b'Two people reviewed; law unverified',reviewed.snapshot.readiness_html)
        again=self.workflow.observe(self.token,self.mid,added.record_id,'Later new observation',
                       'New observation supersedes prior review',now=self.now)
        self.assertIn(b'Second human review required',again.snapshot.readiness_html)

    def test_viewer_cross_firm_and_revoked_denial(self):
        self.assert_private(self.workflow.open(self.viewer,self.mid,now=self.now))
        with self.assertRaises(Denied):
            self.workflow.add_source(self.viewer,self.mid,'Reader source','https://example.org/a','Reader text',now=self.now)
        with self.assertRaises(Denied):
            self.workflow.open(self.other,self.mid,now=self.now)
        with self.assertRaises(Denied):
            self.workflow.complete_task(self.viewer,self.mid,self.task['id'],1,now=self.now)
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):
            self.workflow.open(self.token,self.mid,now=self.now)

    def test_tamper_observation_and_review_denied(self):
        source=self.add()
        obs=self.workflow.observe(self.token,self.mid,source.record_id,'First text',
                                  'Observed source only as a fictional fixture',now=self.now)
        review=self.workflow.second_review(self.second,self.mid,source.record_id,obs.record_id,
                            'corroborated_manually','Second human approved local fictional notes',now=self.now)
        self.core.db.execute('UPDATE source_second_review SET decision=? WHERE id=?',('rejected',review.record_id))
        with self.assertRaises(EvidenceInvalid):
            self.workflow.open(self.token,self.mid,now=self.now)
        self.core.db.execute('UPDATE source_second_review SET decision=? WHERE id=?',('corroborated_manually',review.record_id))
        self.core.db.execute('UPDATE source_observation SET captured_text=? WHERE observation_id=?',
                             ('FORGED CONTENT',obs.record_id))
        with self.assertRaises(EvidenceInvalid):
            self.workflow.open(self.token,self.mid,now=self.now)

    def test_no_repeat_write_after_refresh_failure(self):
        before=self.core.db.execute('SELECT count(*) FROM research_evidence').fetchone()[0] if self._has_table() else 0
        with patch.object(self.workflow,'open',side_effect=RuntimeError('Synthetic read failure')):
            with self.assertRaises(RefreshUnresolved) as ctx:
                self.add()
        self.assertEqual(ctx.exception.operation,'source.add')
        self.assertEqual(self.core.db.execute('SELECT count(*) FROM research_evidence').fetchone()[0],before+1)
        self.assertEqual(self.core.db.execute("SELECT count(*) FROM audit_chain WHERE action='research.evidence_add'").fetchone()[0],1)
        self.assertEqual(len(self.workflow.open(self.token,self.mid,now=self.now).workbench['open_tasks']),1)

    def test_task_completion_refresh_failure_is_explicitly_unresolved(self):
        before=self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'").fetchone()[0]
        with patch.object(self.workflow, 'open',
                          side_effect=RuntimeError('Fictional lost refresh response')):
            with self.assertRaises(RefreshUnresolved) as ctx:
                self.workflow.complete_task(
                    self.token, self.mid, self.task['id'], 1, now=self.now)
        self.assertEqual(ctx.exception.operation, 'task.complete')
        after=self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='task.complete'").fetchone()[0]
        self.assertEqual(after, before+1)
        observation=self.workflow.reconcile_completion(
            self.token, self.mid, self.task['id'], 1)
        self.assertEqual(observation.status, 'observed_completed')
        self.assertFalse(observation.independent_audit_verified)
        with self.assertRaises(Stale):
            self.workflow.complete_task(
                self.token, self.mid, self.task['id'], 1, now=self.now)

    def _has_table(self):
        return bool(self.core.db.execute("SELECT 1 FROM sqlite_master WHERE name='research_evidence'").fetchone())


if __name__=='__main__': unittest.main()
