"""Independent-process task finality tests: fictional offline SQLite only.

These are deterministic local crash acceptance probes, not external custody
attestations. A lost reply after commit remains uncertain to the caller.
No worker retries or clears pending write reservations.
"""
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from src.secure_engine import SecureCore, Stale

ROOT = Path(__file__).resolve().parents[1]

WORKER = r'''
import json, os, signal, sys, time
from pathlib import Path
from src.secure_engine import SecureCore
args=json.loads(sys.stdin.readline())
core=SecureCore(args["db"])
def terminate():
    os.kill(os.getpid(), signal.SIGKILL)
try:
    stage=args["stage"]
    if stage=="before_identity":
        core._identity=lambda token: terminate()
        core.complete_task(args["token"],args["task"],1)
    elif stage=="before_commit":
        core._audit=lambda actor,action,target: terminate()
        core.complete_task(args["token"],args["task"],1)
    elif stage=="after_commit":
        core.complete_task(args["token"],args["task"],1)
        terminate()
    elif stage=="held_writer":
        original=core._identity
        def held(token):
            Path(args["marker"]).write_text("reserved",encoding="ascii")
            until=time.monotonic()+8
            while not Path(args["release"]).exists():
                if time.monotonic()>until: raise RuntimeError("barrier timeout")
                time.sleep(.015)
            return original(token)
        core._identity=held
        core.complete_task(args["token"],args["task"],1)
        print("COMMITTED",flush=True)
    elif stage=="racing_writer":
        try:
            core.complete_task(args["token"],args["task"],1)
            print("UNEXPECTED_COMMIT",flush=True)
        except Exception as exc:
            print(type(exc).__name__,flush=True)
    else:
        raise ValueError("unknown crash stage")
finally:
    core.close()
'''


class IndependentProcessTaskFinality(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=str(Path(self.tmp.name)/"fictional.sqlite3")
        core=SecureCore(self.path)
        firm=core.provision_firm("Fictional Independent Crash Firm")
        _,self.token=core.provision_user(firm,"Fictional Operator")
        matter=core.create_matter(self.token,"Fictional Crash Matter")
        task=core.create_task(self.token,matter["id"],"Fictional Crash Task",
                              "2026-10-01T00:00:00Z")
        self.task=task["id"]
        core.close()

    def launch(self, stage, **other):
        env=os.environ.copy()
        env["PYTHONPATH"]=str(ROOT)
        args={"stage":stage,"db":self.path,"token":self.token,
              "task":self.task,**other}
        p=subprocess.Popen([sys.executable,"-c",WORKER],
                           cwd=str(ROOT),env=env,stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           text=True)
        p.stdin.write(json.dumps(args)+"\n")
        p.stdin.close()
        p.stdin=None
        return p

    def snapshot(self):
        # Read only after child exits: task, audit and chain must agree.
        core=SecureCore(self.path)
        try:
            row=core.db.execute(
                "SELECT completed,version FROM tasks WHERE id=?",
                (self.task,)).fetchone()
            events=core.db.execute(
                "SELECT count(*) FROM audit_chain WHERE action='task.complete' AND target=?",
                (self.task,)).fetchone()[0]
            self.assertTrue(core.verify_audit())
            return row["completed"],row["version"],events
        finally:
            core.close()

    def test_actual_sigkill_before_identity_and_before_commit_rolls_back(self):
        for stage in ("before_identity","before_commit"):
            with self.subTest(stage=stage):
                child=self.launch(stage)
                out,err=child.communicate(timeout=12)
                self.assertEqual(child.returncode,-signal.SIGKILL,(out,err))
                self.assertEqual(self.snapshot(),(0,1,0))

    def test_actual_sigkill_after_commit_persists_one_atomic_result(self):
        child=self.launch("after_commit")
        out,err=child.communicate(timeout=12)
        self.assertEqual(child.returncode,-signal.SIGKILL,(out,err))
        self.assertEqual(self.snapshot(),(1,2,1))
        # A missing acknowledgment NEVER authorizes automatic retry.
        core=SecureCore(self.path)
        try:
            with self.assertRaises(Stale):
                core.complete_task(self.token,self.task,1)
        finally:
            core.close()
        self.assertEqual(self.snapshot(),(1,2,1))

    def test_independent_process_writers_have_single_finalized_result(self):
        marker=Path(self.tmp.name)/"reserved.marker"
        release=Path(self.tmp.name)/"release.marker"
        first=self.launch("held_writer",marker=str(marker),release=str(release))
        second=None
        try:
            deadline=time.monotonic()+8
            while not marker.exists() and time.monotonic()<deadline:
                self.assertIsNone(first.poll(),"first process failed before reservation")
                time.sleep(.015)
            self.assertTrue(marker.exists(),"first process never reserved writer")
            second=self.launch("racing_writer")
            time.sleep(.1)
            self.assertIsNone(second.poll(),"racer bypassed held SQLite reservation")
            release.write_text("proceed",encoding="ascii")
            out1,err1=first.communicate(timeout=12)
            out2,err2=second.communicate(timeout=12)
            self.assertEqual(first.returncode,0,(out1,err1))
            self.assertEqual(second.returncode,0,(out2,err2))
            self.assertIn("COMMITTED",out1)
            self.assertIn("Stale",out2)
            self.assertEqual(self.snapshot(),(1,2,1))
        finally:
            release.write_text("proceed",encoding="ascii")
            for p in (first,second):
                if p is not None and p.poll() is None:
                    p.kill()
                    p.communicate(timeout=5)


if __name__=="__main__":
    unittest.main()
