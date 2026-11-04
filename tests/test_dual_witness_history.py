"""Adversarial fictional dual-signer tests; never external custody evidence."""
import hashlib
import hmac
import json
import unittest

from src.dual_witness_history import DualWitnessHistory
from src.cross_observer_history import verify_observers, CrossObserverRound
from src.read_only_pin_quorum import ReadOnlyPinQuorum
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



class CrossObserverContinuityTests(unittest.TestCase):
    def make_observers(self, sequence=18, prior=None, reservation=RES, event=EVENT):
        previous_a=prior.head_a if prior else 'f'*64
        previous_b=prior.head_b if prior else 'f'*64
        pairs=[]
        for _ in range(2):
            one=FictionalWitness('fictional-signer-A',b'fictional-only-A',
                sequence=sequence,prev=previous_a,reservation=reservation,event=event)
            two=FictionalWitness('fictional-signer-B',b'fictional-only-B',
                sequence=sequence,prev=previous_b,reservation=reservation,event=event)
            pairs.append((one,two))
        gates=[DualWitnessHistory(first=a.boundary(),second=b.boundary())
               for a,b in pairs]
        return pairs,gates

    def check(self,gates, prior=None, reservation=RES, event=EVENT):
        return verify_observers(gates[0],gates[1],reservation=reservation,
                                event_digest=event,previous=prior)

    def test_two_observers_same_signed_heads_no_write_grant(self):
        pairs,gates=self.make_observers()
        proof=self.check(gates)
        self.assertEqual(proof.sequence,18)
        self.assertFalse(proof.independently_custodied)
        self.assertFalse(proof.permits_fence_clearance)
        self.assertFalse(proof.permits_write_replay)

    def test_two_contiguous_rounds_with_exact_external_forward_pin(self):
        _,gates=self.make_observers()
        prior=self.check(gates)
        _,later=self.make_observers(sequence=19,prior=prior,
                                     reservation='c'*64,event='d'*64)
        nxt=self.check(later,prior=prior,reservation='c'*64,event='d'*64)
        self.assertEqual(nxt.sequence,prior.sequence+1)
        self.assertNotEqual(nxt.head_a,prior.head_a)

    def test_prior_commit_replay_or_skipped_generation_denied(self):
        _,gates=self.make_observers()
        prior=self.check(gates)
        for seq in (18,20):
            with self.subTest(seq=seq):
                _,next_gates=self.make_observers(sequence=seq,prior=prior)
                with self.assertRaises(Denied):
                    self.check(next_gates,prior=prior)

    def test_forged_prior_pin_or_changed_signer_denied(self):
        _,gates=self.make_observers()
        prior=self.check(gates)
        _,later=self.make_observers(sequence=19,prior=prior)
        forged=CrossObserverRound(prior.sequence,prior.signer_a,prior.signer_b,
                                  '0'*64,prior.head_b)
        with self.assertRaises(Denied):
            self.check(later,prior=forged)
        rotated=CrossObserverRound(prior.sequence,'new-signer',prior.signer_b,
                                   prior.head_a,prior.head_b)
        with self.assertRaises(Denied):
            self.check(later,prior=rotated)

    def test_split_view_from_same_signer_fails_closed(self):
        pairs,gates=self.make_observers()
        # A dishonest observer's first signer presents a distinct signed head.
        pairs[1][0].head['previous']='0'*64
        pairs[1][0].pin=PinnedCheckpoint(17,'0'*64,'fictional-signer-A')
        pairs[1][0].sign()
        # Both snapshots are individually signed, but trust pins diverge.
        with self.assertRaises(Denied):
            self.check(gates)

    def test_same_reader_reused_across_observers_rejected(self):
        _,gates=self.make_observers()
        with self.assertRaises(Denied):
            verify_observers(gates[0],gates[0],reservation=RES,event_digest=EVENT)
        shared=DualWitnessHistory(first=gates[0].first,
                                  second=gates[1].second)
        with self.assertRaises(Denied):
            verify_observers(gates[0],shared,reservation=RES,event_digest=EVENT)

    def test_one_missing_witness_fails_no_single_observer_fallback(self):
        pairs,gates=self.make_observers()
        pairs[1][1].unavailable=True
        with self.assertRaises(Denied):
            self.check(gates)

    def test_cross_observer_stale_signer_rotation_and_wrong_event(self):
        pairs,gates=self.make_observers()
        pairs[1][1].head['signer_id']='rogue'
        pairs[1][1].sign()
        with self.assertRaises(Denied):
            self.check(gates)
        pairs[1][1].head['signer_id']='fictional-signer-B'
        pairs[1][1].sign()
        with self.assertRaises(Denied):
            self.check(gates,event='d'*64)


