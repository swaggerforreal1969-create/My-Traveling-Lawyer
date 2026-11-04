"""Fictional independent authenticated pin reader acceptance; no production keys."""
import hashlib
import hmac
import json
import unittest

from src.authenticated_pin_source import AuthenticatedPinSource
from src.cross_observer_history import CrossObserverRound
from src.read_only_pin_quorum import ReadOnlyPinQuorum
from src.secure_engine import Denied
from test_dual_witness_history import CrossObserverContinuityTests

KEY_A=b'fictional-separate-pin-signer-A'
KEY_B=b'fictional-separate-pin-signer-B'


class FixtureSignedReader:
    def __init__(self, pin, signer, key):
        self.signer=signer
        self.key=key
        self.reply={
            'schema':'mtl.custody.predecessor-pin.v1',
            'signer_id':signer,
            'pin':{key:getattr(pin,key) for key in
                   ('sequence','signer_a','signer_b','head_a','head_b')}
        }
        self.sign()

    def sign(self):
        payload=json.dumps(self.reply,sort_keys=True,separators=(',',':'),
                           ensure_ascii=True).encode('ascii')
        self.reply['signature']=hmac.new(
            self.key,payload,hashlib.sha256).hexdigest()

    def read_signed_pin(self):
        return json.loads(json.dumps(self.reply))

    def verify(self,signer,payload,signature):
        return (signer==self.signer and hmac.compare_digest(
            hmac.new(self.key,payload,hashlib.sha256).hexdigest(),signature))

    def source(self):
        return AuthenticatedPinSource(
            reader=self,signer_id=self.signer,
            verify_signature=self.verify)


class SignedPinSourceTests(unittest.TestCase):
    def setUp(self):
        fixture=CrossObserverContinuityTests()
        _,before=fixture.make_observers()
        self.prior=fixture.check(before)
        _,self.later=fixture.make_observers(sequence=19,prior=self.prior,
                                             reservation='c'*64,event='d'*64)
        self.a=FixtureSignedReader(self.prior,'fixture-pin-source-A',KEY_A)
        self.b=FixtureSignedReader(self.prior,'fixture-pin-source-B',KEY_B)

    def check(self):
        gate=ReadOnlyPinQuorum(primary=self.a.source(),secondary=self.b.source())
        return gate.verify(self.later[0],self.later[1],
                           reservation='c'*64,event_digest='d'*64,
                           expected_pin=self.prior)

    def test_two_distinct_signed_sources_and_external_anchor(self):
        result=self.check()
        self.assertEqual(result.sequence,19)
        self.assertFalse(result.independently_custodied)
        self.assertFalse(result.permits_write_replay)
        self.assertFalse(result.permits_fence_clearance)

    def test_tampered_pin_without_new_signature_denied(self):
        self.b.reply['pin']['head_a']='0'*64
        with self.assertRaises(Denied):self.check()

    def test_signed_coordinated_rollback_rejected_by_separate_anchor(self):
        for source in (self.a,self.b):
            source.reply['pin']['sequence']-=1
            source.sign()
        with self.assertRaises(Denied):self.check()

    def test_swapped_signer_and_unpinned_key_denied(self):
        self.b.reply['signer_id']='fixture-pin-source-A'
        self.b.sign()
        with self.assertRaises(Denied):self.check()

    def test_identical_signer_on_two_sources_rejected(self):
        clone=FixtureSignedReader(self.prior,'fixture-pin-source-A',KEY_A)
        with self.assertRaises(Denied):
            ReadOnlyPinQuorum(primary=self.a.source(),secondary=clone.source())

    def test_downgrade_unsigned_extra_field_and_bad_schema_denied(self):
        self.b.reply['legacy_allow_unsigned']=True
        with self.assertRaises(Denied):self.check()
        del self.b.reply['legacy_allow_unsigned']
        self.b.reply['schema']='mtl.custody.unverified.v0'
        self.b.sign()
        with self.assertRaises(Denied):self.check()

    def test_replayed_signed_pin_without_external_anchor_is_not_custody(self):
        # Exact signed pin alone cannot prove freshness or independence.
        first=self.a.source().read_pin()
        self.assertEqual(first,self.prior)
        self.assertFalse(first.independently_custodied)
        self.assertFalse(first.permits_fence_clearance)

    def test_signer_failure_and_malformed_signature_denied(self):
        self.b.reply['signature']='0'*64
        with self.assertRaises(Denied):self.check()
        self.b.reply['signature']=None
        with self.assertRaises(Denied):self.check()


if __name__=='__main__':
    unittest.main()
