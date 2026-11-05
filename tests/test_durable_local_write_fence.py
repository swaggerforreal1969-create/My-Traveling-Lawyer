"""Fictional real SQLite tests for crash-durable local write fencing."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import multiprocessing
import sqlite3
import unittest

from src.durable_local_write_fence import LocalWriteFence
from src.local_operator_gui import LocalOperatorController
from src.secure_engine import SecureCore, Denied, Invalid


def independent_try_begin(path, queue):
    try:
        LocalWriteFence(path).begin()
    except Denied:
        queue.put('denied')
    else:
        queue.put('allowed')


class DurableLocalWriteFenceTests(unittest.TestCase):
    def setUp(self):
        self.dir=TemporaryDirectory()
        self.path=Path(self.dir.name) / 'fictional.sqlite3'
        self.core=SecureCore(self.path)
        firm=self.core.provision_firm('Imaginary Firm')
        _,self.author=self.core.provision_user(firm,'Fictional Author')
        editor_id,self.editor=self.core.provision_user(firm,'Fictional Editor')
        self.mid=self.core.create_matter(self.author,'SECRET FICTIONAL MATTER')['id']
        self.core.grant(self.author,self.mid,editor_id,'editor',1)
        self.core.create_task(self.author,self.mid,'SECRET FICTIONAL TASK',
                              '2026-10-01T00:00:00Z')
        flow=LocalOperatorController(self.core,self.editor)
        self.eid=flow.operator.workflow.evidence.add(
            self.author,self.mid,'SECRET FICTIONAL SOURCE',
            'https://example.org/fiction','SECRET EXCERPT')['id']
        flow.operator.workflow.observations.capture(
            self.author,self.mid,self.eid,
            'Fictional source observation','Human recorded fictitious source')
        self.fence=LocalWriteFence(self.path)
        self.client=LocalOperatorController(
            self.core,self.editor,durable_fence=self.fence)
        self.assertEqual(self.client.list_matters(),1)
        self.client.select(0)

    def tearDown(self):
        self.core.close()
        self.dir.cleanup()

    def count(self, action):
        return self.core.db.execute(
            'SELECT count(*) FROM audit_chain WHERE action=?',(action,)).fetchone()[0]

    def test_review_second_display_failure_keeps_durable_fence_after_restart(self):
        with patch.object(self.client,'refresh',
                          side_effect=RuntimeError('lost postcommit review display')):
            result=self.client.review(
                0,'corroborated_manually',
                'Human independently verified imaginary research',True)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertEqual(self.count('research.second_source_review'),1)
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.fence.pending_kind(),'review')
        restarted=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        restarted.list_matters()
        restarted.select(0)
        self.assertEqual(restarted.counts(),(0,0))
        self.assertEqual(restarted.reconcile_pending_review_after_restart().status,
                         'observed_local_commit')
        self.assertFalse(self.fence.is_pending())
        self.assertEqual(self.count('research.second_source_review'),1)

    def test_review_final_cas_rejection_never_rearms_tasks(self):
        with patch.object(self.fence,'finish_confirmed',
                          side_effect=Denied('synthetic CAS denial')):
            result=self.client.review(
                0,'corroborated_manually',
                'Human independently checked fictional evidence',True)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertTrue(self.fence.is_pending())
        self.assertTrue(self.client.has_recovery())
        self.client.refresh()
        self.assertEqual(self.client.counts(),(0,0))
        with self.assertRaises(Denied):
            self.client.complete(0,True)
        self.assertEqual(self.count('research.second_source_review'),1)
        self.assertEqual(self.count('task.complete'),0)

    def test_review_successful_final_display_clears_reservation(self):
        result=self.client.review(
            0,'corroborated_manually',
            'Independent human reviewed fictitious source',True)
        self.assertEqual(result.status,'review_committed')
        self.assertFalse(self.fence.is_pending())
        self.assertEqual(self.count('research.second_source_review'),1)

    def test_task_reservation_readback_after_local_commit_retains_fence(self):
        from src.task_reconciliation import reconcile_task
        task=self.client._tasks[0]
        with patch.object(self.client.operator.workflow,'open',
                          side_effect=RuntimeError('Lost completion acknowledgment')):
            result=self.client.complete(0,True)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.fence.pending_kind(),'task')
        after=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        after.list_matters()
        after.select(0)
        self.assertEqual(after.counts(),(0,0))
        reply=after.reconcile_pending_task_after_restart()
        self.assertEqual(reply.status,'observed_local_commit')
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.count('task.complete'),1)
        self.assertEqual(reconcile_task(self.core,self.editor,self.mid,
                                       task[0],task[1]).status,'observed_completed')
        with self.assertRaises(Denied):
            after.complete(0,True)
        data=self.fence.path.read_bytes()
        for secret in (self.editor,self.author,self.mid,task[0]):
            self.assertNotIn(secret.encode(),data)

    def test_task_second_display_failure_retains_durable_fence_across_restart(self):
        task=self.client._tasks[0]
        with patch.object(self.client,'refresh',
                          side_effect=RuntimeError('postcommit GUI read failed')):
            outcome=self.client.complete(0,True)
        self.assertEqual(outcome.status,'committed_refresh_unresolved')
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.fence.pending_kind(),'task')
        self.assertEqual(self.count('task.complete'),1)
        reopened=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        reopened.list_matters()
        reopened.select(0)
        self.assertEqual(reopened.counts(),(0,0))
        self.assertEqual(reopened.reconcile_pending_task_after_restart().status,
                         'observed_local_commit')
        self.assertTrue(self.fence.is_pending())
        with self.assertRaises(Denied):
            reopened.complete(0,True)
        self.assertEqual(self.count('task.complete'),1)

    def test_task_final_clearance_failure_never_replays_or_rearms(self):
        with patch.object(self.fence,'finish_confirmed',
                          side_effect=Denied('simulated CAS rejection')):
            result=self.client.complete(0,True)
        self.assertEqual(result.status,'committed_refresh_unresolved')
        self.assertTrue(self.fence.is_pending())
        self.assertTrue(self.client.has_recovery())
        self.client.refresh()
        self.assertEqual(self.client.counts(),(0,0))
        with self.assertRaises(Invalid):
            self.client.complete(0,True)
        self.assertEqual(self.count('task.complete'),1)

    def test_task_successful_display_clears_exact_reservation(self):
        self.assertFalse(self.fence.is_pending())
        result=self.client.complete(0,True)
        self.assertEqual(result.status,'completed_and_refreshed')
        self.assertFalse(self.fence.is_pending())
        self.assertEqual(self.count('task.complete'),1)
        restarted=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        restarted.list_matters()
        restarted.select(0)
        self.assertEqual(restarted.counts()[0],0)

    def test_task_reservation_prewrite_crash_readback_retains_fence(self):
        task=self.client._tasks[0]
        actor=self.core._identity(self.editor)
        before=self.core.db.execute(
            'SELECT COALESCE(MAX(seq),0) FROM audit_chain').fetchone()[0]
        self.fence.begin(task_identity=(actor['id'],self.mid,task[0],task[1]),
                         audit_before=before)
        after=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        after.list_matters()
        after.select(0)
        self.assertEqual(after.reconcile_pending_task_after_restart().status,
                         'observed_local_no_commit')
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.count('task.complete'),0)
        with self.assertRaises(Denied):after.complete(0,True)

    def test_task_readback_wrong_actor_and_cross_firm_fail_closed(self):
        task=self.client._tasks[0]
        actor=self.core._identity(self.editor)
        before=self.core.db.execute(
            'SELECT COALESCE(MAX(seq),0) FROM audit_chain').fetchone()[0]
        self.fence.begin(task_identity=(actor['id'],self.mid,task[0],task[1]),
                         audit_before=before)
        viewer_id,viewer=self.core.provision_user(
            self.core.db.execute('SELECT firm_id FROM users WHERE id=?',
                                 (actor['id'],)).fetchone()[0],'Different Reader')
        self.core.grant(self.author,self.mid,viewer_id,'viewer',
                        self.core.db.execute('SELECT version FROM matters WHERE id=?',
                                             (self.mid,)).fetchone()[0])
        stranger=LocalOperatorController(self.core,viewer,
                                        durable_fence=LocalWriteFence(self.path))
        stranger.list_matters()
        stranger.select(0)
        with self.assertRaises(Denied):
            stranger.reconcile_pending_task_after_restart()
        self.assertTrue(self.fence.is_pending())

    def test_task_reservation_corrupted_fingerprint_never_reconciles(self):
        task=self.client._tasks[0]
        actor=self.core._identity(self.editor)
        before=self.core.db.execute(
            'SELECT COALESCE(MAX(seq),0) FROM audit_chain').fetchone()[0]
        self.fence.begin(task_identity=(actor['id'],self.mid,task[0],task[1]),
                         audit_before=before)
        with sqlite3.connect(self.fence.path) as db:
            db.execute("UPDATE fence SET fingerprint=? WHERE slot=1",('0'*64,))
        after=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        after.list_matters()
        after.select(0)
        self.assertEqual(after.reconcile_pending_task_after_restart().status,
                         'reconciliation_unresolved')
        self.assertTrue(self.fence.is_pending())

    def test_pending_state_survives_restart_without_secrets(self):
        self.fence.begin() # simulate crash after durable reservation
        self.assertTrue(LocalWriteFence(self.path).is_pending())
        second=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        second.list_matters()
        second.select(0)
        self.assertEqual(second.counts(),(0,0))
        with self.assertRaises(Denied):
            second.complete(0,True)
        content=LocalWriteFence(self.path).path.read_bytes()
        for secret in (self.editor,self.author,self.mid,self.eid,
                       'SECRET FICTIONAL MATTER','SECRET FICTIONAL TASK'):
            self.assertNotIn(secret.encode(),content)
        self.assertEqual(self.count('task.complete'),0)

    def test_independent_process_denied_by_existing_pending_bit(self):
        self.fence.begin()
        ctx=multiprocessing.get_context('spawn')
        output=ctx.Queue()
        process=ctx.Process(target=independent_try_begin,args=(self.path,output))
        process.start()
        process.join(12)
        self.assertEqual(process.exitcode,0)
        self.assertEqual(output.get(timeout=2),'denied')
        self.assertTrue(self.fence.is_pending())

    def test_durable_uncertain_review_blocks_restart_until_read_only_proof(self):
        with patch.object(self.client.operator.workflow,'open',
                          side_effect=RuntimeError('Lost postcommit refresh')):
            response=self.client.review(0,'corroborated_manually',
                'Second human confirmed fictional source',True)
        self.assertEqual(response.status,'committed_refresh_unresolved')
        self.assertTrue(LocalWriteFence(self.path).is_pending())
        after=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        after.list_matters()
        after.select(0)
        self.assertEqual(after.counts(),(0,0))
        with self.assertRaises(Denied):after.complete(0,True)
        proof=self.client.reconcile_last_review()
        self.assertEqual(proof.status,'observed_local_commit')
        self.assertFalse(LocalWriteFence(self.path).is_pending())
        after.refresh()
        self.assertEqual(after.counts(),(1,0))
        self.assertEqual(after.complete(0,True).status,'completed_and_refreshed')
        self.assertEqual(self.count('research.second_source_review'),1)
        self.assertEqual(self.count('task.complete'),1)

    def test_corrupted_journal_fails_closed(self):
        self.fence.path.write_bytes(b'not a valid sqlite database')
        with self.assertRaises(Denied):
            self.fence.is_pending()
        with self.assertRaises(Denied):
            self.client.complete(0,True)
        self.assertEqual(self.count('task.complete'),0)

    def test_known_commits_clear_fence_and_cancel_does_not_reserve(self):
        self.assertEqual(self.client.complete(0,False).status,'cancelled')
        self.assertFalse(self.fence.is_pending())
        self.assertEqual(self.client.complete(0,True).status,
                         'completed_and_refreshed')
        self.assertFalse(self.fence.is_pending())
        self.assertEqual(self.count('task.complete'),1)

    def test_actor_recovers_review_identity_after_full_controller_restart(self):
        with patch.object(self.client.operator.workflow,'open',
                          side_effect=RuntimeError('Postcommit window lost')):
            reply=self.client.review(0,'corroborated_manually',
                'Fictional human reviewer inspected offline record',True)
        self.assertEqual(reply.status,'committed_refresh_unresolved')
        self.assertTrue(self.fence.is_pending())
        fresh=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        fresh.list_matters()
        fresh.select(0)
        self.assertEqual(fresh.counts(),(0,0))
        self.assertTrue(fresh.has_recovery())
        recovered=fresh.reconcile_last_review()
        self.assertEqual(recovered.status,'observed_local_commit')
        self.assertIn('after restart',recovered.message)
        self.assertFalse(LocalWriteFence(self.path).is_pending())
        self.assertEqual(self.count('research.second_source_review'),1)
        self.assertEqual(fresh.complete(0,True).status,'completed_and_refreshed')
        self.assertEqual(self.count('research.second_source_review'),1)
        self.assertEqual(self.count('task.complete'),1)

    def test_crash_before_write_does_not_invent_review_commit(self):
        with self.core.lock:
            actor=self.core._identity(self.editor)
            seq=self.core.db.execute(
                'SELECT COALESCE(MAX(seq),0) FROM audit_chain').fetchone()[0]
        oid=self.client._reviews[0][1]
        self.fence.begin(
            review_identity=(actor['id'],self.mid,self.eid,oid),
            audit_before=seq)
        fresh=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        fresh.list_matters()
        fresh.select(0)
        reply=fresh.reconcile_last_review()
        self.assertEqual(reply.status,'reconciliation_unresolved')
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.count('research.second_source_review'),0)
        with self.assertRaises(Denied):
            fresh.complete(0,True)

    def test_restarted_recovery_requires_current_credentials(self):
        with patch.object(self.client.operator.workflow,'open',
                          side_effect=RuntimeError('Lost refresh')):
            self.client.review(0,'corroborated_manually',
                    'Fictional human reviewer inspected record',True)
        self.core.revoke_token(self.editor)
        fresh=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        with self.assertRaises(Denied):
            fresh.list_matters()
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.count('research.second_source_review'),1)

    def test_wrong_firm_and_wrong_account_cannot_reconcile(self):
        with patch.object(self.client.operator.workflow,'open',
                          side_effect=RuntimeError('Lost refresh')):
            self.client.review(0,'corroborated_manually',
                    'Fictional human reviewer inspected record',True)
        other_firm=self.core.provision_firm('Unrelated Fictional Firm')
        _,outsider=self.core.provision_user(other_firm,'Outsider')
        outside=LocalOperatorController(
            self.core,outsider,durable_fence=LocalWriteFence(self.path))
        self.assertEqual(outside.list_matters(),0)
        with self.assertRaises(Invalid):outside.select(0)
        with self.assertRaises(Invalid):outside.reconcile_last_review()
        # A different user in the same matter cannot adopt another review.
        author=LocalOperatorController(
            self.core,self.author,durable_fence=LocalWriteFence(self.path))
        author.list_matters()
        author.select(0)
        self.assertEqual(author.reconcile_last_review().status,
                         'reconciliation_unresolved')
        self.assertTrue(self.fence.is_pending())

    def test_modified_pending_fingerprint_never_unfences(self):
        with patch.object(self.client.operator.workflow,'open',
                          side_effect=RuntimeError('Lost refresh')):
            self.client.review(0,'corroborated_manually',
                    'Fictional human reviewer inspected record',True)
        with sqlite3.connect(str(self.fence.path)) as db:
            db.execute("UPDATE fence SET fingerprint=? WHERE slot=1",('f'*64,))
        fresh=LocalOperatorController(
            self.core,self.editor,durable_fence=LocalWriteFence(self.path))
        fresh.list_matters()
        fresh.select(0)
        self.assertEqual(fresh.reconcile_last_review().status,
                         'reconciliation_unresolved')
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.count('research.second_source_review'),1)

    def test_deleted_fence_sidecar_cannot_be_silently_recreated(self):
        self.fence.begin()
        self.fence.path.unlink()
        with self.assertRaises(Denied):
            LocalWriteFence(self.path)
        with self.assertRaises(Denied):
            self.fence.is_pending()
        with self.assertRaises(Denied):
            self.client.complete(0,True)
        self.assertEqual(self.count('task.complete'),0)

    def test_replaced_sidecar_marker_cannot_be_adopted(self):
        self.fence.begin()
        self.fence.path.unlink()
        with sqlite3.connect(str(self.fence.path)) as db:
            db.execute("CREATE TABLE fence_marker(slot INTEGER PRIMARY KEY,marker TEXT)")
            db.execute("INSERT INTO fence_marker VALUES(1,?)",('forged',))
        with self.assertRaises(Denied):
            LocalWriteFence(self.path)
        with self.assertRaises(Denied):
            self.client.complete(0,True)
        self.assertEqual(self.count('task.complete'),0)

    def test_correct_existing_fence_reopens_with_same_binding(self):
        another=LocalWriteFence(self.path)
        self.assertFalse(another.is_pending())
        another.begin()
        self.assertTrue(self.fence.is_pending())
        with self.assertRaises(Denied):
            LocalWriteFence(self.path).begin()
        self.assertEqual(self.count('task.complete'),0)

    def test_stale_cas_cannot_clear_newer_reservation(self):
        old=self.fence.begin()
        self.assertEqual(old,LocalWriteFence(self.path).pending_reservation())
        self.fence.finish_confirmed(expected_reservation=old)
        current=LocalWriteFence(self.path).begin()
        self.assertNotEqual(old,current)
        with self.assertRaises(Denied):
            self.fence.finish_confirmed(expected_reservation=old)
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.fence.pending_reservation(),current)
        self.fence.finish_confirmed(expected_reservation=current)
        self.assertFalse(self.fence.is_pending())
        self.assertEqual(self.count('task.complete'),0)

    def test_empty_or_forged_reservation_never_clears_hold(self):
        held=self.fence.begin()
        for value in (None, '', '0'*64, 'X'*64, held[:-1]):
            with self.subTest(value=value):
                with self.assertRaises(Denied):
                    self.fence.finish_confirmed(expected_reservation=value)
                self.assertEqual(self.fence.pending_reservation(),held)
        self.assertEqual(self.count('task.complete'),0)

    def test_recovery_does_not_clear_reservation_swapped_after_proof(self):
        with patch.object(self.client.operator.workflow,'open',
                          side_effect=RuntimeError('Postcommit refresh lost')):
            outcome=self.client.review(0,'corroborated_manually',
                'Fictional reviewer verified independently',True)
        self.assertEqual(outcome.status,'committed_refresh_unresolved')
        original=self.client.operator.reconcile_research
        new_ids=[]
        def concurrent_switch(*args,**kwargs):
            proof=original(*args,**kwargs)
            prior=self.fence.pending_reservation()
            self.fence.finish_confirmed(expected_reservation=prior)
            new_ids.append(LocalWriteFence(self.path).begin())
            return proof
        with patch.object(self.client.operator,'reconcile_research',
                          side_effect=concurrent_switch):
            with self.assertRaises(Denied):
                self.client.reconcile_last_review()
        self.assertEqual(self.fence.pending_reservation(),new_ids[0])
        self.assertEqual(self.count('research.second_source_review'),1)
        self.assertEqual(self.count('task.complete'),0)

    def test_missing_reservation_version_requires_incident_handling(self):
        held=self.fence.begin()
        with sqlite3.connect(str(self.fence.path)) as db:
            db.execute("UPDATE fence SET reservation=NULL WHERE slot=1")
        with self.assertRaises(Denied):
            LocalWriteFence(self.path).pending_reservation()
        with self.assertRaises(Denied):
            self.fence.finish_confirmed(expected_reservation=held)
        self.assertTrue(self.fence.is_pending())

    def test_unresolved_recovery_never_auto_clears(self):
        from types import SimpleNamespace
        with patch.object(self.client.operator.workflow,'open',
                          side_effect=RuntimeError('Lost refresh')):
            self.client.review(0,'corroborated_manually',
                    'Second human confirmed fictional source',True)
        with patch.object(self.client.operator,'reconcile_research',
                          return_value=SimpleNamespace(status='unresolved')):
            self.assertEqual(self.client.reconcile_last_review().status,
                             'reconciliation_unresolved')
        self.assertTrue(LocalWriteFence(self.path).is_pending())
        with self.assertRaises(Denied):
            self.client.complete(0,True)
        self.assertEqual(self.count('task.complete'),0)


if __name__=='__main__':
    unittest.main()
