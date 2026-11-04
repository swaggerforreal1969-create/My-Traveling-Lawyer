"""Strict fictional signed v2 nonce identity acceptance; v1 is unchanged."""
import hashlib
import hmac
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from src.nonce_bound_custody import OfflineNonceBoundCustody
from src.independent_checkpoint_boundary import PinnedCheckpoint
from src.secure_engine import Denied

KEY=b'fictional-v2-hmac-test-only'
PIN=PinnedCheckpoint(0,'a'*64,'fictional-v2-signer')


def sign(signer,data):
    if signer!=PIN.signer_id:raise ValueError('Wrong fixture signer')
    return hmac.new(KEY,data,hashlib.sha256).hexdigest()


def verify(signer,data,sig):
    return signer==PIN.signer_id and hmac.compare_digest(
        hmac.new(KEY,data,hashlib.sha256).hexdigest(),sig)


class NonceBoundReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'v2-fixture.sqlite3'
        self.authorized=True
        self.provider=self.open()
        self.ops=[]
        current=PIN
        for number in range(3):
            nonce='%064x'%(100+number)
            reservation='%064x'%(200+number)
            event='%064x'%(300+number)
            ack=self.provider.admit_once(
                credential='fixture-authorized',nonce=nonce,
                reservation=reservation,event_digest=event,expected=current,
                explicitly_authorized=True)
            self.ops.append((nonce,reservation,event))
            current=PinnedCheckpoint(
                ack['sequence'],ack['head_digest'],PIN.signer_id)
        self.latest=current

    def open(self,**kwargs):
        return OfflineNonceBoundCustody(
            self.path,genesis=PIN,
            authenticate=kwargs.get('authenticate',
                lambda c:c=='fixture-authorized' and self.authorized),
            sign=kwargs.get('sign',sign),
            verify_signature=kwargs.get('verify_signature',verify))

    def recover(self,index=1,**kwargs):
        nonce,reservation,event=self.ops[index]
        args={'nonce':nonce,'reservation':reservation,'event_digest':event,
              'predecessor':PIN,'retained_latest':self.latest}
        args.update(kwargs)
        return self.provider.read_historical(**args)

    def test_exact_historical_nonce_covered_by_signature(self):
        result=self.recover()
        self.assertTrue(result.nonce_authenticated)
        self.assertEqual((result.sequence,result.latest_sequence),(2,3))
        self.assertFalse(result.independently_custodied)
        self.assertFalse(result.permits_write_replay)
        self.assertFalse(result.permits_fence_clearance)

    def test_nonce_substitution_and_wrong_reservation_event_fail(self):
        with self.assertRaises(Denied):
            self.recover(nonce='f'*64)
        with self.assertRaises(Denied):
            self.recover(reservation='f'*64)
        with self.assertRaises(Denied):
            self.recover(event_digest='f'*64)

    def test_signed_nonce_tamper_without_resigning_denied(self):
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE custody_v2_events SET nonce_digest=? '
                       'WHERE sequence=2',('f'*64,))
        with self.assertRaises(Denied):self.recover()

    def test_two_competing_admissions_one_cas_winner(self):
        results=[]
        barrier=threading.Barrier(2)
        def attempt(i):
            barrier.wait()
            try:
                self.provider.admit_once(
                    credential='fixture-authorized',
                    nonce='%064x'%(400+i),
                    reservation='%064x'%(500+i),
                    event_digest='%064x'%(600+i),expected=self.latest,
                    explicitly_authorized=True)
                results.append('admitted')
            except Denied:
                results.append('denied')
        a=threading.Thread(target=attempt,args=(1,))
        b=threading.Thread(target=attempt,args=(2,))
        a.start();b.start();a.join(10);b.join(10)
        self.assertEqual(sorted(results),['admitted','denied'])
        with self.assertRaises(Denied):
            self.recover()  # held latest anchor is now stale

    def test_duplicate_nonce_and_reservation_rejected(self):
        args=dict(credential='fixture-authorized',
                  nonce=self.ops[1][0],reservation='f'*64,
                  event_digest='e'*64,expected=self.latest,
                  explicitly_authorized=True)
        with self.assertRaises(Denied):
            self.provider.admit_once(**args)
        args['nonce']='f'*64
        args['reservation']=self.ops[1][1]
        with self.assertRaises(Denied):
            self.provider.admit_once(**args)

    def test_revoked_signer_and_credential_denied(self):
        self.authorized=False
        with self.assertRaises(Denied):
            self.provider.admit_once(
                credential='fixture-authorized',nonce='f'*64,
                reservation='f'*64,event_digest='f'*64,
                expected=self.latest,explicitly_authorized=True)
        self.authorized=True
        self.provider.revoke()
        with self.assertRaises(Denied):
            self.provider.admit_once(
                credential='fixture-authorized',nonce='f'*64,
                reservation='f'*64,event_digest='f'*64,
                expected=self.latest,explicitly_authorized=True)

    def test_rollback_and_stale_tip_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM custody_v2_events WHERE sequence=3')
        with self.assertRaises(Denied):self.recover()

    def test_v1_cannot_be_misread_as_v2_nonce_authenticated(self):
        # The v1 table uses a different schema and has no signed nonce.
        from src.checkpoint_admission_prototype import LocalCheckpointAdmissionPrototype
        legacy=LocalCheckpointAdmissionPrototype(
            self.path,genesis=PinnedCheckpoint(0,'b'*64,'fixture-v1'),
            authenticate=lambda x:True,
            sign=lambda a,b:'f'*64,signer_id='fixture-v1')
        legacy.admit(credential='fixture',reservation='f'*64,nonce='f'*64,
                     event_digest='f'*64,
                     expected=PinnedCheckpoint(0,'b'*64,'fixture-v1'))
        self.assertEqual(self.recover().sequence,2)
        with sqlite3.connect(self.path) as db:
            legacy_count=db.execute('SELECT count(*) FROM checkpoint_events').fetchone()[0]
            modern_count=db.execute('SELECT count(*) FROM custody_v2_events').fetchone()[0]
        self.assertEqual((legacy_count,modern_count),(1,3))

    def test_signer_failure_atomic_rollback(self):
        self.provider=self.open(sign=lambda *a: (_ for _ in ()).throw(
            RuntimeError('offline signer failed')))
        with self.assertRaises(Denied):
            self.provider.admit_once(
                credential='fixture-authorized',nonce='f'*64,
                reservation='f'*64,event_digest='f'*64,
                expected=self.latest,explicitly_authorized=True)
        self.provider=self.open()
        self.assertEqual(self.recover().sequence,2)

    def test_bounded_recovery_performance_fictional(self):
        samples=[]
        for _ in range(30):
            started=time.perf_counter()
            self.assertEqual(self.recover().sequence,2)
            samples.append((time.perf_counter()-started)*1000)
        samples.sort()
        print('FICTIONAL V2 HISTORICAL RECOVERY ms n=30 '
              'p50=%.3f p95-nearest=%.3f max=%.3f'%(
              (samples[14]+samples[15])/2,samples[28],samples[-1]),
              flush=True)


if __name__=='__main__':
    unittest.main()
