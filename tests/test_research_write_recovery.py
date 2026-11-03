"""Genuine SecureCore procedural research recovery; fictional data only."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest
from src.secure_engine import SecureCore, Denied, Invalid
from src.attorney_research_workflow import AttorneyResearchWorkflow, RefreshUnresolved


class ResearchWriteRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Fictional Legal Practice')
        self.owner, self.token = self.core.provision_user(firm, 'Fictional Author')
        self.reviewer_id, self.reviewer = self.core.provision_user(firm, 'Fictional Second Reviewer')
        self.viewer_id, self.viewer = self.core.provision_user(firm, 'Reader')
        other_firm = self.core.provision_firm('Separate Fictional Firm')
        _, self.outsider = self.core.provision_user(other_firm, 'Outsider')
        self.mid = self.core.create_matter(self.token, 'SECRET FICTIONAL CASE')['id']
        self.core.grant(self.token, self.mid, self.reviewer_id, 'editor', 1)
        self.core.grant(self.token, self.mid, self.viewer_id, 'viewer', 2)
        self.workflow = AttorneyResearchWorkflow(self.core)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def add(self):
        return self.workflow.evidence.add(self.token, self.mid, 'SECRET SOURCE',
                                         'https://example.org/fictional', 'SECRET EXCERPT')['id']

    def observe(self, eid):
        return self.workflow.observations.capture(
            self.token, self.mid, eid, 'Fictional captured text',
            'Manual note on invented source')['observation_id']

    def test_source_add_recovery_and_no_replay(self):
        before=self.core.db.execute('SELECT count(*) FROM research_evidence').fetchone()[0]
        with patch.object(self.workflow, 'open', side_effect=RuntimeError('lost read')):
            with self.assertRaises(RefreshUnresolved) as context:
                self.workflow.add_source(self.token, self.mid, 'Fictional',
                    'https://example.org/fictional', 'Fictional excerpt')
        exc=context.exception
        self.assertEqual(exc.operation, 'source.add')
        self.assertEqual(len(exc.record_id), 32)
        state=self.workflow.reconcile_research(self.token,self.mid,exc.operation,exc.record_id)
        self.assertEqual(state.status,'observed_local_commit')
        self.assertFalse(state.official_source_authenticated)
        self.assertFalse(state.independent_audit_verified)
        self.assertNotIn('SECRET',repr(state))
        self.assertEqual(self.core.db.execute('SELECT count(*) FROM research_evidence').fetchone()[0],before+1)

    def test_observation_and_second_human_review_recovery(self):
        eid=self.add()
        obs=self.observe(eid)
        observed=self.workflow.reconcile_research(self.token,self.mid,'source.observe',obs)
        self.assertEqual(observed.operation,'source.observe')
        review=self.workflow.reviews.record(self.reviewer,self.mid,eid,obs,
            'corroborated_manually','Second human checked invented source')
        confirmed=self.workflow.reconcile_research(
            self.reviewer,self.mid,'source.second_review',review['review_id'])
        self.assertEqual(confirmed.status,'observed_local_commit')
        with self.assertRaises(Denied):
            self.workflow.reconcile_research(self.token,self.mid,
                'source.second_review',review['review_id'])
        self.assertFalse(confirmed.legal_authority_current)

    def test_viewer_cross_firm_wrong_matter_and_revoked_denied(self):
        eid=self.add()
        with self.assertRaises(Denied):
            self.workflow.reconcile_research(self.viewer,self.mid,'source.add',eid)
        with self.assertRaises(Denied):
            self.workflow.reconcile_research(self.outsider,self.mid,'source.add',eid)
        unrelated=self.core.create_matter(self.token,'Other case')['id']
        with self.assertRaises(Denied):
            self.workflow.reconcile_research(self.token,unrelated,'source.add',eid)
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):
            self.workflow.reconcile_research(self.token,self.mid,'source.add',eid)

    def test_forged_evidence_content_and_missing_audit_denied(self):
        eid=self.add()
        self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',
                             ('FORGED',eid))
        with self.assertRaises(Invalid):
            self.workflow.reconcile_research(self.token,self.mid,'source.add',eid)
        self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',
                             ('SECRET EXCERPT',eid))
        self.core.db.execute("DELETE FROM audit_chain WHERE action='research.evidence_add' AND target=?",
                             (eid,))
        with self.assertRaises(Invalid):
            self.workflow.reconcile_research(self.token,self.mid,'source.add',eid)

    def test_forged_observation_and_review_denied(self):
        eid=self.add()
        obs=self.observe(eid)
        review=self.workflow.reviews.record(self.reviewer,self.mid,eid,obs,
            'rejected','Second human rejected invented observation')
        self.core.db.execute('UPDATE source_second_review SET decision=? WHERE id=?',
                             ('corroborated_manually',review['review_id']))
        with self.assertRaises(Invalid):
            self.workflow.reconcile_research(
                self.reviewer,self.mid,'source.second_review',review['review_id'])
        self.core.db.execute('UPDATE source_observation SET note=? WHERE observation_id=?',
                             ('FORGED NOTE',obs))
        with self.assertRaises(Invalid):
            self.workflow.reconcile_research(self.token,self.mid,'source.observe',obs)

    def test_invalid_identifiers_fail_closed(self):
        eid=self.add()
        with self.assertRaises(Invalid):
            self.workflow.reconcile_research(self.token,self.mid,'other',eid)
        with self.assertRaises(Invalid):
            self.workflow.reconcile_research(self.token,self.mid,'source.add','bad')
        with self.assertRaises(Denied):
            self.workflow.reconcile_research(self.token,self.mid,'source.add','0'*32)


if __name__=='__main__':
    unittest.main()
