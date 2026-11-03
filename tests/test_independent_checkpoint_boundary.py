"""Controlled signed fixture only. NOT independent custody or production."""
import hmac
import hashlib
import json
import unittest
from copy import deepcopy

from src.independent_checkpoint_boundary import (
    CheckpointReadbackBoundary, PinnedCheckpoint, _digest)
from src.secure_engine import Denied

# Test-only key. No production identity or witness is provided here.
KEY = b"fictional-test-fixture-key"
PIN = PinnedCheckpoint(42, "a"*64, "test-witness-v1")
RESERVATION = "b"*64
EVENT = "c"*64


def serialize(head):
    fields={k:v for k,v in head.items() if k!="signature"}
    return json.dumps(fields, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def sign(head):
    head["signature"]=hmac.new(KEY,serialize(head),hashlib.sha256).hexdigest()
    return head


def signature_check(signer, data, signature):
    return (signer == PIN.signer_id and
            hmac.compare_digest(hmac.new(KEY,data,hashlib.sha256).hexdigest(),
                                signature))


class ControlledIndependentReader:
    def __init__(self):
        self.head=sign({"sequence":43,"previous":PIN.digest,
            "event_digest":EVENT,
            "reservation_digest":_digest({"reservation":RESERVATION}),
            "signer_id":PIN.signer_id})
        self.event={"sequence":43,"reservation_digest":self.head["reservation_digest"],
                    "event_digest":EVENT,"commit_state":"committed"}
        self.fail=False

    def read_head(self):
        if self.fail:raise TimeoutError("controlled lost acknowledgment")
        return deepcopy(self.head)

    def read_event(self, seq):
        if self.fail:raise TimeoutError("controlled unavailable readback")
        return deepcopy(self.event)


class CheckpointBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.reader=ControlledIndependentReader()
        self.gate=CheckpointReadbackBoundary(
            provider=self.reader, verify_signature=signature_check, pinned=PIN)

    def confirm(self, **extra):
        return self.gate.verify(reservation=RESERVATION,event_digest=EVENT,**extra)

    def test_contiguous_signed_committed_readback_is_observation_only(self):
        result=self.confirm()
        self.assertEqual(result.sequence,43)
        self.assertEqual(result.signer_id,PIN.signer_id)
        self.assertFalse(result.independently_custodied)
        self.assertEqual(result.head_digest,_digest({
            key:self.reader.head[key] for key in self.reader.head if key!="signature"}))

    def test_invalid_signature_rejected(self):
        self.reader.head["signature"]="0"*64
        with self.assertRaises(Denied):self.confirm()

    def test_stale_replay_rejected_even_with_signature(self):
        self.reader.head["sequence"]=42
        sign(self.reader.head)
        self.reader.event["sequence"]=42
        with self.assertRaises(Denied):self.confirm()

    def test_skipped_predecessor_rejected(self):
        self.reader.head["sequence"]=44
        sign(self.reader.head)
        self.reader.event["sequence"]=44
        with self.assertRaises(Denied):self.confirm()

    def test_rollback_or_wrong_pin_rejected(self):
        self.reader.head["previous"]="e"*64
        sign(self.reader.head)
        with self.assertRaises(Denied):self.confirm()

    def test_signer_rotation_cannot_silently_downgrade(self):
        self.reader.head["signer_id"]="rotated-signer"
        sign(self.reader.head)
        with self.assertRaises(Denied):self.confirm()

    def test_signed_not_committed_response_rejected(self):
        self.reader.event["commit_state"]="prepared"
        with self.assertRaises(Denied):self.confirm()

    def test_mismatched_reservation_or_event_denied(self):
        for reservation,event in (("d"*64,EVENT),(RESERVATION,"d"*64)):
            with self.subTest(reservation=reservation,event=event):
                with self.assertRaises(Denied):
                    self.gate.verify(reservation=reservation,event_digest=event)

    def test_forged_committed_event_separate_from_signed_head(self):
        self.reader.event["reservation_digest"]="0"*64
        with self.assertRaises(Denied):self.confirm()

    def test_unsigned_extra_field_and_policy_downgrade_denied(self):
        self.reader.head["legacy_allow_unsigned"]=True
        with self.assertRaises(Denied):self.confirm()
        del self.reader.head["legacy_allow_unsigned"]
        self.reader.event["approved"]=True
        with self.assertRaises(Denied):self.confirm()

    def test_readback_timeout_fails_closed(self):
        self.reader.fail=True
        with self.assertRaises(Denied):self.confirm()

    def test_conflicting_or_lost_write_acknowledgment_denied(self):
        for value in ({"sequence":43,"head_digest":"0"*64},
                      {"sequence":42,"head_digest":_digest({
                          k:v for k,v in self.reader.head.items() if k!="signature"})},
                      {"sequence":43,"head_digest":_digest({
                          k:v for k,v in self.reader.head.items() if k!="signature"}),
                       "skip_verify":True}):
            with self.subTest(value=value):
                with self.assertRaises(Denied):self.confirm(proposal=value)

    def test_matching_ack_still_requires_real_readback(self):
        ack={"sequence":43,"head_digest":_digest({
            k:v for k,v in self.reader.head.items() if k!="signature"})}
        self.assertEqual(self.confirm(proposal=ack).sequence,43)
        self.reader.fail=True
        with self.assertRaises(Denied):self.confirm(proposal=ack)

    def test_missing_trust_root_fails_at_construction(self):
        with self.assertRaises(Denied):
            CheckpointReadbackBoundary(provider=self.reader,
                                       verify_signature=None,pinned=PIN)
        with self.assertRaises(Denied):
            CheckpointReadbackBoundary(provider=self.reader,
                                       verify_signature=signature_check,
                                       pinned=PinnedCheckpoint(42,"wrong",PIN.signer_id))


if __name__=="__main__":
    unittest.main()
