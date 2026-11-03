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
