"""Offline fictional signed-checkpoint fixture; NO independent custody claim."""
import hashlib
import hmac
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from src.secure_engine import SecureCore, Denied, Invalid
from src.durable_local_write_fence import LocalWriteFence
from src.independent_checkpoint_boundary import (
    CheckpointReadbackBoundary, PinnedCheckpoint, _digest)
from src.task_external_anchor import compare_task_to_checkpoint

TEST_KEY=b'fictional-key-never-for-production'
PIN=PinnedCheckpoint(17,'a'*64,'fictional-external-witness')


class FixtureReader:
    def __init__(self, event_digest, reservation):
        head={'sequence':18,'previous':PIN.digest,
              'event_digest':event_digest,
              'reservation_digest':_digest({'reservation':reservation}),
              'signer_id':PIN.signer_id}
        payload=json.dumps(head,sort_keys=True,separators=(',',':'),
                           ensure_ascii=True).encode('ascii')
        head['signature']=hmac.new(TEST_KEY,payload,hashlib.sha256).hexdigest()
        self.head=head
        self.event={'sequence':18,'reservation_digest':head['reservation_digest'],
                    'event_digest':event_digest,'commit_state':'committed'}
    def read_head(self):
        return dict(self.head)
    def read_event(self, seq):
        return dict(self.event)


def test_signature(signer,payload,signature):
    return (signer==PIN.signer_id and hmac.compare_digest(
        hmac.new(TEST_KEY,payload,hashlib.sha256).hexdigest(),signature))


