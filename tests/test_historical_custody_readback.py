"""Offline signed history recovery: fictional signer and local SQLite ONLY."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.checkpoint_admission_prototype import LocalCheckpointAdmissionPrototype
from src.historical_custody_readback import HistoricalCustodyReadback
from src.independent_checkpoint_boundary import PinnedCheckpoint
from src.secure_engine import Denied
from test_checkpoint_admission_prototype import PIN,sign,verify


class HistoricalSignedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'fictional-checkpoints.sqlite3'
        self.provider=LocalCheckpointAdmissionPrototype(
            self.path,genesis=PIN,authenticate=lambda c:c=='test-credential',
            sign=sign,signer_id=PIN.signer_id)
        self.reservations=[]
        self.events=[]
        predecessor=PIN
        for n in range(3):
            res=('%064x'%(101+n))
            nonce=('%064x'%(201+n))
            event=('%064x'%(301+n))
            ack=self.provider.admit(
                credential='test-credential',reservation=res,nonce=nonce,
                event_digest=event,expected=predecessor)
            self.reservations.append(res)
            self.events.append(event)
            predecessor=PinnedCheckpoint(
                ack['sequence'],ack['head_digest'],PIN.signer_id)
        self.latest=predecessor

    def gate(self,provider=None,predecessor=None,latest=None):
        return HistoricalCustodyReadback(
            provider=self.provider if provider is None else provider,
            verify_signature=verify,
            predecessor=PIN if predecessor is None else predecessor,
            retained_latest=self.latest if latest is None else latest)

    def recover(self,idx=1,gate=None):
        return (self.gate() if gate is None else gate).verify(
            reservation=self.reservations[idx],event_digest=self.events[idx])

    def test_lost_ack_historical_middle_operation_readback(self):
        found=self.recover()
        self.assertEqual((found.operation_sequence,found.latest_sequence,
                          found.inspected_events),(2,3,3))
        self.assertFalse(found.independently_custodied)
        self.assertFalse(found.nonce_authenticated)
        self.assertFalse(found.permits_write_replay)
        self.assertFalse(found.permits_fence_clearance)

    def test_first_and_last_operations_are_both_recoverable(self):
        self.assertEqual(self.recover(0).operation_sequence,1)
        self.assertEqual(self.recover(2).operation_sequence,3)

    def test_exact_mismatched_identity_and_missing_event_denied(self):
        with self.assertRaises(Denied):
            self.gate().verify(reservation='f'*64,event_digest=self.events[1])
        with self.assertRaises(Denied):
            self.gate().verify(reservation=self.reservations[1],event_digest='f'*64)

    def test_signed_intermediate_head_corruption_denied(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute("UPDATE checkpoint_events SET signature=? WHERE sequence=2",
                         ('0'*64,))
        with self.assertRaises(Denied):self.recover()

    def test_coordinated_local_db_rollback_vs_external_tip_denied(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute('DELETE FROM checkpoint_events WHERE sequence=3')
        with self.assertRaises(Denied):self.recover()

    def test_stale_external_tip_and_signer_rotation_denied(self):
        with self.assertRaises(Denied):
            self.recover(gate=self.gate(latest=PinnedCheckpoint(
                2,'f'*64,PIN.signer_id)))
        with self.assertRaises(Denied):
            self.gate(latest=PinnedCheckpoint(
                3,self.latest.digest,'unauthorized-signer'))

    def test_history_exceeding_strict_bound_denied(self):
        with self.assertRaises(Denied):
            HistoricalCustodyReadback(
                provider=self.provider,verify_signature=verify,
                predecessor=PIN,retained_latest=self.latest,max_events=2)

    def test_current_head_changed_during_readback_denied(self):
        class Switched:
            def __init__(self,actual):
                self.actual=actual
                self.calls=0
            def read_head(self):
                self.calls+=1
                out=self.actual.read_head()
                if self.calls==2:
                    out['event_digest']='f'*64
                return out
            def read_head_at(self,seq):
                return self.actual.read_head_at(seq)
            def read_event(self,seq):
                return self.actual.read_event(seq)
        with self.assertRaises(Denied):
            self.recover(gate=self.gate(provider=Switched(self.provider)))

    def test_duplicate_signed_reservation_event_fails_ambiguity(self):
        # Cannot legitimately create a duplicate through atomic admission.
        # Fault-inject inconsistent DB history to exercise deny semantics.
        with sqlite3.connect(self.path) as conn:
            conn.execute('UPDATE checkpoint_events SET reservation_digest=('
                         'SELECT reservation_digest FROM checkpoint_events '
                         'WHERE sequence=2) WHERE sequence=3')
        with self.assertRaises(Denied):self.recover()


if __name__=='__main__':
    unittest.main()
