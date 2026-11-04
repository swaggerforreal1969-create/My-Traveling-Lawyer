"""Real multi-process SQLite custody admission, crash and lost-ACK acceptance.

All signers/credentials are fictional test fixtures. This exercises local
transaction mechanics ONLY; NOT independent custody or production approval.
"""
import hashlib
import hmac
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

ROOT=Path(__file__).resolve().parents[1]
KEY=b'fictional-offline-admission-process-test-key'
GENESIS='a'*64
SIGNER='fictional-process-signer'

WORKER=r"""
import hashlib,hmac,json,os,signal,sqlite3,sys
from src.checkpoint_admission_prototype import LocalCheckpointAdmissionPrototype
from src.independent_checkpoint_boundary import PinnedCheckpoint,CheckpointReadbackBoundary
from src.secure_engine import Denied
KEY=b'fictional-offline-admission-process-test-key'
SIGNER='fictional-process-signer'
def sign(identity,payload):
    if identity!=SIGNER:raise Denied('fictional signer identity wrong')
    if args['stage']=='kill_precommit':
        os.kill(os.getpid(),signal.SIGKILL)
    return hmac.new(KEY,payload,hashlib.sha256).hexdigest()
def verify(identity,payload,signature):
    return (identity==SIGNER and hmac.compare_digest(
        hmac.new(KEY,payload,hashlib.sha256).hexdigest(),signature))
args=json.loads(sys.stdin.readline())
pin=PinnedCheckpoint(args['pin_seq'],args['pin_digest'],SIGNER)
p=LocalCheckpointAdmissionPrototype(
    args['path'],genesis=PinnedCheckpoint(0,'a'*64,SIGNER),
    authenticate=lambda cred:cred=='fictional-authorized' and
        args['stage']!='revoke_credential',
    sign=sign,signer_id=SIGNER)
try:
    if args['stage']=='revoke_signer':
        p.revoke_signer()
        print(json.dumps({'status':'revoked'}),flush=True)
    elif args['stage']=='read_only':
        result=CheckpointReadbackBoundary(
            provider=p,pinned=pin,verify_signature=verify).verify(
            reservation=args['reservation'],event_digest=args['event_digest'])
        print(json.dumps({'status':'observed','seq':result.sequence,
                          'independent':result.independently_custodied}),
              flush=True)
    else:
        reply=p.admit(credential='fictional-authorized',
            reservation=args['reservation'],nonce=args['nonce'],
            event_digest=args['event_digest'],expected=pin)
        if args['stage']=='kill_postcommit':
            os.kill(os.getpid(),signal.SIGKILL)
        print(json.dumps({'status':'ack','seq':reply['sequence'],
                          'head_digest':reply['head_digest']}),flush=True)
except Exception as exc:
    print(json.dumps({'status':'denied','error':type(exc).__name__}),
          flush=True)
"""
HOLDER=r"""
import sqlite3,sys
db=sqlite3.connect(sys.argv[1],timeout=5,isolation_level=None)
db.execute('BEGIN IMMEDIATE')
print('LOCK_ACQUIRED',flush=True)
sys.stdin.readline()
db.execute('ROLLBACK')
"""


class AtomicCustodyProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'fictional-custody.sqlite3'
        self.pin={'pin_seq':0,'pin_digest':GENESIS}
        self.res='b'*64
        self.nonce='c'*64
        self.event='d'*64

    def command(self,stage='normal',**override):
        args=dict(self.pin,path=str(self.path),stage=stage,
                  reservation=self.res,nonce=self.nonce,
                  event_digest=self.event)
        args.update(override)
        env=os.environ.copy()
        env['PYTHONPATH']=str(ROOT)
        return ([sys.executable,'-c',WORKER],json.dumps(args)+'\n',env)

    def run_worker(self,stage='normal',**override):
        cmd,stdin,env=self.command(stage,**override)
        p=subprocess.run(cmd,input=stdin,text=True,capture_output=True,
                         cwd=str(ROOT),env=env,timeout=14)
        return p.returncode,json.loads(p.stdout) if p.stdout.strip() else None,p.stderr

    def rows(self):
        if not self.path.exists():return []
        with sqlite3.connect(self.path) as db:
            return db.execute(
                'SELECT sequence,nonce,reservation_digest,event_digest,previous,'
                'head_digest FROM checkpoint_events ORDER BY sequence').fetchall()

    @unittest.skipUnless(os.name=='posix','SIGKILL is POSIX-specific')
    def test_sigkill_before_commit_rolls_back_nonce_and_head(self):
        code,result,err=self.run_worker('kill_precommit')
        self.assertEqual(code,-signal.SIGKILL,(result,err))
        self.assertEqual(self.rows(),[])
        code,result,err=self.run_worker()
        self.assertEqual((code,result['status'],result['seq']),(0,'ack',1))
        self.assertEqual(len(self.rows()),1)

    @unittest.skipUnless(os.name=='posix','SIGKILL is POSIX-specific')
    def test_sigkill_postcommit_ackloss_requires_readonly_reconciliation(self):
        code,result,err=self.run_worker('kill_postcommit')
        self.assertEqual(code,-signal.SIGKILL,(result,err))
        before=self.rows()
        self.assertEqual(len(before),1)
        code,view,err=self.run_worker('read_only')
        self.assertEqual((code,view['status'],view['seq']),(0,'observed',1))
        self.assertFalse(view['independent'])
        # An uncertain admission must not be replayed. This is an explicit
        # adversarial denied duplicate check, never a retry mechanism.
        code,denied,err=self.run_worker()
        self.assertEqual((code,denied['status']),(0,'denied'))
        self.assertEqual(self.rows(),before)

    def test_two_competing_processes_one_cas_winner(self):
        calls=[self.command(reservation=(letter*64),nonce=(n*64))
               for letter,n in (('b','c'),('e','f'))]
        procs=[subprocess.Popen(cmd,stdin=subprocess.PIPE,
                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                   env=env,cwd=str(ROOT),text=True)
               for cmd,_,env in calls]
        try:
            answers=[]
            for p,(_,data,_) in zip(procs,calls):
                out,err=p.communicate(data,timeout=14)
                self.assertEqual(p.returncode,0,err)
                answers.append(json.loads(out)['status'])
            self.assertEqual(sorted(answers),['ack','denied'])
            self.assertEqual(len(self.rows()),1)
        finally:
            for p in procs:
                if p.poll() is None:p.kill();p.communicate(timeout=4)

    def test_independent_sqlite_lock_contention_waits_without_double_commit(self):
        # Bootstrap the schema first, then reserve a real second-process writer.
        code,reply,err=self.run_worker('revoke_credential')
        self.assertEqual((code,reply['status']),(0,'denied'),err)
        holder=subprocess.Popen([sys.executable,'-c',HOLDER,str(self.path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,cwd=str(ROOT))
        try:
            self.assertEqual(holder.stdout.readline().strip(),'LOCK_ACQUIRED')
            started=time.perf_counter()
            cmd,data,env=self.command()
            writer=subprocess.Popen(cmd,stdin=subprocess.PIPE,
                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                  cwd=str(ROOT),env=env,text=True)
            try:
                time.sleep(0.25)
                holder.stdin.write('\n');holder.stdin.flush()
                out,err=writer.communicate(data,timeout=14)
                elapsed=(time.perf_counter()-started)*1000
                self.assertEqual(writer.returncode,0,err)
                self.assertEqual(json.loads(out)['status'],'ack')
                self.assertGreaterEqual(elapsed,200)
                self.assertEqual(len(self.rows()),1)
                print('FICTIONAL SQLITE CONTENTION elapsed_ms=%.3f'%elapsed,
                      flush=True)
            finally:
                if writer.poll() is None:writer.kill();writer.communicate(timeout=4)
        finally:
            if holder.poll() is None:
                try:holder.stdin.write('\n');holder.stdin.flush()
                except (BrokenPipeError,OSError):pass
                try:holder.communicate(timeout=4)
                except ValueError:holder.wait(timeout=4)
            if holder.poll() is None:holder.kill();holder.wait(timeout=4)

    def test_credential_revocation_and_signer_revocation_fail_closed(self):
        code,denied,err=self.run_worker('revoke_credential')
        self.assertEqual((code,denied['status']),(0,'denied'))
        self.assertEqual(self.rows(),[])
        code,reply,err=self.run_worker('revoke_signer')
        self.assertEqual((code,reply['status']),(0,'revoked'))
        code,denied,err=self.run_worker()
        self.assertEqual((code,denied['status']),(0,'denied'))
        self.assertEqual(self.rows(),[])

    def test_stale_or_wrong_predecessor_fails_closed_across_restart(self):
        code,first,err=self.run_worker()
        self.assertEqual((code,first['status']),(0,'ack'),err)
        for seq,digest in ((0,GENESIS),(1,'f'*64),(2,'f'*64)):
            with self.subTest(seq=seq):
                code,reply,err=self.run_worker(
                    pin_seq=seq,pin_digest=digest,
                    reservation='e'*64,nonce='f'*64,
                    event_digest='e'*64)
                self.assertEqual((code,reply['status']),(0,'denied'))
        self.assertEqual(len(self.rows()),1)

    def test_subprocess_admission_latency_fictional(self):
        # One per completely new DB: no reused predecessor or valid writes.
        samples=[]
        for n in range(8):
            self.path=Path(self.temp.name)/('measure-%d.sqlite3'%n)
            start=time.perf_counter()
            code,reply,err=self.run_worker()
            samples.append((time.perf_counter()-start)*1000)
            self.assertEqual((code,reply['status']),(0,'ack'),err)
        ordered=sorted(samples)
        print('FICTIONAL CUSTODY ADMISSION ms n=8 p50=%.3f '
              'p95-nearest=%.3f max=%.3f'%
              ((ordered[3]+ordered[4])/2,ordered[-1],ordered[-1]),flush=True)


if __name__=='__main__':
    unittest.main()
