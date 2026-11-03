"""Synthetic offline duplicate/conflicting signer rotation reservations."""
import hashlib
import hmac
import json
import multiprocessing
import tempfile
import threading
import unittest
from pathlib import Path

from src.independent_checkpoint_boundary import PinnedCheckpoint
from src.offline_trust_rotation import OfflinePinRotationPreflight
from src.offline_rotation_ledger import OfflineRotationLedger
from src.secure_engine import Denied

PIN=PinnedCheckpoint(11,"a"*64,"current-fixture-signer")
NOW=1800000000
OLD=b"offline-signature-fixture-old"
NEW=b"offline-signature-fixture-new"


def bytes_to_sign(manifest):
    return json.dumps(
        {k:v for k,v in manifest.items()
         if k not in ("old_signature","new_signature")},
        sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")


def sign(manifest):
    body=bytes_to_sign(manifest)
    manifest["old_signature"]=hmac.new(OLD,body,hashlib.sha256).hexdigest()
    manifest["new_signature"]=hmac.new(NEW,body,hashlib.sha256).hexdigest()


def policy():
    return OfflinePinRotationPreflight(
        current_pin=PIN,
        verify_old_key=lambda key,body,sig:
            key==PIN.signer_id and hmac.compare_digest(
                hmac.new(OLD,body,hashlib.sha256).hexdigest(),sig),
        verify_new_key=lambda key,body,sig:
            key=="next-fixture-signer" and hmac.compare_digest(
                hmac.new(NEW,body,hashlib.sha256).hexdigest(),sig),
        independent_approval=lambda rotation_id,body:
            rotation_id in ("b"*64,"c"*64))


def proposal(id="b"*64, successor="d"*64):
    m={"version":1,"previous_sequence":11,
       "previous_digest":PIN.digest,"previous_signer":PIN.signer_id,
       "next_sequence":11,"next_digest":successor,
       "next_signer":"next-fixture-signer","valid_after":NOW-10,
       "valid_before":NOW+100,"rotation_id":id}
    sign(m)
    return m


def child_reserve(path,manifest,queue):
    try:
        OfflineRotationLedger(path).reserve_once(
            policy=policy(),manifest=manifest,now=NOW,
            operator_authorized=True)
        queue.put("reserved")
    except Denied:
        queue.put("denied")


class OfflineRotationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"fictional-rotation.sqlite3"
        self.ledger=OfflineRotationLedger(self.path,create=True)

    def tearDown(self):
        self.temp.cleanup()

    def reserve(self,manifest=None,**kw):
        args={"policy":policy(),"manifest":proposal() if manifest is None else manifest,
              "now":NOW,"operator_authorized":True}
        args.update(kw)
        return self.ledger.reserve_once(**args)

    def test_one_approved_proposal_records_observation_not_key_change(self):
        result=self.reserve()
        self.assertEqual(result.status,"reserved_for_independent_manual_review")
        self.assertFalse(result.observation.independent_custody_confirmed)
        stored=self.ledger.inspect_reserved("b"*64)
        self.assertEqual(stored["state"],"proposed")
        self.assertEqual(stored["previous"],PIN)
        self.assertEqual(stored["successor"].signer_id,"next-fixture-signer")

    def test_duplicate_rotation_identity_denied_after_restart(self):
        self.reserve()
        again=OfflineRotationLedger(self.path)
        with self.assertRaises(Denied):
            again.reserve_once(policy=policy(),manifest=proposal(),
                               now=NOW,operator_authorized=True)

    def test_conflicting_rotation_same_predecessor_denied(self):
        self.reserve()
        with self.assertRaises(Denied):
            self.reserve(proposal(id="c"*64,successor="e"*64))

    def test_two_threads_same_predecessor_only_one_proposal(self):
        barrier=threading.Barrier(2)
        results=[]
        def worker(manifest):
            barrier.wait()
            try:
                self.reserve(manifest)
                results.append("reserved")
            except Denied:
                results.append("denied")
        a=threading.Thread(target=worker,args=(proposal(),))
        b=threading.Thread(target=worker,args=(proposal(id="c"*64,successor="e"*64),))
        a.start();b.start();a.join(10);b.join(10)
        self.assertEqual(sorted(results),["denied","reserved"])

    def test_two_spawned_processes_only_one_proposal(self):
        ctx=multiprocessing.get_context("spawn")
        out=ctx.Queue()
        a=ctx.Process(target=child_reserve,args=(str(self.path),proposal(),out))
        b=ctx.Process(target=child_reserve,
                      args=(str(self.path),proposal(id="c"*64,successor="e"*64),out))
        a.start();b.start();a.join(15);b.join(15)
        self.assertEqual((a.exitcode,b.exitcode),(0,0))
        self.assertEqual(sorted((out.get(timeout=3),out.get(timeout=3))),
                         ["denied","reserved"])

    def test_no_approval_or_wrong_pin_never_consumes_identity(self):
        with self.assertRaises(Denied):
            self.reserve(operator_authorized=False)
        bad=proposal()
        bad["previous_digest"]="f"*64
        sign(bad)
        with self.assertRaises(Denied):
            self.reserve(bad)
        self.assertEqual(self.reserve().status,
                         "reserved_for_independent_manual_review")

    def test_corrupted_store_fails_closed(self):
        self.path.write_bytes(b"not a sqlite database")
        with self.assertRaises(Denied):
            self.reserve()
        with self.assertRaises(Denied):
            OfflineRotationLedger(self.path)

    def test_missing_ledger_fails_closed_without_explicit_bootstrap(self):
        self.path.unlink()
        with self.assertRaises(Denied):
            OfflineRotationLedger(self.path)
        with self.assertRaises(Denied):
            self.ledger.reserve_once(policy=policy(),manifest=proposal(),
                                     now=NOW,operator_authorized=True)

    def test_no_automatic_pin_rotation_or_ledger_clearance(self):
        self.reserve()
        self.assertEqual(policy().current_pin,PIN)
        self.assertFalse(hasattr(self.ledger,"apply_rotation"))
        self.assertFalse(hasattr(self.ledger,"clear"))
        self.assertEqual(self.ledger.inspect_reserved("b"*64)["state"],"proposed")


if __name__=="__main__":
    unittest.main()
