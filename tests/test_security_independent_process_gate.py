"""Adversarial tests for the authorized experimental local attorney core.

Real separate OS Python processes and fresh SQLite connections; fictional data.
No v1.4 restricted originals, remote provider, HTTP entrypoint or production approval.
"""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from src.secure_engine import SecureCore, Denied
from src.durable_local_write_fence import LocalWriteFence


class IndependentProcessSecurityAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mtl-fictional-sec-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fictional.sqlite3"
        self.core = SecureCore(self.path)
        self.addCleanup(self.core.close)
        self.firm = self.core.provision_firm("Fictional First Firm")
        self.owner_id, self.owner = self.core.provision_user(self.firm, "Owner")
        self.editor_id, self.editor = self.core.provision_user(self.firm, "Editor")
        other_firm = self.core.provision_firm("Fictional Outside Firm")
        self.outsider_id, self.outsider = self.core.provision_user(other_firm, "Outsider")
        self.matter = self.core.create_matter(self.owner, "FICTIONAL PRIVATE MATTER")
        self.core.grant(self.owner, self.matter["id"], self.editor_id, "editor", 1)

    def child(self, code, *args):
        # Never log or print even fictional bearer tokens or private record bytes.
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", code, str(self.path), *map(str, args)],
            cwd=str(Path(__file__).resolve().parents[1]), env=env,
            capture_output=True, text=True, timeout=25, check=False)
        self.assertEqual(result.returncode, 0, "Independent child failed (output redacted)")
        self.assertEqual(result.stdout.strip(), "PASS", "Independent child gave no verified result")
        self.assertEqual(result.stderr, "", "Unexpected child diagnostic (redacted)")

    def test_cross_firm_permissions_and_private_note_not_exposed(self):
        self.core.add_note(self.owner, self.matter["id"], "FICTIONAL SECRET")
        before = self.core.audit_head()
        with self.assertRaises(Denied):
            self.core.read_notes(self.outsider, self.matter["id"])
        with self.assertRaises(Denied):
            self.core.grant(self.outsider, self.matter["id"], self.outsider_id, "editor", 2)
        with self.assertRaises(Denied):
            self.core.grant(self.owner, self.matter["id"], self.outsider_id, "editor", 2)
        self.assertEqual(self.core.audit_head(), before)
        self.assertEqual(self.core.list_matters(self.outsider), [])
        self.assertEqual(self.core.read_notes(self.owner, self.matter["id"])[0]["text"], "FICTIONAL SECRET")

    def test_sql_metacharacters_remain_note_data(self):
        payload = "fictional'); DROP TABLE matters; --"
        self.core.add_note(self.owner, self.matter["id"], payload)
        self.assertEqual(self.core.read_notes(self.owner, self.matter["id"])[0]["text"], payload)
        self.assertEqual(len(self.core.list_matters(self.owner)), 1)
        self.assertTrue(self.core.verify_audit())

    def test_revocation_in_other_process_denies_existing_session(self):
        self.child(
            "import sys; from src.secure_engine import SecureCore; "
            "c=SecureCore(sys.argv[1]); c.revoke_token(sys.argv[2]); c.close(); print('PASS')",
            self.editor)
        with self.assertRaises(Denied):
            self.core.list_matters(self.editor)
        with self.assertRaises(Denied):
            self.core.add_note(self.editor, self.matter["id"], "NEVER WRITTEN")
        self.assertEqual(self.core.read_notes(self.owner, self.matter["id"]), [])

    def test_cross_process_acl_downgrade_prevents_task_completion(self):
        task = self.core.create_task(self.owner, self.matter["id"], "FICTIONAL TASK",
                                     "2026-12-01T00:00:00Z")
        self.child(
            "import sys; from src.secure_engine import SecureCore; "
            "c=SecureCore(sys.argv[1]); "
            "c.grant(sys.argv[2], sys.argv[3], sys.argv[4], 'viewer', int(sys.argv[5])); "
            "c.close(); print('PASS')",
            self.owner, self.matter["id"], self.editor_id, 2)
        before = self.core.audit_head()
        with self.assertRaises(Denied):
            self.core.complete_task(self.editor, task["id"], 1)
        self.assertEqual(self.core.audit_head(), before)
        row = self.core.db.execute(
            "SELECT completed,version FROM tasks WHERE id=?", (task["id"],)).fetchone()
        self.assertEqual((row["completed"], row["version"]), (0, 1))

    def test_audit_row_deletion_is_detected(self):
        self.core.add_note(self.owner, self.matter["id"], "FICTIONAL FIRST")
        self.core.add_note(self.owner, self.matter["id"], "FICTIONAL SECOND")
        self.assertTrue(self.core.verify_audit())
        row = self.core.db.execute(
            "SELECT seq FROM audit_chain ORDER BY seq LIMIT 1 OFFSET 1").fetchone()
        self.assertIsNotNone(row)
        self.core.db.execute("DELETE FROM audit_chain WHERE seq=?", (row["seq"],))
        self.assertFalse(self.core.verify_audit())

    def test_crashed_separate_process_keeps_durable_write_fence_pending(self):
        self.child(
            "import os,sys; from src.durable_local_write_fence import LocalWriteFence; "
            "f=LocalWriteFence(sys.argv[1]); f.begin(); print('PASS'); "
            "sys.stdout.flush(); os._exit(0)")
        fresh = LocalWriteFence(self.path)
        self.assertTrue(fresh.is_pending())
        with self.assertRaises(Denied):
            fresh.begin()
        with self.assertRaises(Denied):
            fresh.finish_confirmed(expected_reservation="0" * 64)
        self.assertTrue(LocalWriteFence(self.path).is_pending())


if __name__ == "__main__":
    unittest.main()