class _FixturePinSource:
    def __init__(self, pin):
        self.pin=pin
        self.failure=False
        self.after=None
        self.reads=0
    def read_pin(self):
        self.reads+=1
        if self.failure:raise OSError('fictional pin service unavailable')
        if self.reads>1 and self.after is not None:
            return self.after
        return self.pin


class ExternalPinReadbackTests(unittest.TestCase):
    def setUp(self):
        fixture=CrossObserverContinuityTests()
        _,early=fixture.make_observers()
        self.prior=fixture.check(early)
        _,self.later=fixture.make_observers(
            sequence=19,prior=self.prior,
            reservation='c'*64,event='d'*64)
        self.first=_FixturePinSource(self.prior)
        self.second=_FixturePinSource(self.prior)
        self.verifier=ReadOnlyPinQuorum(primary=self.first,
                                        secondary=self.second)

    def verify(self):
        return self.verifier.verify(
            self.later[0],self.later[1],
            reservation='c'*64,event_digest='d'*64)

    def test_two_readonly_predecessor_sources_match(self):
        observed=self.verify()
        self.assertEqual(observed.sequence,19)
        self.assertEqual((self.first.reads,self.second.reads),(2,2))
        self.assertFalse(observed.independently_custodied)
        self.assertFalse(observed.permits_fence_clearance)

    def test_single_source_or_shared_reader_rejected(self):
        with self.assertRaises(Denied):
            ReadOnlyPinQuorum(primary=self.first,secondary=self.first)
        with self.assertRaises(Denied):
            ReadOnlyPinQuorum(primary=self.first,secondary=None)

    def test_split_pin_across_two_sources_rejected(self):
        self.second.pin=CrossObserverRound(
            self.prior.sequence,self.prior.signer_a,self.prior.signer_b,
            '0'*64,self.prior.head_b)
        with self.assertRaises(Denied):self.verify()

    def test_rolled_back_one_source_rejected(self):
        self.second.pin=CrossObserverRound(
            self.prior.sequence-1,self.prior.signer_a,self.prior.signer_b,
            self.prior.head_a,self.prior.head_b)
        with self.assertRaises(Denied):self.verify()

    def test_source_changes_between_pre_and_post_readback_rejected(self):
        self.second.after=CrossObserverRound(
            self.prior.sequence+1,self.prior.signer_a,self.prior.signer_b,
            self.prior.head_a,self.prior.head_b)
        with self.assertRaises(Denied):self.verify()

    def test_malformed_pin_and_missing_source_fail_closed(self):
        self.first.pin={'sequence':self.prior.sequence}
        with self.assertRaises(Denied):self.verify()
        self.first.pin=self.prior
        self.second.failure=True
        with self.assertRaises(Denied):self.verify()

    def test_external_pin_wrong_signer_rejected(self):
        self.first.pin=CrossObserverRound(
            self.prior.sequence,'fictional-rotated-signer',
            self.prior.signer_b,self.prior.head_a,self.prior.head_b)
        self.second.pin=self.first.pin
        with self.assertRaises(Denied):self.verify()

    def test_previous_pin_missing_is_never_trust_on_first_use(self):
        self.first.pin=None
        self.second.pin=None
        with self.assertRaises(Denied):self.verify()



if __name__=='__main__':
    unittest.main()