class TaskExternalAnchorConsistency(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'fictional.sqlite3'
        self.core=SecureCore(self.path)
        firm=self.core.provision_firm('Fictional Legal Office')
        self.uid,self.token=self.core.provision_user(firm,'Fictional Attorney')
        self.matter=self.core.create_matter(self.token,'Fictional Private Matter')['id']
        self.task=self.core.create_task(
            self.token,self.matter,'Fictional Task','2026-10-01T00:00:00Z')['id']
        self.fence=LocalWriteFence(self.path)
        before=self.core.audit_head()['seq']
        self.reservation=self.fence.begin(
            task_identity=(self.uid,self.matter,self.task,1),
            audit_before=before)
        # A frozen pre-write snapshot, separately from the still-running DB.
        self.snapshot_db=Path(self.tmp.name)/'prewrite.sqlite3'
        with sqlite3.connect(self.snapshot_db) as copy:
            self.core.db.backup(copy)
        self.snapshot_sidecar=Path(self.tmp.name)/'prewrite-fence.sqlite3'
        shutil.copy2(self.fence.path,self.snapshot_sidecar)
        self.core.complete_task(self.token,self.task,1)
        self.reader=FixtureReader(self.event_digest(),self.reservation)
        self.boundary=CheckpointReadbackBoundary(
            provider=self.reader,verify_signature=test_signature,pinned=PIN)

    def tearDown(self):
        self.core.close()

    def event_digest(self):
        events=self.core.db.execute(
            "SELECT seq,row_hash FROM audit_chain WHERE action='task.complete' "
            "AND target=?",(self.task,)).fetchall()
        self.assertEqual(len(events),1)
        head=self.core.audit_head()
        return _digest({
            'schema':'mtl.task.audit.anchor.v1',
            'matter_id':self.matter,
            'task_id':self.task,
            'expected_version':1,
            'task_event_seq':events[0]['seq'],
            'task_event_hash':events[0]['row_hash'],
            'audit_head_seq':head['seq'],
            'audit_head_hash':head['row_hash'],
        })

    def observe(self, token=None):
        return compare_task_to_checkpoint(
            self.core,self.token if token is None else token,
            self.matter,self.task,1,reservation=self.reservation,
            boundary=self.boundary)

    def test_matching_signed_fixture_is_observational_only(self):
        result=self.observe()
        self.assertEqual(result.status,'local_and_signed_checkpoint_consistent')
        self.assertEqual(result.checkpoint_sequence,18)
        self.assertFalse(result.independently_custodied)
        self.assertFalse(result.permits_write_replay)
        self.assertFalse(result.permits_fence_clearance)
        self.assertTrue(self.fence.is_pending())

    def test_provider_readback_never_holds_local_core_lock(self):
        import threading
        observed=[]
        parent=self
        original=self.reader.read_head
        def challenged_read_head():
            done=threading.Event()
            def independent_local_read():
                try:
                    parent.core.audit_head()
                    observed.append('local_read_completed')
                finally:
                    done.set()
            worker=threading.Thread(target=independent_local_read)
            worker.start()
            if not done.wait(2):
                raise TimeoutError('Provider read blocked by application lock')
            worker.join(timeout=2)
            return original()
        self.reader.read_head=challenged_read_head
        result=self.observe()
        self.assertEqual(result.status,'local_and_signed_checkpoint_consistent')
        self.assertEqual(observed,['local_read_completed'])
        self.assertTrue(self.fence.is_pending())

    def test_fictional_readback_latency_p50_p95_report(self):
        import statistics
        import time
        samples=[]
        for _ in range(30):
            started=time.perf_counter_ns()
            observed=self.observe()
            self.assertFalse(observed.permits_fence_clearance)
            samples.append((time.perf_counter_ns()-started)/1_000_000)
        ordered=sorted(samples)
        p50=statistics.median(ordered)
        p95=ordered[max(0,int(len(ordered)*0.95+0.999999)-1)]
        self.assertGreaterEqual(p95,0)
        self.assertGreaterEqual(p95,p50)
        print('FICTIONAL TASK ANCHOR LATENCY ms: n=30 p50=%.3f p95=%.3f max=%.3f'%
              (p50,p95,max(samples)),flush=True)

    def test_authorization_revoked_during_provider_readback_denied(self):
        original=self.reader.read_head
        def revoke_during_readback():
            self.core.revoke_token(self.token)
            return original()
        self.reader.read_head=revoke_during_readback
        with self.assertRaises(Denied):
            self.observe()
        self.assertTrue(self.fence.is_pending())

    def test_local_audit_mutation_during_provider_readback_denied(self):
        original=self.reader.read_head
        def concurrent_audit_mutation():
            self.core.create_task(
                self.token,self.matter,'Fictional competing task',
                '2026-10-01T00:00:00Z')
            return original()
        self.reader.read_head=concurrent_audit_mutation
        with self.assertRaises(Denied):
            self.observe()
        self.assertTrue(self.fence.is_pending())

    def test_privilege_downgrade_during_provider_readback_denied(self):
        original=self.reader.read_head
        # A controlled direct ACL mutation models an independent administrator
        # changing the grant while signed readback is in progress.
        def downgrade():
            self.core.db.execute(
                "UPDATE grants SET role='viewer' WHERE matter_id=? AND user_id=?",
                (self.matter,self.uid))
            return original()
        self.reader.read_head=downgrade
        with self.assertRaises(Denied):
            self.observe()
        self.assertTrue(self.fence.is_pending())

    def test_coordinated_database_and_sidecar_rollback_is_detected(self):
        self.core.close()
        shutil.copy2(self.snapshot_db,self.path)
        shutil.copy2(self.snapshot_sidecar,self.fence.path)
        self.core=SecureCore(self.path)
        self.fence=LocalWriteFence(self.path)
        self.assertTrue(self.fence.is_pending())
        with self.assertRaises((Denied,Invalid)):
            self.observe()
        self.assertTrue(self.fence.is_pending())
        self.assertEqual(self.core.db.execute(
            'SELECT completed FROM tasks WHERE id=?',(self.task,)).fetchone()[0],0)

    def test_unauthorized_actor_and_revoked_session_fail_closed(self):
        _,other=self.core.provision_user(
            self.core.db.execute('SELECT id FROM firms LIMIT 1').fetchone()[0],
            'Different Attorney')
        with self.assertRaises(Denied):
            self.observe(other)
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):
            self.observe()
        self.assertTrue(self.fence.is_pending())

    def test_wrong_signer_or_tampered_signed_event_is_denied(self):
        self.reader.head['signer_id']='rogue-witness'
        with self.assertRaises(Denied):
            self.observe()
        self.assertTrue(self.fence.is_pending())

    def test_locally_forged_audit_head_rejected(self):
        self.core.db.execute(
            "UPDATE audit_chain SET row_hash=? WHERE action='task.complete'",
            ('0'*64,))
        with self.assertRaises((Denied,Invalid)):
            self.observe()
        self.assertTrue(self.fence.is_pending())


if __name__=='__main__':
    unittest.main()
