"""Adversarial fictional dual-signer tests; never external custody evidence."""
import hashlib
import hmac
import json
import unittest

from src.dual_witness_history import DualWitnessHistory
from src.independent_checkpoint_boundary import (
    CheckpointReadbackBoundary, PinnedCheckpoint, _digest)
from src.secure_engine import Denied

RES='a'*64
EVENT='b'*64


class FictionalWitness:
    def __init__(self, label, key, sequence=18, prev='f'*64,
                 reservation=RES, event=EVENT):
        self.label=label
        self.key=key
        self.pin=PinnedCheckpoint(sequence-1,prev,label)
        self.sequence=sequence
        self.event_digest=event
        self.head={'sequence':sequence,'previous':prev,
                   'event_digest':event,
                   'reservation_digest':_digest({'reservation':reservation}),
                   'signer_id':label}
        self.sign()
        self.event={'sequence':sequence,'reservation_digest':self.head['reservation_digest'],
                    'event_digest':event,'commit_state':'committed'}
        self.unavailable=False

    def sign(self):
        payload=json.dumps({k:v for k,v in self.head.items() if k!='signature'},
                           sort_keys=True,separators=(',',':'),
                           ensure_ascii=True).encode('ascii')
        self.head['signature']=hmac.new(self.key,payload,hashlib.sha256).hexdigest()

    def verify(self, signer, payload, signature):
        return signer==self.label and hmac.compare_digest(
            hmac.new(self.key,payload,hashlib.sha256).hexdigest(),signature)

    def read_head(self):
        if self.unavailable:
            raise TimeoutError('fictional witness unavailable')
        return dict(self.head)

    def read_event(self, seq):
        if self.unavailable:
            raise TimeoutError('fictional event unavailable')
        return dict(self.event)

    def boundary(self):
        return CheckpointReadbackBoundary(
            provider=self,verify_signature=self.verify,pinned=self.pin)


class DualWitnessHistoryTests(unittest.TestCase):
    def setUp(self):
        self.one=FictionalWitness('fictional-signer-A',b'fictional-only-A')
        self.two=FictionalWitness('fictional-signer-B',b'fictional-only-B')
        self.gate=DualWitnessHistory(first=self.one.boundary(),
                                     second=self.two.boundary())

    def check(self):
        return self.gate.verify(reservation=RES,event_digest=EVENT)

    def test_two_distinct_signatures_same_event_observation_only(self):
        result=self.check()
        self.assertEqual(result.sequence,18)
        self.assertNotEqual(result.first_head_digest,result.second_head_digest)
        self.assertFalse(result.independently_custodied)
        self.assertFalse(result.permits_write_replay)
        self.assertFalse(result.permits_fence_clearance)

    def test_unavailable_witness_rejects_no_quorum_downgrade(self):
        self.two.unavailable=True
        with self.assertRaises(Denied):
            self.check()

    def test_forked_second_witness_signed_other_event_rejected(self):
        self.two.head['event_digest']='c'*64
        self.two.event['event_digest']='c'*64
        self.two.sign()
        with self.assertRaises(Denied):
            self.check()

    def test_forked_same_reservation_with_different_event_rejected(self):
        self.two.head['reservation_digest']=_digest({'reservation':'d'*64})
        self.two.event['reservation_digest']=self.two.head['reservation_digest']
        self.two.sign()
        with self.assertRaises(Denied):
            self.check()

    def test_stale_replayed_witness_rejected(self):
        self.two.head['sequence']=17
        self.two.event['sequence']=17
        self.two.sign()
        with self.assertRaises(Denied):
            self.check()

    def test_skip_sequence_and_signer_rotation_rejected(self):
        self.two.head['sequence']=19
        self.two.event['sequence']=19
        self.two.sign()
        with self.assertRaises(Denied):
            self.check()
        self.two.head['sequence']=18
        self.two.event['sequence']=18
        self.two.head['signer_id']='unauthorized-rotated-signer'
        self.two.sign()
        with self.assertRaises(Denied):
            self.check()

    def test_tampered_signature_rejected(self):
        self.two.head['signature']='0'*64
        with self.assertRaises(Denied):
            self.check()

    def test_same_signer_or_same_reader_rejected(self):
        first=self.one.boundary()
        with self.assertRaises(Denied):
            DualWitnessHistory(first=first,second=first)
        with self.assertRaises(Denied):
            DualWitnessHistory(first=first,second=self.one.boundary())
        # Two separately allocated objects claiming the same pinned signer
        # do not make a distinct independent witness.
        mirror=FictionalWitness('fictional-signer-A',b'fictional-other-key')
        with self.assertRaises(Denied):
            DualWitnessHistory(first=first,second=mirror.boundary())

    def test_untrusted_foreign_identity_denied(self):
        with self.assertRaises(Denied):
            self.gate.verify(reservation='invalid',event_digest=EVENT)
        with self.assertRaises(Denied):
            self.gate.verify(reservation=RES,event_digest='invalid')

    def test_correct_second_signer_but_wrong_predecessor_denied(self):
        self.two.head['previous']='0'*64
        self.two.sign()
        with self.assertRaises(Denied):
            self.check()


if __name__=='__main__':
    unittest.main()
