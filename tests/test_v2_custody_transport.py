"""Authenticated v2 transport contract tests; all data/keys are fictional."""
import sqlite3
import unittest

from src.independent_checkpoint_boundary import PinnedCheckpoint
from src.nonce_bound_custody import SCHEMA
from src.provider_neutral_custody_client import AuthenticatedCustodyTransport
from src.v2_custody_transport import NonceBoundCustodyClientV2
from src.secure_engine import Denied
from test_nonce_bound_custody import NonceBoundReceiptTests, PIN, verify


class V2TransportTests(unittest.TestCase):
    def setUp(self):
        self.fixture=NonceBoundReceiptTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.events=self.fixture.ops
        self.calls=[]
        self.revoked=False
        self.mutate=False
        self.head_reads=0
        self.wire=AuthenticatedCustodyTransport(
            request=self.exchange,transport_authenticated=True)
        self.client=NonceBoundCustodyClientV2(
            transport=self.wire,predecessor=PIN,verify_signature=verify)

    def exchange(self,operation,body):
        self.calls.append(operation)
        if self.revoked or body.get('credential')!='fictional-credential':
            raise Denied('Provider credential denied')
        if body.get('schema')!=SCHEMA:
            raise Denied('No v1-to-v2 downgrade')
        if operation=='v2_read_latest':
            self.head_reads+=1
            with sqlite3.connect(self.fixture.path) as db:
                row=db.execute('SELECT sequence,head_digest FROM custody_v2_events '
                               'ORDER BY sequence DESC LIMIT 1').fetchone()
            if row is None:raise Denied('No signed head')
            if self.mutate and self.head_reads==2:
                return {'sequence':row[0],'head_digest':'f'*64}
            return {'sequence':row[0],'head_digest':row[1]}
        if operation=='v2_read_head_at':
            return self.fixture.provider._head_at(body['sequence'])
        if operation=='v2_admit':
            expected=body['expected']
            return self.fixture.provider.admit_once(
                credential='fixture-authorized',nonce=body['nonce'],
                reservation=body['reservation'],
                event_digest=body['event_digest'],
                expected=PinnedCheckpoint(expected['sequence'],expected['digest'],
                                          expected['signer_id']),
                explicitly_authorized=True)
        raise Denied('Unsupported version-two operation')

    def read(self, idx=1, **kwargs):
        nonce,res,event=self.events[idx]
        payload={'credential':'fictional-credential','nonce':nonce,
                 'reservation':res,'event_digest':event,
                 'retained_latest':self.fixture.latest}
        payload.update(kwargs)
        return self.client.reconcile_read_only(**payload)

    def test_exact_signed_nonce_historical_transport(self):
        seen=self.read()
        self.assertEqual((seen.sequence,seen.latest_sequence),(2,3))
        self.assertTrue(seen.nonce_authenticated)
        self.assertFalse(seen.independently_custodied)
        self.assertFalse(seen.permits_write_replay)
        self.assertFalse(seen.permits_fence_clearance)
        self.assertEqual(self.calls.count('v2_read_head_at'),3)

    def test_nonce_forgery_and_stale_tip_denied(self):
        with self.assertRaises(Denied):self.read(nonce='f'*64)
        with self.assertRaises(Denied):
            self.read(retained_latest=PinnedCheckpoint(
                3,'0'*64,PIN.signer_id))

    def test_signature_tampering_denied(self):
        with sqlite3.connect(self.fixture.path) as db:
            db.execute("UPDATE custody_v2_events SET signature='0' WHERE sequence=2")
        with self.assertRaises(Denied):self.read()

    def test_read_head_changes_during_response_denied(self):
        self.mutate=True
        with self.assertRaises(Denied):self.read()

    def test_revoked_credentials_denied(self):
        self.revoked=True
        with self.assertRaises(Denied):self.read()
        with self.assertRaises(Denied):
            self.client.admit_once(
                credential='fictional-credential',nonce='f'*64,
                reservation='f'*64,event_digest='f'*64,
                explicit_authorization=True)

    def test_human_authorization_and_no_automatic_replay(self):
        with self.assertRaises(Denied):
            self.client.admit_once(
                credential='fictional-credential',nonce='f'*64,
                reservation='f'*64,event_digest='f'*64,
                explicit_authorization=False)
        self.assertNotIn('v2_admit',self.calls)
        self.calls.clear()
        before=len(self.calls)
        try:
            self.client.admit_once(
                credential='fictional-credential',nonce='f'*64,
                reservation='f'*64,event_digest='f'*64,
                explicit_authorization=True)
        except Denied:
            pass
        self.assertEqual(self.calls.count('v2_admit'),1)

    def test_legacy_v1_transport_does_not_turn_nonce_authenticated(self):
        from src.provider_neutral_custody_client import CustodyClient
        legacy=CustodyClient(
            transport=self.wire,pinned=PIN,verify_signature=verify)
        self.assertFalse(hasattr(legacy,'reconcile_v2_read_only'))
        self.assertEqual(self.read().sequence,2)

    def test_untrusted_signature_verifier_cannot_accept(self):
        failed=NonceBoundCustodyClientV2(
            transport=self.wire,predecessor=PIN,
            verify_signature=lambda *a:False)
        nonce,res,event=self.events[1]
        with self.assertRaises(Denied):
            failed.reconcile_read_only(
                credential='fictional-credential',nonce=nonce,
                reservation=res,event_digest=event,
                retained_latest=self.fixture.latest)

    def test_history_window_fails_closed(self):
        with self.assertRaises(Denied):self.read(max_events=2)
        with self.assertRaises(Denied):self.read(max_events=0)

    def test_transport_authentication_is_contract_not_real_independence(self):
        with self.assertRaises(Denied):
            AuthenticatedCustodyTransport(
                request=self.exchange,transport_authenticated=False)
        self.assertFalse(self.read().independently_custodied)


if __name__=='__main__':
    unittest.main()
