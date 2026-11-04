"""Fictional ephemeral-key Ed25519 v2 provider-conformance acceptance.

Test private keys are generated in RAM only. No production key, identity,
external service, network, or independently managed custody is involved.
"""
import hashlib
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from src.independent_checkpoint_boundary import PinnedCheckpoint
from src.nonce_bound_custody import OfflineNonceBoundCustody, SCHEMA
from src.provider_neutral_custody_client import AuthenticatedCustodyTransport
from src.v2_custody_transport import NonceBoundCustodyClientV2
from src.v2_asymmetric_trust import PinnedEd25519Trust, PinnedEd25519Verifier
from src.secure_engine import Denied

SIGNER='fictional-ed25519-v2-signer'
GENESIS=PinnedCheckpoint(0,'a'*64,SIGNER)


class FictionalAsymmetricCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/'fictional-v2.sqlite3'
        self.private=Ed25519PrivateKey.generate()
        raw=self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw)
        self.trust=PinnedEd25519Trust(
            signer_id=SIGNER,public_key_raw=raw,
            public_key_sha256=hashlib.sha256(raw).hexdigest(),
            valid_from=100,valid_until=1000)
        self.verifier=PinnedEd25519Verifier(trust=self.trust,evaluated_at=500)
        self.authorized=True
        self.provider=OfflineNonceBoundCustody(
            self.db,genesis=GENESIS,
            authenticate=lambda cred:cred=='fixture-authorized' and self.authorized,
            sign=lambda sid,payload:self.private.sign(payload).hex()
                if sid==SIGNER else (_ for _ in ()).throw(ValueError('signer')),
            verify_signature=self.verifier)
        self.history=[]
        tip=GENESIS
        for seq in range(1,4):
            nonce='%064x'%(100+seq)
            reservation='%064x'%(200+seq)
            event='%064x'%(300+seq)
            ack=self.provider.admit_once(
                credential='fixture-authorized',nonce=nonce,
                reservation=reservation,event_digest=event,
                expected=tip,explicitly_authorized=True)
            self.history.append((nonce,reservation,event))
            tip=PinnedCheckpoint(ack['sequence'],ack['head_digest'],SIGNER)
        self.latest=tip
        self.calls=[]
        self.revoked=False
        self.drift=False
        self.head_reads=0
        self.transport=AuthenticatedCustodyTransport(
            request=self.exchange,transport_authenticated=True)
        self.client=NonceBoundCustodyClientV2(
            transport=self.transport,predecessor=GENESIS,
            verify_signature=self.verifier)

    def exchange(self,action,body):
        self.calls.append(action)
        if self.revoked or body.get('credential')!='fictional-reader':
            raise Denied('Fixture credential denied')
        if body.get('schema')!=SCHEMA:
            raise Denied('Fixture protocol version rejected')
        if action=='v2_read_latest':
            self.head_reads+=1
            with sqlite3.connect(self.db) as db:
                row=db.execute('SELECT sequence,head_digest '
                    'FROM custody_v2_events ORDER BY sequence DESC LIMIT 1').fetchone()
            if self.drift and self.head_reads==2:
                return {'sequence':row[0],'head_digest':'f'*64}
            return {'sequence':row[0],'head_digest':row[1]}
        if action=='v2_read_head_at':
            return self.provider._head_at(body['sequence'])
        if action=='v2_admit':
            expected=body['expected']
            return self.provider.admit_once(
                credential='fixture-authorized',nonce=body['nonce'],
                reservation=body['reservation'],
                event_digest=body['event_digest'],
                expected=PinnedCheckpoint(expected['sequence'],expected['digest'],
                                          expected['signer_id']),
                explicitly_authorized=True)
        raise Denied('Unsupported fixture operation')

    def read(self,**kw):
        nonce,res,event=self.history[1]
        args=dict(credential='fictional-reader',nonce=nonce,
                  reservation=res,event_digest=event,
                  retained_latest=self.latest)
        args.update(kw)
        return self.client.reconcile_read_only(**args)

    def test_verified_three_generation_asymmetric_signed_nonce(self):
        observation=self.read()
        self.assertEqual((observation.sequence,observation.latest_sequence),(2,3))
        self.assertTrue(observation.nonce_authenticated)
        self.assertFalse(observation.independently_custodied)
        self.assertFalse(observation.permits_write_replay)
        self.assertFalse(observation.permits_fence_clearance)

    def test_wrong_public_key_even_with_same_signer_label_denied(self):
        unrelated=Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        pin=PinnedEd25519Trust(
            SIGNER,unrelated,hashlib.sha256(unrelated).hexdigest(),100,1000)
        client=NonceBoundCustodyClientV2(
            transport=self.transport,predecessor=GENESIS,
            verify_signature=PinnedEd25519Verifier(trust=pin,evaluated_at=500))
        nonce,res,event=self.history[1]
        with self.assertRaises(Denied):
            client.reconcile_read_only(
                credential='fictional-reader',nonce=nonce,
                reservation=res,event_digest=event,retained_latest=self.latest)

    def test_wrong_signer_identity_and_incorrect_fingerprint_denied(self):
        with self.assertRaises(Denied):
            PinnedEd25519Trust(
                SIGNER,self.trust.public_key_raw,'0'*64,100,1000)
        self.assertFalse(self.verifier('replaced-signer',b'payload','0'*128))
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE custody_v2_events SET signer_id=? WHERE sequence=2",
                       ('replaced-signer',))
        with self.assertRaises(Denied):self.read()

    def test_expired_not_yet_valid_and_revoked_keys_denied(self):
        for when in (99,1000,1001):
            with self.subTest(when=when),self.assertRaises(Denied):
                PinnedEd25519Verifier(trust=self.trust,evaluated_at=when)
        from dataclasses import replace
        with self.assertRaises(Denied):
            PinnedEd25519Verifier(trust=replace(self.trust,revoked=True),
                                  evaluated_at=500)

    def test_nonce_replay_stale_tip_and_signed_history_tamper_denied(self):
        with self.assertRaises(Denied):self.read(nonce='f'*64)
        with self.assertRaises(Denied):
            self.read(retained_latest=PinnedCheckpoint(3,'0'*64,SIGNER))
        with sqlite3.connect(self.db) as db:
            db.execute('UPDATE custody_v2_events SET nonce_digest=? WHERE sequence=2',
                       ('f'*64,))
        with self.assertRaises(Denied):self.read()

    def test_revoked_transport_and_drifted_head_fail_closed(self):
        self.revoked=True
        with self.assertRaises(Denied):self.read()
        self.revoked=False
        self.drift=True
        with self.assertRaises(Denied):self.read()

    def test_explicit_authorization_only_one_v2_admit(self):
        self.calls.clear()
        with self.assertRaises(Denied):
            self.client.admit_once(
                credential='fictional-reader',
                nonce='f'*64,reservation='e'*64,event_digest='d'*64,
                explicit_authorization=False)
        self.assertEqual(self.calls,[])
        # The client's pinned genesis is deliberately stale relative to the
        # already committed history. One request is attempted and denied.
        with self.assertRaises(Denied):
            self.client.admit_once(
                credential='fictional-reader',
                nonce='f'*64,reservation='e'*64,event_digest='d'*64,
                explicit_authorization=True)
        self.assertEqual(self.calls.count('v2_admit'),1)

    def test_asymmetric_readback_latency_fictional(self):
        measures=[]
        for _ in range(25):
            start=time.perf_counter()
            self.assertEqual(self.read().sequence,2)
            measures.append((time.perf_counter()-start)*1000)
        sorted_ms=sorted(measures)
        print('FICTIONAL ED25519 V2 READBACK ms n=25 '
              'p50=%.3f p95-nearest=%.3f max=%.3f'%(
                  sorted_ms[12],sorted_ms[23],sorted_ms[-1]),flush=True)


if __name__=='__main__':
    unittest.main()
