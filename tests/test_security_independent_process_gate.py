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

    def test_cross_process_note_admission_serializes_with_acl_downgrade(self):
        """A second OS process cannot revoke between admission and note commit.

        Allowed outcomes are serialized: revocation committed first => DENIED;
        our reserved writer first => concurrent downgrade BUSY until commit.
        """
        original_role = self.core._role
        observed = []
        def checked_then_competed(identity, matter_id, allowed):
            accepted = original_role(identity, matter_id, allowed)
            if not observed and identity["id"] == self.editor_id:
                code = (
                    "import sqlite3,sys; from src.secure_engine import SecureCore; "
                    "c=None\ntry:\n"
                    " c=SecureCore(sys.argv[1]); c.db.execute('PRAGMA busy_timeout=200')\n"
                    " c.grant(sys.argv[2],sys.argv[3],sys.argv[4],'viewer',int(sys.argv[5]))\n"
                    " print('COMMITTED')\n"
                    "except sqlite3.OperationalError as err:\n"
                    " if 'locked' not in str(err).lower(): raise\n"
                    " print('BUSY')\n"
                    "finally:\n"
                    " if c is not None: c.close()"
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, str(self.path), self.owner,
                     self.matter["id"], self.editor_id, "2"],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True, text=True, timeout=15, check=False)
                self.assertEqual(child.returncode, 0, "Competing child error (redacted)")
                self.assertEqual(child.stderr, "", "Competing child stderr (redacted)")
                self.assertIn(child.stdout.strip(), ("BUSY", "COMMITTED"))
                observed.append(child.stdout.strip())
            return accepted
        self.core._role = checked_then_competed
        try:
            if not observed:
                # Original vulnerable implementation lets child revoke first,
                # then returns an improperly accepted stale editor permission.
                # Atomic implementation holds the writer lock first, and
                # the child's real downgrade attempt fails BUSY until commit.
                try:
                    self.core.add_note(self.editor, self.matter["id"],
                                       "FICTIONAL SERIALIZED NOTE")
                    wrote = True
                except Denied:
                    wrote = False
        finally:
            self.core._role = original_role
        self.assertEqual(len(observed), 1)
        notes = self.core.read_notes(self.owner, self.matter["id"])
        if observed[0] == "COMMITTED":
            self.assertFalse(wrote, "STALE_REVOKED_EDITOR_WROTE_NOTE")
            self.assertEqual(notes, [])
        else:
            self.assertTrue(wrote, "AUTHORIZED_WRITER_NOT_COMPLETED")
            self.assertEqual(len(notes), 1)
            # After writer completes, owner may legally revoke the editor.
            self.core.grant(self.owner, self.matter["id"], self.editor_id,
                            "viewer", 2)
            with self.assertRaises(Denied):
                self.core.add_note(self.editor, self.matter["id"],
                                   "AFTER_REVOCATION_SHOULD_DENY")


    def test_owner_token_revocation_race_cannot_grant_new_access(self):
        """Second process revokes the owner after role admission, before grant.

        Must serialize either grant-then-revoke, or revoke-then-deny grant.
        No permission may be granted after a completed revocation.
        """
        original_role = self.core._role
        seen = []
        target_id, _ = self.core.provision_user(self.firm, "New Fictional Viewer")
        import hashlib
        digest = hashlib.sha256(self.owner.encode()).hexdigest()
        def role_and_compete(identity, matter_id, allowed):
            result = original_role(identity, matter_id, allowed)
            if not seen and identity["id"] == self.owner_id:
                code = (
                    "import sqlite3,sys; "
                    "c=sqlite3.connect(sys.argv[1],timeout=0.3,isolation_level=None); "
                    "c.execute('PRAGMA busy_timeout=300')\n"
                    "try:\n"
                    " c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',(sys.argv[2],)); "
                    " print('COMMITTED')\n"
                    "except sqlite3.OperationalError as e:\n"
                    " if 'locked' not in str(e).lower(): raise\n"
                    " print('BUSY')\n"
                    "finally:\n c.close()"
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, str(self.path), digest],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True, text=True, timeout=12, check=False)
                self.assertEqual(child.returncode, 0, "Revocation child failed (redacted)")
                self.assertEqual(child.stderr, "", "Revocation child stderr (redacted)")
                seen.append(child.stdout.strip())
                self.assertIn(seen[0], ("COMMITTED", "BUSY"))
            return result
        self.core._role = role_and_compete
        try:
            try:
                self.core.grant(self.owner, self.matter["id"], target_id, "viewer", 2)
                wrote = True
            except Denied:
                wrote = False
        finally:
            self.core._role = original_role
        self.assertEqual(len(seen), 1)
        granted = self.core.db.execute(
            "SELECT role FROM grants WHERE matter_id=? AND user_id=?",
            (self.matter["id"], target_id)).fetchone()
        if seen[0] == "COMMITTED":
            self.assertFalse(wrote, "REVOKED_OWNER_GRANTED_NEW_ACCESS")
            self.assertIsNone(granted, "REVOKED_OWNER_GRANT_PERSISTED")
        else:
            self.assertTrue(wrote, "LOCKED_GRANT_DID_NOT_COMPLETE")
            self.assertEqual(granted["role"], "viewer")

    def test_cross_process_revocation_between_identity_and_create_matter(self):
        """A committed revocation must not be followed by stale matter creation."""
        original = self.core._identity
        outcomes = []
        def identity_then_revoke(token):
            identity = original(token)
            if not outcomes and token == self.owner:
                code = (
                    "import sqlite3,sys; from hashlib import sha256; "
                    "c=sqlite3.connect(sys.argv[1],timeout=.25,isolation_level=None); "
                    "c.execute('PRAGMA busy_timeout=250')\n"
                    "try:\n"
                    " cur=c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',"
                    "(sha256(sys.argv[2].encode()).hexdigest(),)); "
                    "print('COMMITTED' if cur.rowcount==1 else 'MISSING')\n"
                    "except sqlite3.OperationalError as e:\n"
                    " print('BUSY' if 'locked' in str(e).lower() else 'ERROR')\n"
                    "finally: c.close()"
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, str(self.path), token],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True, text=True, timeout=12)
                self.assertEqual(child.returncode, 0, "Revocation child failed (redacted)")
                outcomes.append(child.stdout.strip())
            return identity
        self.core._identity = identity_then_revoke
        try:
            before = self.core.db.execute("SELECT count(*) FROM matters").fetchone()[0]
            audit_before = self.core.audit_head()
            try:
                self.core.create_matter(self.owner, "STALE OWNER MATTER")
                created = True
            except Denied:
                created = False
        finally:
            self.core._identity = original
        self.assertEqual(len(outcomes), 1)
        after = self.core.db.execute("SELECT count(*) FROM matters").fetchone()[0]
        if outcomes[0] == "COMMITTED":
            self.assertFalse(created, "REVOKED OWNER CREATED MATTER")
            self.assertEqual(after, before)
            self.assertEqual(self.core.audit_head(), audit_before)
        else:
            self.assertEqual(outcomes[0], "BUSY")
            self.assertTrue(created)
            self.assertEqual(self.core.audit_head()["seq"], audit_before["seq"] + 1)
        self.assertTrue(self.core.verify_audit())

    def test_cross_process_acl_downgrade_between_role_and_create_task(self):
        """A committed editor downgrade must not be followed by task creation."""
        original = self.core._role
        outcomes = []
        def role_then_downgrade(identity, matter_id, allowed):
            result = original(identity, matter_id, allowed)
            if not outcomes and identity["id"] == self.editor_id:
                code = (
                    "import sqlite3,sys; from src.secure_engine import SecureCore; "
                    "c=None\ntry:\n"
                    " c=SecureCore(sys.argv[1]); c.db.execute('PRAGMA busy_timeout=250')\n"
                    " c.grant(sys.argv[2],sys.argv[3],sys.argv[4],'viewer',2)\n"
                    " print('COMMITTED')\n"
                    "except sqlite3.OperationalError as e:\n"
                    " print('BUSY' if 'locked' in str(e).lower() else 'ERROR')\n"
                    "finally:\n"
                    " if c is not None: c.close()"
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, str(self.path), self.owner,
                     self.matter["id"], self.editor_id],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True, text=True, timeout=12)
                self.assertEqual(child.returncode, 0, "Downgrade child failed (redacted)")
                outcomes.append(child.stdout.strip())
            return result
        self.core._role = role_then_downgrade
        try:
            before = self.core.db.execute("SELECT count(*) FROM tasks").fetchone()[0]
            audit_before = self.core.audit_head()
            try:
                self.core.create_task(self.editor, self.matter["id"],
                                      "STALE EDITOR TASK", "2026-12-01T00:00:00Z")
                created = True
            except Denied:
                created = False
        finally:
            self.core._role = original
        self.assertEqual(len(outcomes), 1)
        after = self.core.db.execute("SELECT count(*) FROM tasks").fetchone()[0]
        if outcomes[0] == "COMMITTED":
            self.assertFalse(created, "DOWNGRADED EDITOR CREATED TASK")
            self.assertEqual(after, before)
            self.assertEqual(self.core.audit_head(), audit_before)
        else:
            self.assertEqual(outcomes[0], "BUSY")
            self.assertTrue(created)
            self.assertEqual(self.core.audit_head()["seq"], audit_before["seq"] + 1)
        self.assertTrue(self.core.verify_audit())

    def test_cross_process_revocation_between_identity_and_token_rotation(self):
        """A completed revocation must not be followed by minting a new session."""
        from hashlib import sha256
        original = self.core._identity
        outcomes = []
        def identity_then_revoke(token):
            identity = original(token)
            if not outcomes and token == self.owner:
                code = (
                    "import sqlite3,sys; from hashlib import sha256; "
                    "c=sqlite3.connect(sys.argv[1],timeout=.25,isolation_level=None); "
                    "c.execute('PRAGMA busy_timeout=250')\n"
                    "try:\n"
                    " cur=c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',"
                    "(sha256(sys.argv[2].encode()).hexdigest(),)); "
                    "print('COMMITTED' if cur.rowcount==1 else 'MISSING')\n"
                    "except sqlite3.OperationalError as e:\n"
                    " print('BUSY' if 'locked' in str(e).lower() else 'ERROR')\n"
                    "finally: c.close()"
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, str(self.path), token],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True, text=True, timeout=12)
                self.assertEqual(child.returncode, 0, "Revocation child failed (redacted)")
                outcomes.append(child.stdout.strip())
            return identity
        self.core._identity = identity_then_revoke
        try:
            before = self.core.db.execute(
                "SELECT count(*) FROM credentials WHERE user_id=? AND revoked=0",
                (self.owner_id,)).fetchone()[0]
            audit_before = self.core.audit_head()
            try:
                self.core.rotate_token(self.owner)
                rotated = True
            except Denied:
                rotated = False
        finally:
            self.core._identity = original
        after = self.core.db.execute(
            "SELECT count(*) FROM credentials WHERE user_id=? AND revoked=0",
            (self.owner_id,)).fetchone()[0]
        self.assertEqual(len(outcomes), 1)
        if outcomes[0] == "COMMITTED":
            self.assertFalse(rotated, "REVOKED SESSION MINTED A NEW TOKEN")
            self.assertEqual(after, before - 1)
            self.assertEqual(self.core.audit_head(), audit_before)
        else:
            self.assertEqual(outcomes[0], "BUSY")
            self.assertTrue(rotated)
            self.assertEqual(self.core.audit_head()["seq"], audit_before["seq"] + 1)
        self.assertTrue(self.core.verify_audit())


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



    def test_recovery_code_issuance_serializes_with_cross_process_revocation(self):
        """A committed revocation cannot be followed by stale recovery-code issuance."""
        original = self.core._identity
        outcomes = []
        def identity_then_revoke(token):
            identity = original(token)
            if not outcomes and token == self.owner:
                code = (
                    "import sqlite3,sys; from hashlib import sha256; "
                    "c=sqlite3.connect(sys.argv[1],timeout=.25,isolation_level=None); "
                    "c.execute('PRAGMA busy_timeout=250')\n"
                    "try:\n"
                    " cur=c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',"
                    "(sha256(sys.argv[2].encode()).hexdigest(),)); "
                    " print('COMMITTED' if cur.rowcount==1 else 'MISSING')\n"
                    "except sqlite3.OperationalError as e:\n"
                    " print('BUSY' if 'locked' in str(e).lower() else 'ERROR')\n"
                    "finally: c.close()"
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, str(self.path), token],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True, text=True, timeout=12)
                self.assertEqual(child.returncode, 0, "Revocation child failed (redacted)")
                self.assertEqual(child.stderr, "", "Revocation child stderr (redacted)")
                outcomes.append(child.stdout.strip())
            return identity
        self.core._identity = identity_then_revoke
        before = self.core.audit_head()
        try:
            try:
                issued = self.core.issue_recovery_code(self.owner)
            except Denied:
                issued = None
        finally:
            self.core._identity = original
        self.assertEqual(len(outcomes), 1)
        if outcomes[0] == "COMMITTED":
            self.assertIsNone(issued, "REVOKED SESSION ISSUED A RECOVERY CODE")
            self.assertEqual(self.core.audit_head(), before)
            self.assertEqual(self.core.db.execute(
                "SELECT count(*) FROM recovery_codes WHERE user_id=?",
                (self.owner_id,)).fetchone()[0], 0)
        else:
            self.assertEqual(outcomes[0], "BUSY")
            self.assertIsNotNone(issued)
            self.assertEqual(self.core.audit_head()["seq"], before["seq"] + 1)
        self.assertTrue(self.core.verify_audit())

    def test_token_revocation_serializes_with_cross_process_revocation(self):
        """A stale session cannot append a revocation action after revocation wins."""
        original = self.core._identity
        outcomes = []
        def identity_then_revoke(token):
            identity = original(token)
            if not outcomes and token == self.editor:
                code = (
                    "import sqlite3,sys; from hashlib import sha256; "
                    "c=sqlite3.connect(sys.argv[1],timeout=.25,isolation_level=None); "
                    "c.execute('PRAGMA busy_timeout=250')\n"
                    "try:\n"
                    " cur=c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',"
                    "(sha256(sys.argv[2].encode()).hexdigest(),)); "
                    " print('COMMITTED' if cur.rowcount==1 else 'MISSING')\n"
                    "except sqlite3.OperationalError as e:\n"
                    " print('BUSY' if 'locked' in str(e).lower() else 'ERROR')\n"
                    "finally: c.close()"
                )
                child = subprocess.run(
                    [sys.executable, "-c", code, str(self.path), token],
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True, text=True, timeout=12)
                self.assertEqual(child.returncode, 0, "Revocation child failed (redacted)")
                self.assertEqual(child.stderr, "", "Revocation child stderr (redacted)")
                outcomes.append(child.stdout.strip())
            return identity
        self.core._identity = identity_then_revoke
        before = self.core.audit_head()
        try:
            try:
                self.core.revoke_token(self.editor)
                revoked = True
            except Denied:
                revoked = False
        finally:
            self.core._identity = original
        self.assertEqual(len(outcomes), 1)
        if outcomes[0] == "COMMITTED":
            self.assertFalse(revoked, "REVOKED SESSION PERFORMED A LATER WRITE")
            self.assertEqual(self.core.audit_head(), before)
        else:
            self.assertEqual(outcomes[0], "BUSY")
            self.assertTrue(revoked)
            self.assertEqual(self.core.audit_head()["seq"], before["seq"] + 1)
        self.assertTrue(self.core.verify_audit())


    def test_offline_recovery_code_is_consumed_once_across_processes(self):
        """A recovery code can create only one replacement session."""
        code = self.core.issue_recovery_code(self.owner)
        child_success = "\n".join([
            "import sys",
            "from src.secure_engine import SecureCore",
            "c=SecureCore(sys.argv[1])",
            "c.recover_offline(sys.argv[2],sys.argv[3])",
            "c.close()",
            "print('PASS')",
        ])
        self.child(child_success, self.owner_id, code)
        child_denied = "\n".join([
            "import sys",
            "from src.secure_engine import SecureCore, Denied",
            "c=SecureCore(sys.argv[1])",
            "try:",
            " c.recover_offline(sys.argv[2],sys.argv[3])",
            "except Denied:",
            " print('DENIED')",
            "else:",
            " raise AssertionError('RECOVERY_CODE_REUSED')",
            "finally:",
            " c.close()",
        ])
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", child_denied, str(self.path), self.owner_id, code],
            cwd=str(Path(__file__).resolve().parents[1]), env=env,
            capture_output=True, text=True, timeout=25, check=False)
        self.assertEqual(result.returncode, 0, "Second recovery child failed (redacted)")
        self.assertEqual(result.stdout.strip(), "DENIED")
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM recovery_codes WHERE user_id=? AND used=0",
            (self.owner_id,)).fetchone()[0], 0)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM credentials WHERE user_id=? AND revoked=0",
            (self.owner_id,)).fetchone()[0], 1)
        self.assertTrue(self.core.verify_audit())
        self.assertEqual(self.core.audit_head()["seq"], 4)


    def _competing_sql(self, sql, *params):
        """Run a real second-process write and return only its lock outcome."""
        code = """import sqlite3,sys
c=sqlite3.connect(sys.argv[1],timeout=.2,isolation_level=None)
c.execute('PRAGMA busy_timeout=200')
try:
 cur=c.execute(sys.argv[2],tuple(sys.argv[3:]))
 print('COMMITTED' if cur.rowcount else 'MISSING')
except sqlite3.OperationalError as e:
 print('BUSY' if 'locked' in str(e).lower() else 'ERROR')
finally:
 c.close()
"""
        result=subprocess.run(
            [sys.executable,"-c",code,str(self.path),sql,*map(str,params)],
            cwd=str(Path(__file__).resolve().parents[1]),
            capture_output=True,text=True,timeout=12,check=False)
        self.assertEqual(result.returncode,0,"Competing process failed (output redacted)")
        self.assertEqual(result.stderr,"","Competing process stderr (redacted)")
        return result.stdout.strip()

    def test_read_notes_serializes_with_cross_process_acl_downgrade(self):
        """A concurrent downgrade cannot race the confidential-note read."""
        self.core.add_note(self.owner,self.matter["id"],"FICTIONAL CONFIDENTIAL NOTE")
        original=self.core._role
        outcomes=[]
        def role_then_downgrade(identity,matter_id,allowed):
            result=original(identity,matter_id,allowed)
            if not outcomes and identity["id"]==self.editor_id:
                outcomes.append(self._competing_sql(
                    "UPDATE grants SET role='viewer' WHERE matter_id=? AND user_id=?",
                    matter_id,self.editor_id))
            return result
        self.core._role=role_then_downgrade
        before=self.core.audit_head()
        try:
            notes=self.core.read_notes(self.editor,self.matter["id"])
        finally:
            self.core._role=original
        self.assertEqual(outcomes,["BUSY"],
                         "ACL downgrade committed between authorization and confidential read")
        self.assertEqual(len(notes),1)
        self.assertEqual(notes[0]["text"],"FICTIONAL CONFIDENTIAL NOTE")
        self.assertEqual(self.core.audit_head(),before)
        self.assertTrue(self.core.verify_audit())
        self.child(
            "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
            "c.execute(\"UPDATE grants SET role='viewer' WHERE matter_id=? AND user_id=?\","
            "(sys.argv[2],sys.argv[3])); c.commit(); c.close(); print('PASS')",
            self.matter["id"],self.editor_id)
        with self.assertRaises(Denied):
            self.core.add_note(self.editor,self.matter["id"],"MUST BE DENIED")

    def test_list_matters_serializes_with_cross_process_credential_revocation(self):
        """Revocation cannot race credential admission and matter metadata return."""
        import hashlib
        digest=hashlib.sha256(self.editor.encode()).hexdigest()
        original=self.core._identity
        outcomes=[]
        def identity_then_revoke(token):
            identity=original(token)
            if not outcomes and token==self.editor:
                outcomes.append(self._competing_sql(
                    "UPDATE credentials SET revoked=1 WHERE token_digest=?",digest))
            return identity
        self.core._identity=identity_then_revoke
        before=self.core.audit_head()
        try:
            matters=self.core.list_matters(self.editor)
        finally:
            self.core._identity=original
        self.assertEqual(outcomes,["BUSY"],
                         "Credential revocation committed before matter metadata was returned")
        self.assertEqual(len(matters),1)
        self.assertEqual(matters[0]["id"],self.matter["id"])
        self.assertEqual(self.core.audit_head(),before)
        self.assertTrue(self.core.verify_audit())
        self.child(
            "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
            "c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',(sys.argv[2],)); "
            "c.commit(); c.close(); print('PASS')",digest)
        with self.assertRaises(Denied):
            self.core.list_matters(self.editor)


    def test_dashboard_serializes_with_cross_process_credential_revocation(self):
        """A revoked session cannot race dashboard task metadata retrieval."""
        self.core.create_task(self.editor,self.matter["id"],"FICTIONAL DASHBOARD TASK",
                              "2026-12-02T00:00:00Z")
        import hashlib
        digest=hashlib.sha256(self.editor.encode()).hexdigest()
        original=self.core._identity
        outcomes=[]
        def identity_then_revoke(token):
            identity=original(token)
            if not outcomes and token==self.editor:
                outcomes.append(self._competing_sql(
                    "UPDATE credentials SET revoked=1 WHERE token_digest=?",digest))
            return identity
        self.core._identity=identity_then_revoke
        before=self.core.audit_head()
        try:
            dashboard=self.core.dashboard(self.editor)
        finally:
            self.core._identity=original
        self.assertEqual(outcomes,["BUSY"],
                         "Credential revocation raced dashboard data retrieval")
        self.assertEqual(dashboard["matter_count"],1)
        self.assertEqual(len(dashboard["upcoming_tasks"]),1)
        self.assertEqual(self.core.audit_head(),before)
        self.assertTrue(self.core.verify_audit())
        self.child(
            "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
            "c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',(sys.argv[2],)); "
            "c.commit(); c.close(); print('PASS')",digest)
        with self.assertRaises(Denied):
            self.core.dashboard(self.editor)


    def test_workbench_matter_snapshot_serializes_with_cross_process_acl_downgrade(self):
        from src.attorney_workbench import AttorneyWorkbench
        original=self.core._role
        outcomes=[]
        def role_then_downgrade(identity,matter_id,allowed):
            result=original(identity,matter_id,allowed)
            if not outcomes and identity["id"]==self.editor_id:
                outcomes.append(self._competing_sql(
                    "UPDATE grants SET role='viewer' WHERE matter_id=? AND user_id=?",
                    matter_id,self.editor_id))
            return result
        self.core._role=role_then_downgrade
        before=self.core.audit_head()
        try:
            view=AttorneyWorkbench(self.core).matter(
                self.editor,self.matter["id"])
        finally:
            self.core._role=original
        self.assertEqual(outcomes,["BUSY"])
        self.assertTrue(view["can_complete_tasks"])
        self.assertEqual(self.core.audit_head(),before)
        self.assertTrue(self.core.verify_audit())
        self.child(
            "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
            "c.execute(\"UPDATE grants SET role='viewer' WHERE matter_id=? AND user_id=?\","
            "(sys.argv[2],sys.argv[3])); c.commit(); c.close(); print('PASS')",
            self.matter["id"],self.editor_id)
        current=AttorneyWorkbench(self.core).matter(self.editor,self.matter["id"])
        self.assertFalse(current["can_complete_tasks"])

    def test_research_evidence_add_serializes_with_cross_process_revocation(self):
        from src.research_evidence import ResearchEvidence
        original=self.core._role
        outcomes=[]
        def role_then_revoke(identity,matter_id,allowed):
            result=original(identity,matter_id,allowed)
            if not outcomes and identity["id"]==self.editor_id:
                import hashlib
                digest=hashlib.sha256(self.editor.encode()).hexdigest()
                outcomes.append(self._competing_sql(
                    "UPDATE credentials SET revoked=1 WHERE token_digest=?",digest))
            return result
        self.core._role=role_then_revoke
        before=self.core.audit_head()
        try:
            created=ResearchEvidence(self.core).add(
                self.editor,self.matter["id"],"Fictional source",
                "https://example.gov/rule","Fictional excerpt")
        finally:
            self.core._role=original
        self.assertEqual(outcomes,["BUSY"])
        self.assertEqual(self.core.audit_head()["seq"],before["seq"]+1)
        self.assertTrue(self.core.verify_audit())
        rows=self.core.db.execute(
            "SELECT id FROM research_evidence WHERE matter_id=?",(self.matter["id"],)).fetchall()
        self.assertEqual(len(rows),1)
        self.child(
            "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
            "c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',(sys.argv[2],)); "
            "c.commit(); c.close(); print('PASS')",
            __import__("hashlib").sha256(self.editor.encode()).hexdigest())
        with self.assertRaises(Denied):
            ResearchEvidence(self.core).add(
                self.editor,self.matter["id"],"Must deny",
                "https://example.gov/other","No write after revocation")
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM research_evidence WHERE matter_id=?",
            (self.matter["id"],)).fetchone()[0],1)
        self.assertTrue(self.core.verify_audit())

    def test_preview_ticket_issue_serializes_with_cross_process_revocation(self):
        from src.preview_session import PreviewSessionBroker
        broker=PreviewSessionBroker(self.core)
        original=self.core._role
        outcomes=[]
        def role_then_revoke(identity,matter_id,allowed):
            result=original(identity,matter_id,allowed)
            if not outcomes and identity["id"]==self.editor_id:
                import hashlib
                digest=hashlib.sha256(self.editor.encode()).hexdigest()
                outcomes.append(self._competing_sql(
                    "UPDATE credentials SET revoked=1 WHERE token_digest=?",digest))
            return result
        self.core._role=role_then_revoke
        try:
            issued=broker.issue(self.editor,self.matter["id"])
        finally:
            self.core._role=original
        self.assertEqual(outcomes,["BUSY"])
        self.assertTrue(issued["single_use"])
        self.child(
            "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
            "c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',(sys.argv[2],)); "
            "c.commit(); c.close(); print('PASS')",
            __import__("hashlib").sha256(self.editor.encode()).hexdigest())
        with self.assertRaises(Denied):
            broker.issue(self.editor,self.matter["id"])
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM preview_ticket WHERE user_id=?",
            (self.editor_id,)).fetchone()[0],1)
        self.assertTrue(self.core.verify_audit())

    def test_source_observation_capture_serializes_with_cross_process_revocation(self):
        from src.research_evidence import ResearchEvidence
        from src.source_observation import SourceObservation
        evidence=ResearchEvidence(self.core).add(
            self.owner,self.matter["id"],"Fictional source",
            "https://example.gov/rule","Fictional excerpt")
        original=self.core._role
        outcomes=[]
        def role_then_revoke(identity,matter_id,allowed):
            result=original(identity,matter_id,allowed)
            if not outcomes and identity["id"]==self.editor_id:
                import hashlib
                digest=hashlib.sha256(self.editor.encode()).hexdigest()
                outcomes.append(self._competing_sql(
                    "UPDATE credentials SET revoked=1 WHERE token_digest=?",digest))
            return result
        self.core._role=role_then_revoke
        before=self.core.audit_head()
        try:
            observed=SourceObservation(self.core).capture(
                self.editor,self.matter["id"],evidence["id"],
                "Fictional captured text","Manual fictional verification note")
        finally:
            self.core._role=original
        self.assertEqual(outcomes,["BUSY"])
        self.assertEqual(self.core.audit_head()["seq"],before["seq"]+1)
        self.assertTrue(self.core.verify_audit())
        self.child(
            "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); "
            "c.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',(sys.argv[2],)); "
            "c.commit(); c.close(); print('PASS')",
            __import__("hashlib").sha256(self.editor.encode()).hexdigest())
        with self.assertRaises(Denied):
            SourceObservation(self.core).capture(
                self.editor,self.matter["id"],evidence["id"],
                "Must not be captured","This must be rejected after revocation")
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM source_observation WHERE matter_id=?",
            (self.matter["id"],)).fetchone()[0],1)
        self.assertTrue(self.core.verify_audit())

    def test_workbench_completion_rejects_task_from_different_selected_matter(self):
        from src.attorney_workbench import AttorneyWorkbench
        second=self.core.create_matter(self.owner,"FICTIONAL SECOND MATTER")
        task=self.core.create_task(self.owner,self.matter["id"],"FICTIONAL TASK",
                                   "2026-12-03T00:00:00Z")
        before=self.core.audit_head()
        with self.assertRaises(Denied):
            AttorneyWorkbench(self.core).complete(
                self.owner,second["id"],task["id"],1)
        row=self.core.db.execute(
            "SELECT completed,version FROM tasks WHERE id=?",(task["id"],)).fetchone()
        self.assertEqual((row["completed"],row["version"]),(0,1))
        self.assertEqual(self.core.audit_head(),before)
        self.assertTrue(self.core.verify_audit())

if __name__ == "__main__":
    unittest.main()
