"""Controlled offline witness-admission tests; no independent provider involved."""
import hmac
import hashlib
import sqlite3
import threading
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from src.checkpoint_admission_prototype import LocalCheckpointAdmissionPrototype
from src.independent_checkpoint_boundary import (
    CheckpointReadbackBoundary, PinnedCheckpoint, _digest)
from src.secure_engine import Denied

KEY=b"synthetic-only-test-key-not-a-production-signing-secret"
PIN=PinnedCheckpoint(0,"a"*64,"synthetic-signer")
RESERVATION="b"*64
NONCE="c"*64
EVENT="d"*64


def sign(signer,data):
    if signer != PIN.signer_id:
        raise ValueError('wrong synthetic signer')
    return hmac.new(KEY,data,hashlib.sha256).hexdigest()


def verify(signer,data,signature):
    return signer == PIN.signer_id and hmac.compare_digest(sign(signer,data),signature)


class CheckpointAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"fictional-witness.sqlite3"
        self.auth_valid=True
        self.service=self.new_service()

    def tearDown(self):
        self.temp.cleanup()

    def new_service(self, **kwargs):
        return LocalCheckpointAdmissionPrototype(
            self.path,genesis=PIN,
            authenticate=kwargs.get('authenticate',
                                    lambda credential: credential=="synthetic-only" and self.auth_valid),
            sign=kwargs.get('sign',sign),signer_id=PIN.signer_id)

    def admit(self,**kwargs):
        args={'credential':'synthetic-only','reservation':RESERVATION,
              'nonce':NONCE,'event_digest':EVENT,'expected':PIN}
        args.update(kwargs)
        return self.service.admit(**args)

    def reader(self,pin=PIN,verifier=verify):
        return CheckpointReadbackBoundary(
            provider=self.service,pinned=pin,verify_signature=verifier)

    def test_atomic_admission_requires_separate_pinned_readback(self):
        ack=self.admit()
        self.assertEqual(ack['sequence'],1)
        observed=self.reader().verify(
            reservation=RESERVATION,event_digest=EVENT,proposal=ack)
        self.assertEqual(observed.sequence,1)
        self.assertFalse(observed.independently_custodied)

    def test_duplicate_nonce_and_reservation_fail_closed(self):
        self.admit()
        for args in ({'reservation':'e'*64},
                     {'nonce':'e'*64}):
            with self.subTest(args=args),self.assertRaises(Denied):
                self.admit(**args)
        self.assertEqual(self.service.read_head()['sequence'],1)

    def test_stale_pin_and_skipped_sequence_denied(self):
        self.admit()
        with self.assertRaises(Denied):
            self.admit(nonce='e'*64,reservation='e'*64)
        with self.assertRaises(Denied):
            self.admit(nonce='e'*64,reservation='e'*64,
                       expected=PinnedCheckpoint(2,"f"*64,PIN.signer_id))

    def test_reauthentication_is_required_for_each_admission(self):
        self.auth_valid=False
        with self.assertRaises(Denied):self.admit()
        self.auth_valid=True
        self.assertEqual(self.admit()['sequence'],1)

    def test_revoked_signer_blocks_new_admissions(self):
        self.service.revoke_signer()
        with self.assertRaises(Denied):self.admit()
        self.new_service()
        with self.assertRaises(Denied):self.admit()

    def test_signer_failure_rolls_back_nonce_and_head(self):
        def error_sign(*args):
            raise RuntimeError('Synthetic signer unavailable')
        self.service=self.new_service(sign=error_sign)
        with self.assertRaises(Denied):self.admit()
        with sqlite3.connect(str(self.path)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM checkpoint_events').fetchone()[0],0)
        self.service=self.new_service()
        self.assertEqual(self.admit()['sequence'],1)

    def test_invalid_signature_output_is_not_committed(self):
        self.service=self.new_service(sign=lambda *a:None)
        with self.assertRaises(Denied):self.admit()
        self.service=self.new_service()
        self.assertEqual(self.admit()['sequence'],1)

    def test_lost_acknowledgment_reconciled_by_readback_not_replay(self):
        ack=self.admit()
        del ack  # caller loses response after commitment
        with self.assertRaises(Denied):self.admit()
        self.assertEqual(self.reader().verify(
            reservation=RESERVATION,event_digest=EVENT).sequence,1)

    def test_forged_signature_fails_readback(self):
        self.admit()
        with sqlite3.connect(str(self.path)) as db:
            db.execute("UPDATE checkpoint_events SET signature='0' WHERE sequence=1")
        with self.assertRaises(Denied):
            self.reader().verify(reservation=RESERVATION,event_digest=EVENT)

    def test_conflicting_committed_readback_denied(self):
        self.admit()
        with sqlite3.connect(str(self.path)) as db:
            db.execute("UPDATE checkpoint_events SET event_digest=? WHERE sequence=1",
                       ('f'*64,))
        with self.assertRaises(Denied):
            self.reader().verify(reservation=RESERVATION,event_digest=EVENT)

    def test_concurrent_operators_at_same_pin_admit_only_one(self):
        barrier=threading.Barrier(2)
        out=[]
        def attempt(reservation,nonce):
            barrier.wait()
            try:
                out.append(('ok',self.admit(reservation=reservation,nonce=nonce)))
            except Denied:
                out.append(('denied',None))
        t1=threading.Thread(target=attempt,args=('b'*64,'c'*64))
        t2=threading.Thread(target=attempt,args=('e'*64,'f'*64))
        t1.start();t2.start();t1.join(10);t2.join(10)
        self.assertEqual(sorted(x[0] for x in out),['denied','ok'])
        self.assertEqual(self.service.read_head()['sequence'],1)

    def test_provider_database_rollback_detected_only_by_external_pin(self):
        # Local history is reversible. Caller MUST retain its pin independently.
        ack1=self.admit()
        seen=self.reader().verify(reservation=RESERVATION,event_digest=EVENT,proposal=ack1)
        local_pin=PinnedCheckpoint(seen.sequence,seen.head_digest,PIN.signer_id)
        self.path.unlink()  # synthetic whole-history removal / rewind
        reset=self.new_service()
        ack2=reset.admit(credential='synthetic-only',reservation='e'*64,
                         nonce='f'*64,event_digest='f'*64,expected=PIN)
        self.assertEqual(ack2['sequence'],1)
        with self.assertRaises(Denied):
            CheckpointReadbackBoundary(
                provider=reset,pinned=local_pin,
                verify_signature=verify).verify(reservation='e'*64,event_digest='f'*64)
        # Old, rolled-back pin would NOT detect substitution; no independent
        # rollback resistance claim is allowed from a mutable SQLite provider.

    def test_genesis_or_signer_substitution_fails_closed(self):
        with self.assertRaises(Denied):
            LocalCheckpointAdmissionPrototype(
                self.path,genesis=PinnedCheckpoint(0,'f'*64,PIN.signer_id),
                authenticate=lambda x:True,sign=sign,signer_id=PIN.signer_id)
        with self.assertRaises(Denied):
            LocalCheckpointAdmissionPrototype(
                self.path,genesis=PIN,authenticate=lambda x:True,
                sign=sign,signer_id='different-signer')

    def test_pinned_successor_allows_next_atomic_event_only(self):
        first=self.admit()
        result=self.reader().verify(
            reservation=RESERVATION,event_digest=EVENT,proposal=first)
        pinned=PinnedCheckpoint(result.sequence,result.head_digest,PIN.signer_id)
        second=self.admit(reservation='e'*64,nonce='f'*64,event_digest='f'*64,
                          expected=pinned)
        next_result=self.reader(pin=pinned).verify(
            reservation='e'*64,event_digest='f'*64,proposal=second)
        self.assertEqual(next_result.sequence,2)
        with self.assertRaises(Denied):
            self.reader().verify(reservation=RESERVATION,event_digest=EVENT)


if __name__=="__main__":
    unittest.main()
