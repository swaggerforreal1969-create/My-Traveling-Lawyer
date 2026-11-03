"""Headless controller acceptance for actual local Tk GUI over real SecureCore."""
from pathlib import Path
import tempfile
import unittest

from src.secure_engine import SecureCore, Denied, Invalid
from src.research_evidence import EvidenceInvalid
from src.local_operator_gui import LocalOperatorController


class GraphicalOperatorControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.core=SecureCore(Path(self.tmp.name)/'fictional.sqlite3')
        firm=self.core.provision_firm('Fictional Legal Practice')
        self.author_id,self.author=self.core.provision_user(firm,'Author')
        self.reviewer_id,self.reviewer=self.core.provision_user(firm,'Reviewer')
        self.viewer_id,self.viewer=self.core.provision_user(firm,'Reader')
        other=self.core.provision_firm('Other Fictional Firm')
        _,self.outside=self.core.provision_user(other,'Outsider')
        self.mid=self.core.create_matter(self.author,'SECRET CLIENT CASE')['id']
        self.core.grant(self.author,self.mid,self.reviewer_id,'editor',1)
        self.core.grant(self.author,self.mid,self.viewer_id,'viewer',2)
        self.task=self.core.create_task(self.author,self.mid,'SECRET PRIVATE TASK',
                         '2026-10-01T00:00:00Z')
        self.client=LocalOperatorController(self.core,self.reviewer)
        self.eid=self.client.operator.workflow.evidence.add(
            self.author,self.mid,'SECRET RESEARCH TITLE',
            'https://example.org/imagined','SECRET EXCERPT')['id']
        self.oid=self.client.operator.workflow.observations.capture(
            self.author,self.mid,self.eid,'SECRET CAPTURE',
            'Manual observation from fictional document')['observation_id']

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def select(self,client=None):
        cl=self.client if client is None else client
        self.assertEqual(cl.list_matters(),1)
        cl.select(0)
        return cl

    def audit_count(self,action):
        return self.core.db.execute(
            'SELECT count(*) FROM audit_chain WHERE action=?',(action,)).fetchone()[0]

    def test_full_graphical_controller_journey(self):
        cl=self.select()
        self.assertEqual(cl.counts(),(1,1))
        self.assertEqual(cl.review(0,'corroborated_manually',
            'Second human checked fictitious source',False).status,'cancelled')
        self.assertEqual(self.audit_count('research.second_source_review'),0)
        review=cl.review(0,'corroborated_manually',
                         'Second human checked fictitious source',True)
        self.assertEqual(review.status,'review_committed')
        self.assertEqual(cl.counts(),(1,0))
        self.assertEqual(cl.complete(0,False).status,'cancelled')
        self.assertEqual(self.audit_count('task.complete'),0)
        result=cl.complete(0,True)
        self.assertEqual(result.status,'completed_and_refreshed')
        self.assertEqual(cl.counts(),(0,0))
        self.assertEqual(self.audit_count('task.complete'),1)
        self.assertTrue(self.core.verify_audit())

    def test_cross_firm_viewer_and_revocation_denied(self):
        self.assertEqual(LocalOperatorController(self.core,self.outside).list_matters(),0)
        reader=self.select(LocalOperatorController(self.core,self.viewer))
        self.assertEqual(reader.counts(),(0,0))
        with self.assertRaises(Invalid):reader.complete(0,True)
        self.select()
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):self.client.refresh()
        with self.assertRaises(Denied):
            self.client.review(0,'corroborated_manually',
                'Revoked session cannot commit review',True)
        self.assertEqual(self.audit_count('research.second_source_review'),0)

    def test_stale_review_and_task_are_not_replayed(self):
        self.select()
        self.client.operator.workflow.observations.capture(
            self.author,self.mid,self.eid,'New fake observation',
            'Second manually checked observation')
        with self.assertRaises(EvidenceInvalid):
            self.client.review(0,'corroborated_manually',
                'Review cannot sign superseded observation',True)
        self.assertEqual(self.audit_count('research.second_source_review'),0)
        self.client.refresh()
        self.core.complete_task(self.author,self.task['id'],1)
        result=self.client.complete(0,True)
        self.assertEqual(result.status,'observed_completed_no_write')
        self.assertEqual(self.audit_count('task.complete'),1)

    def test_uncertain_review_and_actor_only_read_only_recovery(self):
        self.select()
        cl=self.client
        original=cl.operator.workflow.open
        cl.operator.workflow.open=lambda *a,**k:(
            _ for _ in ()).throw(RuntimeError('Lost local refresh'))
        result=cl.review(0,'corroborated_manually',
                  'Second human checked imaginary authority',True)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertEqual(cl.counts(),(0,0))
        self.assertEqual(self.audit_count('research.second_source_review'),1)
        cl.operator.workflow.open=original
        recovered=cl.reconcile_last_review()
        self.assertEqual(recovered.status,'observed_local_commit')
        self.assertEqual(self.audit_count('research.second_source_review'),1)
        with self.assertRaises(Invalid):cl.reconcile_last_review()

    def test_bad_state_no_write_and_no_client_text_in_controller_results(self):
        self.select()
        with self.assertRaises(Invalid):self.client.review(-1,
            'corroborated_manually','Second human fictional note',True)
        with self.assertRaises(Invalid):self.client.complete(True,True)
        with self.assertRaises(Invalid):self.client.review(0,
            'forged_decision','Second human fictional note',True)
        with self.assertRaises(Invalid):self.client.review(0,
            'corroborated_manually','Too short',True)
        result=self.client.complete(0,False)
        for private in ('SECRET CLIENT CASE','SECRET PRIVATE TASK',
                        'SECRET RESEARCH TITLE','SECRET EXCERPT',self.mid,
                        self.eid,self.oid,self.reviewer):
            self.assertNotIn(private,str(result))
        self.assertEqual(self.audit_count('task.complete'),0)

    def test_revoked_session_cannot_reconcile_prior_review(self):
        self.select()
        cl=self.client
        cl.operator.workflow.open=lambda *a,**k: (
            _ for _ in ()).throw(RuntimeError('lost refresh'))
        cl.review(0,'corroborated_manually',
                  'Human approved imaginary source',True)
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):cl.reconcile_last_review()


if __name__=='__main__':
    unittest.main()
