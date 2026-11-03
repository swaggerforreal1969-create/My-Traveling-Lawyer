"""Headless controller acceptance for actual local Tk GUI over real SecureCore."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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
        # Failed authorization clears all cached selectable IDs. A subsequent
        # write attempt must fail even before reaching a stale credential.
        self.assertEqual(self.client.counts(),(0,0))
        with self.assertRaises(Invalid):
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


    def test_second_refresh_failure_after_committed_review_is_recoverable(self):
        cl=self.select()
        with patch.object(cl,'refresh',side_effect=RuntimeError('Local window refresh failed')):
            outcome=cl.review(0,'corroborated_manually',
                 'Independent human reviewed fictitious material',True)
        self.assertEqual(outcome.status,'committed_refresh_unresolved')
        self.assertTrue(cl.has_recovery())
        self.assertEqual(cl.counts(),(0,0))
        self.assertEqual(self.audit_count('research.second_source_review'),1)
        recovered=cl.reconcile_last_review()
        self.assertEqual(recovered.status,'observed_local_commit')
        self.assertFalse(cl.has_recovery())
        self.assertEqual(self.audit_count('research.second_source_review'),1)
        self.assertTrue(self.core.verify_audit())

    def test_postcommit_feedback_keeps_custody_id_internal(self):
        cl=self.select()
        original=cl.operator.workflow.open
        cl.operator.workflow.open=lambda *args,**kwargs: (
            _ for _ in ()).throw(RuntimeError('Intentional readiness failure'))
        try:
            outcome=cl.review(0,'corroborated_manually',
                'Second human reviewed fictional confidential source',True)
        finally:
            cl.operator.workflow.open=original
        self.assertEqual(outcome.status,'committed_refresh_unresolved')
        self.assertTrue(cl.has_recovery())
        self.assertFalse(hasattr(outcome,'recovery_id'))
        self.assertFalse(hasattr(outcome,'recovery_operation'))
        self.assertNotIn(cl._recovery[1],str(outcome))
        self.assertNotIn(self.eid,str(outcome))
        self.assertNotIn(self.mid,str(outcome))
        self.assertEqual(self.audit_count('research.second_source_review'),1)
        self.assertEqual(cl.reconcile_last_review().status,'observed_local_commit')
        self.assertEqual(self.audit_count('research.second_source_review'),1)

    def test_reconciliation_proof_survives_second_display_refresh_failure(self):
        cl=self.select()
        with patch.object(cl.operator.workflow,'open',
                          side_effect=RuntimeError('Lost readiness display')):
            initial=cl.review(0,'corroborated_manually',
                'Fictional independent manual verification note',True)
        self.assertEqual(initial.status,'committed_refresh_unresolved')
        self.assertTrue(cl.has_recovery())
        with patch.object(cl,'refresh',
                          side_effect=RuntimeError('Display refresh unavailable')):
            observed=cl.reconcile_last_review()
        self.assertEqual(observed.status,'observed_local_commit_refresh_unresolved')
        self.assertIn('Independent custody not verified', observed.message)
        self.assertFalse(cl.has_recovery())
        self.assertEqual(cl.counts(),(0,0))
        self.assertEqual(self.audit_count('research.second_source_review'),1)
        self.assertEqual(cl.refresh().pending_second_review_count,0)
        self.assertEqual(self.audit_count('research.second_source_review'),1)

    def test_unresolved_read_only_reconcile_does_not_invent_commit_confirmation(self):
        cl=self.select()
        with patch.object(cl.operator.workflow,'open',
                          side_effect=RuntimeError('Lost readiness display')):
            cl.review(0,'corroborated_manually',
                'Fictional independent manual verification note',True)
        self.assertTrue(cl.has_recovery())
        from types import SimpleNamespace
        with patch.object(cl.operator,'reconcile_research',
                          return_value=SimpleNamespace(status='unresolved')):
            reply=cl.reconcile_last_review()
        self.assertEqual(reply.status,'reconciliation_unresolved')
        self.assertTrue(cl.has_recovery())
        self.assertEqual(cl.counts(),(0,0))
        self.assertEqual(self.audit_count('research.second_source_review'),1)
        confirmed=cl.reconcile_last_review()
        self.assertEqual(confirmed.status,'observed_local_commit')
        self.assertEqual(self.audit_count('research.second_source_review'),1)

    def test_reviewer_queue_denial_after_task_read_clears_all_actions(self):
        cl=self.select()
        self.assertEqual(cl.counts(),(1,1))
        # The task view succeeds; subsequent independent reviewer query fails.
        with patch.object(cl.operator,'reviewer_inbox',
                          side_effect=Denied('Revoked during refresh')):
            with self.assertRaises(Denied):
                cl.refresh()
        self.assertEqual(cl.counts(),(0,0))
        with self.assertRaises(Invalid):
            cl.complete(0,True)
        with self.assertRaises(Invalid):
            cl.review(0,'corroborated_manually',
                      'Fictional reviewer note is long enough',True)
        self.assertEqual(self.audit_count('task.complete'),0)
        self.assertEqual(self.audit_count('research.second_source_review'),0)

    def test_revoked_session_invalidates_stale_matter_selection(self):
        cl=self.select()
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):
            cl.list_matters()
        self.assertEqual(cl._matters,())
        self.assertEqual(cl.counts(),(0,0))
        with self.assertRaises(Invalid):
            cl.select(0)
        self.assertEqual(self.audit_count('task.complete'),0)

    def test_failed_matter_switch_never_retains_prior_action_ids(self):
        cl=self.select()
        self.assertEqual(cl.counts(),(1,1))
        with patch.object(cl.operator,'select_matter',
                          side_effect=Denied('Matter permission changed')):
            with self.assertRaises(Denied):
                cl.select(0)
        self.assertEqual(cl.counts(),(0,0))
        with self.assertRaises(Invalid):
            cl.complete(0,True)
        self.assertEqual(self.audit_count('task.complete'),0)

    def test_pending_review_fences_refresh_matter_switch_and_all_writes(self):
        cl=self.select()
        with patch.object(cl.operator.workflow, 'open',
                          side_effect=RuntimeError('Lost private refresh')):
            result = cl.review(0, 'corroborated_manually',
                               'Fictional second human verified source', True)
        self.assertEqual(result.status, 'committed_refresh_unresolved')
        self.assertTrue(cl.has_recovery())
        self.assertEqual(self.audit_count('research.second_source_review'), 1)
        # A read-only refresh may occur, but cannot restore actionable IDs.
        cl.refresh()
        self.assertEqual(cl.counts(), (0,0))
        with self.assertRaises(Invalid):
            cl.complete(0, True)
        with self.assertRaises(Invalid):
            cl.review(0, 'rejected', 'Fictional different review note', True)
        with self.assertRaises(Invalid):
            cl.select(0)
        with self.assertRaises(Invalid):
            cl.list_matters()
        self.assertTrue(cl.has_recovery())
        self.assertEqual(self.audit_count('task.complete'), 0)
        self.assertEqual(self.audit_count('research.second_source_review'), 1)
        observed=cl.reconcile_last_review()
        self.assertEqual(observed.status, 'observed_local_commit')
        self.assertFalse(cl.has_recovery())
        self.assertEqual(self.audit_count('research.second_source_review'), 1)
        self.assertEqual(cl.complete(0, True).status, 'completed_and_refreshed')
        self.assertEqual(self.audit_count('task.complete'), 1)

    def test_unresolved_read_only_reconciliation_keeps_session_fenced(self):
        from types import SimpleNamespace
        cl=self.select()
        with patch.object(cl.operator.workflow, 'open',
                          side_effect=RuntimeError('Lost private refresh')):
            cl.review(0, 'corroborated_manually',
                      'Fictional independently verified source', True)
        with patch.object(cl.operator, 'reconcile_research',
                          return_value=SimpleNamespace(status='unresolved')):
            response=cl.reconcile_last_review()
        self.assertEqual(response.status, 'reconciliation_unresolved')
        with self.assertRaises(Invalid):
            cl.list_matters()
        with self.assertRaises(Invalid):
            cl.complete(0, True)
        self.assertEqual(self.audit_count('task.complete'), 0)
        self.assertEqual(self.audit_count('research.second_source_review'), 1)

    def test_revocation_during_pending_recovery_cannot_clear_fence(self):
        cl=self.select()
        with patch.object(cl.operator.workflow, 'open',
                          side_effect=RuntimeError('Lost private refresh')):
            cl.review(0, 'corroborated_manually',
                      'Fictional independently verified source', True)
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):
            cl.reconcile_last_review()
        self.assertTrue(cl.has_recovery())
        with self.assertRaises(Invalid):
            cl.complete(0, True)
        with self.assertRaises(Invalid):
            cl.select(0)
        self.assertEqual(self.audit_count('task.complete'), 0)
        self.assertEqual(self.audit_count('research.second_source_review'), 1)

    def test_second_refresh_failure_after_committed_task_never_retries(self):
        cl=self.select()
        with patch.object(cl,'refresh',side_effect=RuntimeError('Local window refresh failed')):
            result=cl.complete(0,True)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertEqual(cl.counts(),(0,0))
        self.assertEqual(self.audit_count('task.complete'),1)
        self.assertFalse(cl.has_recovery())
        self.assertEqual(cl.refresh().open_task_count,0)
        self.assertEqual(self.audit_count('task.complete'),1)

    def test_cancelled_actions_and_invalid_selection_do_not_gain_auth(self):
        cl=self.select()
        self.assertEqual(cl.review(0,'forged','short',False).status,'cancelled')
        self.assertEqual(cl.complete(0,False).status,'cancelled')
        self.assertEqual(self.audit_count('task.complete'),0)
        self.assertEqual(self.audit_count('research.second_source_review'),0)
        with self.assertRaises(Invalid):cl.select(-1)
        with self.assertRaises(Invalid):cl.review(True,'corroborated_manually',
                                  'An imaginary human review note',True)
        self.assertEqual(self.audit_count('research.second_source_review'),0)



if __name__=='__main__':
    unittest.main()
