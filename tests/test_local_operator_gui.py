"""Headless controller acceptance for actual local Tk GUI over real SecureCore."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.secure_engine import SecureCore, Denied, Invalid, Stale
from src.research_evidence import EvidenceInvalid
from src.local_operator_gui import LocalOperatorController
from src.durable_local_write_fence import LocalWriteFence


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


    def test_explicit_matter_and_task_creation_and_reopen(self):
        fence = LocalWriteFence(Path(self.tmp.name)/'fictional.sqlite3')
        client = LocalOperatorController(self.core,self.author,durable_fence=fence)
        self.assertEqual(client.create_matter('NEW CONFIDENTIAL MATTER',False).status,'cancelled')
        self.assertEqual(client.create_matter('NEW CONFIDENTIAL MATTER',True).status,'matter_created')
        self.assertEqual(client.list_matters(),2)
        # Select the newly created matter by its authorized index.
        index = client.operator.matters(self.author)['matters']
        pos = next(i for i,m in enumerate(index)
                   if self.core.db.execute('SELECT title FROM matters WHERE id=?',
                                         (m['matter_id'],)).fetchone()[0] ==
                   'NEW CONFIDENTIAL MATTER')
        client.select(pos)
        self.assertEqual(client.create_task('PRIVATE FOLLOW-UP', '2030-01-01T00:00:00Z',True).status,'task_created')
        self.assertEqual(client.counts(),(1,0))
        self.assertTrue(self.core.verify_audit())
        self.assertFalse(fence.is_pending())
        self.assertEqual(self.audit_count('matter.create'),2)
        self.assertEqual(self.audit_count('task.create'),2)

    def test_creation_denies_viewer_outsider_and_invalid_dates(self):
        fence = LocalWriteFence(Path(self.tmp.name)/'fictional.sqlite3')
        viewer = LocalOperatorController(self.core,self.viewer,durable_fence=fence)
        viewer.list_matters()
        viewer.select(0)
        with self.assertRaises(Denied):
            viewer.create_task('NOT ALLOWED','2030-01-01T00:00:00Z',True)
        self.assertFalse(fence.is_pending())
        outsider = LocalOperatorController(self.core,self.outside,durable_fence=fence)
        outsider.list_matters()
        with self.assertRaises(Invalid):
            outsider.create_task('NO MATTER','2030-01-01T00:00:00Z',True)
        with self.assertRaises(Invalid):
            viewer.create_task('', 'bad-time',True)
        self.assertEqual(self.audit_count('task.create'),1)

    def test_uncertain_creation_is_fenced_across_restart(self):
        path = Path(self.tmp.name)/'fictional.sqlite3'
        fence = LocalWriteFence(path)
        client = LocalOperatorController(self.core,self.author,durable_fence=fence)
        with patch.object(client.operator,'matters',side_effect=RuntimeError('lost readback')):
            result=client.create_matter('UNCERTAIN FICTIONAL MATTER',True)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertTrue(fence.is_pending())
        restarted=LocalOperatorController(self.core,self.author,durable_fence=LocalWriteFence(path))
        with self.assertRaises(Denied):
            restarted.create_matter('SHOULD NEVER REPLAY',True)
        self.assertEqual(self.audit_count('matter.create'),2)
        self.assertTrue(fence.is_pending())

    def test_invalid_task_date_rejects_before_write_fence_and_allows_correction(self):
        path=Path(self.tmp.name)/'fictional.sqlite3'
        fence=LocalWriteFence(path)
        client=LocalOperatorController(self.core,self.author,durable_fence=fence)
        self.select(client)
        for wrong in ('not-a-date','2030-01-01T00:00:00',None):
            with self.assertRaises(Invalid):
                client.create_task('FICTITIOUS TASK',wrong,True)
            self.assertFalse(fence.is_pending())
        self.assertEqual(self.audit_count('task.create'),1)
        self.assertEqual(client.create_task('CORRECTED TASK','2030-01-01T00:00:00Z',True).status,'task_created')
        self.assertFalse(fence.is_pending())
        self.assertEqual(self.audit_count('task.create'),2)

    def test_revoked_actor_cannot_create_new_matter(self):
        fence=LocalWriteFence(Path(self.tmp.name)/'fictional.sqlite3')
        client=LocalOperatorController(self.core,self.reviewer,durable_fence=fence)
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):
            client.create_matter('BLOCKED',True)
        self.assertFalse(fence.is_pending())


    def test_new_research_source_observation_second_person_and_task(self):
        from src.durable_local_write_fence import LocalWriteFence
        path=Path(self.tmp.name)/'fictional.sqlite3'
        author=LocalOperatorController(self.core,self.author,
                                      durable_fence=LocalWriteFence(path))
        author.list_matters()
        author.select(0)
        self.assertEqual(author.add_research_source(
            'FICTIONAL NEW SOURCE','https://example.org/mock-law',
            'Manually copied fictional excerpt',True).status,'source_recorded')
        saved=author.available_research_sources()
        self.assertEqual(len(saved),2)
        self.assertEqual(author.record_research_observation(
            saved[-1],'Invented human observation',
            'I manually checked the fictional exhibit',True).status,
                         'observation_recorded')
        self.assertFalse(LocalWriteFence(path).is_pending())
        other=LocalOperatorController(self.core,self.reviewer,
                                     durable_fence=LocalWriteFence(path))
        other.list_matters()
        other.select(0)
        self.assertEqual(other.counts(),(1,2))
        self.assertEqual(other.review(
            1,'corroborated_manually',
            'Another human reviewed fictional new evidence',True).status,
            'review_committed')
        self.assertEqual(other.complete(0,True).status,
                         'completed_and_refreshed')
        self.assertTrue(self.core.verify_audit())
        self.assertFalse(LocalWriteFence(path).is_pending())
        self.assertEqual(self.audit_count('research.evidence_add'),2)
        self.assertEqual(self.audit_count('research.manual_source_observation'),2)
        self.assertEqual(self.audit_count('task.complete'),1)

    def test_research_invalid_inputs_denied_before_reservation(self):
        from src.durable_local_write_fence import LocalWriteFence
        path=Path(self.tmp.name)/'fictional.sqlite3'
        cl=LocalOperatorController(self.core,self.author,
                                  durable_fence=LocalWriteFence(path))
        cl.list_matters()
        cl.select(0)
        with self.assertRaises(EvidenceInvalid):
            cl.add_research_source('title','http://unsafe.example','excerpt',True)
        with self.assertRaises(Invalid):
            cl.record_research_observation('bad','x','short',True)
        self.assertFalse(LocalWriteFence(path).is_pending())
        self.assertEqual(self.audit_count('research.evidence_add'),1)

    def test_research_denies_viewer_cross_firm_and_revocation(self):
        from src.durable_local_write_fence import LocalWriteFence
        path=Path(self.tmp.name)/'fictional.sqlite3'
        reader=LocalOperatorController(self.core,self.viewer,
                                      durable_fence=LocalWriteFence(path))
        reader.list_matters()
        reader.select(0)
        with self.assertRaises(Denied):
            reader.add_research_source('title','https://example.org/s','excerpt',True)
        self.assertFalse(LocalWriteFence(path).is_pending())
        outsider=LocalOperatorController(self.core,self.outside,
                                      durable_fence=LocalWriteFence(path))
        outsider.list_matters()
        with self.assertRaises(Denied):
            outsider.add_research_source('title','https://example.org/s','excerpt',True)
        editor=LocalOperatorController(self.core,self.reviewer,
                                      durable_fence=LocalWriteFence(path))
        editor.list_matters()
        editor.select(0)
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):
            editor.add_research_source('title','https://example.org/s','excerpt',True)
        self.assertFalse(LocalWriteFence(path).is_pending())

    def test_research_uncertain_write_stays_blocked_after_new_controller(self):
        from src.durable_local_write_fence import LocalWriteFence
        path=Path(self.tmp.name)/'fictional.sqlite3'
        cl=LocalOperatorController(self.core,self.author,
                                  durable_fence=LocalWriteFence(path))
        cl.list_matters()
        cl.select(0)
        with patch.object(cl,'available_research_sources',
                          side_effect=RuntimeError('lost readback')):
            result=cl.add_research_source('FICTIONAL SOURCE','https://example.org/s',
                                          'Manual excerpt',True)
        self.assertEqual(result.status,'write_unresolved')
        self.assertTrue(LocalWriteFence(path).is_pending())
        new=LocalOperatorController(self.core,self.author,
                                  durable_fence=LocalWriteFence(path))
        new.list_matters()
        new.select(0)
        with self.assertRaises(Denied):
            new.add_research_source('another','https://example.org/new',
                                    'Manual excerpt',True)
        self.assertEqual(self.audit_count('research.evidence_add'),2)
        self.assertTrue(LocalWriteFence(path).is_pending())


    def test_new_matter_owner_explicitly_grants_reviewer_then_completes_research(self):
        from src.durable_local_write_fence import LocalWriteFence
        path=Path(self.tmp.name)/'fictional.sqlite3'
        owner=LocalOperatorController(self.core,self.author,durable_fence=LocalWriteFence(path))
        self.assertEqual(owner.create_matter('NEW FICTIONAL LEGAL MATTER',True).status,
                         'matter_created')
        matters=owner.operator.matters(self.author)['matters']
        new=next(x for x in matters if x['matter_id']!=self.mid)
        owner.list_matters()
        owner.select(matters.index(new))
        with self.assertRaises(Denied):
            self.core._role(self.core._identity(self.reviewer),
                            new['matter_id'],('owner','editor'))
        self.assertEqual(owner.allow_second_reviewer(self.reviewer,
                        new['version'],False).status,'cancelled')
        self.assertEqual(owner.allow_second_reviewer(self.reviewer,
                         new['version'],True).status,'reviewer_authorized')
        self.assertFalse(LocalWriteFence(path).is_pending())
        self.assertEqual(owner.create_task('Fictional new task',
                        '2031-01-01T00:00:00Z',True).status,'task_created')
        self.assertEqual(owner.add_research_source(
             'FICTIONAL EVIDENCE','https://example.org/fictional',
             'Manual invented evidence content',True).status,'source_recorded')
        eid=owner.available_research_sources()[0]
        self.assertEqual(owner.record_research_observation(
            eid,'Imaginary source observation',
            'Human manually observed invented research',True).status,
            'observation_recorded')
        reviewer=LocalOperatorController(self.core,self.reviewer,
                                        durable_fence=LocalWriteFence(path))
        allmatters=reviewer.operator.matters(self.reviewer)['matters']
        reviewer.list_matters()
        reviewer.select(next(i for i,x in enumerate(allmatters)
                        if x['matter_id']==new['matter_id']))
        self.assertEqual(reviewer.counts(),(1,1))
        self.assertEqual(reviewer.review(0,'corroborated_manually',
             'Different human checked this fictional research',True).status,
             'review_committed')
        self.assertEqual(reviewer.complete(0,True).status,
                         'completed_and_refreshed')
        self.assertEqual(reviewer.counts(),(0,0))
        self.assertFalse(LocalWriteFence(path).is_pending())
        self.assertTrue(self.core.verify_audit())

    def test_reviewer_grant_rejects_cross_firm_non_owner_and_stale_version(self):
        from src.durable_local_write_fence import LocalWriteFence
        path=Path(self.tmp.name)/'fictional.sqlite3'
        owner=LocalOperatorController(self.core,self.author,durable_fence=LocalWriteFence(path))
        owner.list_matters()
        owner.select(0)
        row=self.core._role(self.core._identity(self.author),self.mid,('owner',))
        with self.assertRaises(Denied):
            owner.allow_second_reviewer(self.core._identity(self.outside)['id'],
                                         row['version'],True)
        self.assertFalse(LocalWriteFence(path).is_pending())
        staff=LocalOperatorController(self.core,self.reviewer,
                                      durable_fence=LocalWriteFence(path))
        staff.list_matters()
        staff.select(0)
        with self.assertRaises(Denied):
            staff.allow_second_reviewer(self.viewer_id,row['version'],True)
        self.assertFalse(LocalWriteFence(path).is_pending())
        with self.assertRaises(Stale):
            owner.allow_second_reviewer(self.viewer_id,row['version']-1,True)
        self.assertFalse(LocalWriteFence(path).is_pending())

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

    def test_graphical_completion_workload_reauthorizes_current_counts(self):
        client=self.select()
        previous=client.read_only_current_workload()
        self.assertIn('Open user-entered tasks: 1',previous)
        self.assertEqual(client.complete(0,True).status,'completed_and_refreshed')
        refreshed=client.read_only_current_workload()
        self.assertIn('Open user-entered tasks: 0',refreshed)
        self.assertEqual(client.counts(),(0,1))
        for private in ('SECRET CLIENT CASE','SECRET PRIVATE TASK',
                        'SECRET RESEARCH TITLE','SECRET EXCERPT',
                        self.mid,self.eid,self.reviewer):
            self.assertNotIn(private,refreshed)
        self.assertEqual(self.audit_count('task.complete'),1)

    def test_graphical_completion_workload_denied_after_revocation(self):
        client=self.select()
        self.assertEqual(client.complete(0,True).status,'completed_and_refreshed')
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):
            client.read_only_current_workload()
        self.assertEqual(self.audit_count('task.complete'),1)

    def test_graphical_workload_read_failure_does_not_repeat_completion(self):
        client=self.select()
        self.assertEqual(client.complete(0,True).status,'completed_and_refreshed')
        with patch.object(client.operator,'portfolio_summary',
                          side_effect=RuntimeError('fictional read loss')):
            with self.assertRaises(RuntimeError):
                client.read_only_current_workload()
        self.assertEqual(self.audit_count('task.complete'),1)
        self.assertEqual(client.read_only_current_workload().count(
            'Open user-entered tasks: 0'),1)

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
        self.assertTrue(cl.has_recovery())
        self.assertEqual(cl.refresh().open_task_count,0)
        self.assertEqual(cl.counts(),(0,0))
        with self.assertRaises(Invalid):
            cl.complete(0,True)
        self.assertEqual(cl.inspect_uncertain_task_read_only().status,
                         'observed_local_observed_completed')
        self.assertTrue(cl.has_recovery())
        self.assertEqual(self.audit_count('task.complete'),1)

    def test_uncertain_task_refresh_cannot_rearm_completion_or_review(self):
        cl=self.select()
        with patch.object(cl.operator.workflow,'open',
                          side_effect=RuntimeError('synthetic lost readiness')):
            result=cl.complete(0,True)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertTrue(cl.has_recovery())
        self.assertEqual(self.audit_count('task.complete'),1)
        cl.refresh()  # observational; does not reinstate actionable IDs
        self.assertEqual(cl.counts(),(0,0))
        with self.assertRaises(Invalid):
            cl.complete(0,True)
        with self.assertRaises(Invalid):
            cl.review(0,'corroborated_manually',
                      'Fictional follow-up note is intentionally long',True)
        with self.assertRaises(Invalid):
            cl.list_matters()
        observation=cl.inspect_uncertain_task_read_only()
        self.assertEqual(observation.status,'observed_local_observed_completed')
        self.assertTrue(cl.has_recovery())
        self.assertEqual(self.audit_count('task.complete'),1)
        self.assertEqual(self.audit_count('research.second_source_review'),0)

    def test_postcommit_second_refresh_failure_preserves_write_fence(self):
        cl=self.select()
        with patch.object(cl,'refresh',side_effect=RuntimeError('lost GUI refresh')):
            outcome=cl.complete(0,True)
        self.assertEqual(outcome.status,'committed_refresh_unresolved')
        self.assertTrue(cl.has_recovery())
        cl.refresh()
        self.assertEqual(cl.counts(),(0,0))
        self.assertEqual(cl.inspect_uncertain_task_read_only().status,
                         'observed_local_observed_completed')
        self.assertTrue(cl.has_recovery())
        with self.assertRaises(Invalid):
            cl.complete(0,True)
        self.assertEqual(self.audit_count('task.complete'),1)

    def test_uncertain_task_read_only_recovery_denied_after_revocation(self):
        cl=self.select()
        with patch.object(cl.operator.workflow,'open',
                          side_effect=RuntimeError('lost readiness')):
            cl.complete(0,True)
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied):
            cl.inspect_uncertain_task_read_only()
        self.assertTrue(cl.has_recovery())
        self.assertEqual(cl.counts(),(0,0))
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
