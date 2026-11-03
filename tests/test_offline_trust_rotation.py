"""Synthetic dual-signature trust rotation policy checks, no live keys."""
import hashlib
import hmac
import json
import unittest
from copy import deepcopy
from src.offline_trust_rotation import OfflinePinRotationPreflight
from src.independent_checkpoint_boundary import PinnedCheckpoint
from src.secure_engine import Denied

CURRENT=PinnedCheckpoint(9,"a"*64,"old-test-signer")
OLD_KEY=b"fictional-current-trust-fixture"
NEW_KEY=b"fictional-successor-trust-fixture"
NOW=1800000000


def payload(m):
    return json.dumps({k:v for k,v in m.items()
                       if k not in ("old_signature","new_signature")},
                      sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")


def signature(key,data):
    return hmac.new(key,data,hashlib.sha256).hexdigest()


class OfflineRotationTests(unittest.TestCase):
    def setUp(self):
        self.approved=True
        self.gate=OfflinePinRotationPreflight(
            current_pin=CURRENT,
            verify_old_key=lambda signer,data,sig:
                signer==CURRENT.signer_id and
                hmac.compare_digest(signature(OLD_KEY,data),sig),
            verify_new_key=lambda signer,data,sig:
                signer=="new-test-signer" and
                hmac.compare_digest(signature(NEW_KEY,data),sig),
            independent_approval=lambda rotation_id,data:
                self.approved and rotation_id=="b"*64)
        self.manifest={
            "version":1,"previous_sequence":CURRENT.sequence,
            "previous_digest":CURRENT.digest,"previous_signer":CURRENT.signer_id,
            "next_sequence":CURRENT.sequence,"next_digest":CURRENT.digest,
            "next_signer":"new-test-signer",
            "valid_after":NOW-10,"valid_before":NOW+300,
            "rotation_id":"b"*64}
        self.resign()

    def resign(self):
        self.manifest["old_signature"]=signature(OLD_KEY,payload(self.manifest))
        self.manifest["new_signature"]=signature(NEW_KEY,payload(self.manifest))

    def confirm(self,**kw):
        args={"manifest":self.manifest,"now":NOW,
              "operator_authorized":True}
        args.update(kw)
        return self.gate.inspect(**args)

    def test_valid_dual_signature_observation_never_updates_pin(self):
        result=self.confirm()
        self.assertEqual(result.new_pin.signer_id,"new-test-signer")
        self.assertFalse(result.independent_custody_confirmed)
        self.assertEqual(self.gate.current_pin,CURRENT)

    def test_operator_not_authorized_denied(self):
        with self.assertRaises(Denied):
            self.confirm(operator_authorized=False)

    def test_missing_independent_approval_denied(self):
        self.approved=False
        with self.assertRaises(Denied):self.confirm()

    def test_forged_old_signature_denied(self):
        self.manifest["old_signature"]="0"*64
        with self.assertRaises(Denied):self.confirm()

    def test_forged_new_signature_denied(self):
        self.manifest["new_signature"]="0"*64
        with self.assertRaises(Denied):self.confirm()

    def test_changed_history_pin_denied_even_when_resigned(self):
        self.manifest["previous_digest"]="f"*64
        self.resign()
        with self.assertRaises(Denied):self.confirm()

    def test_skipped_or_rollback_sequence_denied(self):
        for n in (CURRENT.sequence-1,CURRENT.sequence+1):
            self.manifest["next_sequence"]=n
            self.resign()
            with self.subTest(n=n),self.assertRaises(Denied):
                self.confirm()

    def test_expired_and_not_yet_valid_denied(self):
        for t in (NOW-11,NOW+301):
            with self.subTest(t=t),self.assertRaises(Denied):
                self.confirm(now=t)

    def test_oversized_rotation_window_denied(self):
        self.manifest["valid_before"]=NOW+100000
        self.resign()
        with self.assertRaises(Denied):self.confirm()

    def test_unknown_fields_and_policy_downgrade_denied(self):
        self.manifest["accept_unsigned"]=True
        self.resign()
        with self.assertRaises(Denied):self.confirm()

    def test_reuse_existing_signer_denied(self):
        self.manifest["next_signer"]=CURRENT.signer_id
        self.resign()
        with self.assertRaises(Denied):self.confirm()

    def test_untrusted_clock_and_missing_callback_fail_closed(self):
        for clock in (None,True,0,"1800000000"):
            with self.subTest(clock=clock),self.assertRaises(Denied):
                self.confirm(now=clock)
        with self.assertRaises(Denied):
            OfflinePinRotationPreflight(
                current_pin=CURRENT,verify_old_key=None,
                verify_new_key=lambda *args:True,
                independent_approval=lambda *args:True)


if __name__=="__main__":
    unittest.main()
