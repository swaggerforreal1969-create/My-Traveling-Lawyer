"""Genuine subprocess v2 signed-nonce crash atomicity; fictional keys only.

Local SQLite is never independent custody. Trust pins are explicitly passed
from caller. No implicit retries, network, external signer, or fence clearance.
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

ROOT=Path(__file__).resolve().parents[1]
WORKER=r"""
import hashlib,hmac,json,os,signal,sys
from src.nonce_bound_custody import OfflineNonceBoundCustody
from src.independent_checkpoint_boundary import PinnedCheckpoint
KEY=b'fictional-v2-crash-test-key-not-production'
SIGNER='fictional-v2-crash-signer'
args=json.loads(sys.stdin.readline())
root=PinnedCheckpoint(0,'a'*64,SIGNER)
def sign(actor,payload):
    if actor!=SIGNER:raise ValueError('unexpected fictional signer')
    if args['stage']=='precommit_sigkill':
        os.kill(os.getpid(),signal.SIGKILL)
    return hmac.new(KEY,payload,hashlib.sha256).hexdigest()
def verify(actor,payload,sig):
    return actor==SIGNER and hmac.compare_digest(
        hmac.new(KEY,payload,hashlib.sha256).hexdigest(),sig)
provider=OfflineNonceBoundCustody(args['db'],genesis=root,
    authenticate=lambda credential:credential=='fictional-credential'
        and args['stage']!='revoked_credential',
    sign=sign,verify_signature=verify)
pin=PinnedCheckpoint(args['predecessor_seq'],args['predecessor_digest'],SIGNER)
try:
    if args['stage']=='revoke_signer':
        provider.revoke()
        print(json.dumps({'status':'revoked'}),flush=True)
    elif args['stage']=='read':
        latest=PinnedCheckpoint(args['latest_seq'],args['latest_digest'],SIGNER)
        found=provider.read_historical(
            nonce=args['nonce'],reservation=args['reservation'],
            event_digest=args['event'],predecessor=pin,
            retained_latest=latest)
        print(json.dumps({'status':'observed','sequence':found.sequence,
            'nonce_authenticated':found.nonce_authenticated,
            'independent':found.independently_custodied,
            'replay':found.permits_write_replay,
            'clear':found.permits_fence_clearance}),flush=True)
    else:
        ack=provider.admit_once(credential='fictional-credential',
            nonce=args['nonce'],reservation=args['reservation'],
            event_digest=args['event'],expected=pin,
            explicitly_authorized=True)
        if args['stage']=='postcommit_sigkill':
            os.kill(os.getpid(),signal.SIGKILL)
        print(json.dumps({'status':'ack','sequence':ack['sequence'],
            'digest':ack['head_digest']}),flush=True)
except Exception as exc:
    print(json.dumps({'status':'denied','error':type(exc).__name__}),flush=True)
"""


class V2IndependentProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'v2-signed-custody.sqlite3'
        self.nonce='b'*64
        self.reservation='c'*64
        self.event='d'*64
        self.genesis='a'*64
        self.head=None

    def args(self,stage='admit',**kwargs):
        values=dict(stage=stage,db=str(self.path),predecessor_seq=0,
            predecessor_digest=self.genesis,latest_seq=1,
            latest_digest=self.head or 'f'*64,
            nonce=self.nonce,reservation=self.reservation,event=self.event)
        values.update(kwargs)
        return values

    def launch(self,stage='admit',**kwargs):
        values=self.args(stage,**kwargs)
        env=os.environ.copy()
        env['PYTHONPATH']=str(ROOT)
        child=subprocess.Popen([sys.executable,'-c',WORKER],
            cwd=str(ROOT),env=env,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        return child,values

    def execute(self,stage='admit',**kwargs):
        child,values=self.launch(stage,**kwargs)
        out,err=child.communicate(json.dumps(values)+'\n',timeout=12)
        return child.returncode,json.loads(out) if out.strip() else None,err

    def committed(self):
        with sqlite3.connect(self.path) as db:
            return db.execute('SELECT sequence,nonce_digest,head_digest '
                              'FROM custody_v2_events ORDER BY sequence').fetchall()

    @unittest.skipUnless(os.name=='posix','SIGKILL requires POSIX')
    def test_real_sigkill_precommit_rolls_back_signed_nonce(self):
        code,reply,err=self.execute('precommit_sigkill')
        self.assertEqual(code,-signal.SIGKILL,(reply,err))
        self.assertEqual(self.committed(),[])
        code,ack,err=self.execute()
        self.assertEqual((code,ack['status'],ack['sequence']),(0,'ack',1))
        self.head=ack['digest']
        self.assertEqual(len(self.committed()),1)

    @unittest.skipUnless(os.name=='posix','SIGKILL requires POSIX')
    def test_postcommit_sigkill_read_only_exact_nonce_after_restart(self):
        code,reply,err=self.execute('postcommit_sigkill')
        self.assertEqual(code,-signal.SIGKILL,(reply,err))
        before=self.committed()
        self.assertEqual(len(before),1)
        self.head=before[0][2]
        code,observed,err=self.execute('read')
        self.assertEqual((code,observed['status'],observed['sequence']),
                         (0,'observed',1),err)
        self.assertTrue(observed['nonce_authenticated'])
        self.assertFalse(observed['independent'])
        self.assertFalse(observed['replay'])
        self.assertFalse(observed['clear'])
        self.assertEqual(self.committed(),before)
        # This is a deliberately denied attack, not an automatic retry.
        code,denied,err=self.execute()
        self.assertEqual((code,denied['status']),(0,'denied'))
        self.assertEqual(self.committed(),before)

    def test_two_real_competing_processes_one_cas_winner(self):
        first,a=self.launch(nonce='b'*64,reservation='c'*64)
        second,b=self.launch(nonce='e'*64,reservation='f'*64)
        try:
            for process,values in ((first,a),(second,b)):
                process.stdin.write(json.dumps(values)+'\n')
                process.stdin.flush()
            results=[]
            for process in (first,second):
                out,err=process.communicate(timeout=12)
                self.assertEqual(process.returncode,0,err)
                results.append(json.loads(out)['status'])
            self.assertEqual(sorted(results),['ack','denied'])
            self.assertEqual(len(self.committed()),1)
        finally:
            for process in (first,second):
                if process.poll() is None:
                    process.kill();process.communicate(timeout=4)

    def test_stale_signer_replacement_or_wrong_nonce_is_denied(self):
        code,ack,err=self.execute()
        self.assertEqual((code,ack['status']),(0,'ack'),err)
        self.head=ack['digest']
        code,denied,err=self.execute('read',nonce='f'*64)
        self.assertEqual((code,denied['status']),(0,'denied'))
        code,denied,err=self.execute('read',latest_digest='0'*64)
        self.assertEqual((code,denied['status']),(0,'denied'))

    def test_revoked_credentials_and_persistent_signer_revocation(self):
        code,denied,err=self.execute('revoked_credential')
        self.assertEqual((code,denied['status']),(0,'denied'),err)
        code,reply,err=self.execute('revoke_signer')
        self.assertEqual((code,reply['status']),(0,'revoked'),err)
        code,denied,err=self.execute()
        self.assertEqual((code,denied['status']),(0,'denied'))

    def test_coordinated_local_rollback_against_held_signed_latest(self):
        code,ack,err=self.execute()
        self.assertEqual((code,ack['status']),(0,'ack'),err)
        self.head=ack['digest']
        with sqlite3.connect(self.path) as db:
            db.execute('DELETE FROM custody_v2_events')
        code,denied,err=self.execute('read')
        self.assertEqual((code,denied['status']),(0,'denied'),err)

    def test_crash_recovery_fictional_latency_p50_p95(self):
        samples=[]
        for i in range(8):
            self.path=Path(self.tmp.name)/('latency-%02d.sqlite3'%i)
            started=time.perf_counter()
            code,ack,err=self.execute()
            samples.append((time.perf_counter()-started)*1000)
            self.assertEqual((code,ack['status']),(0,'ack'),err)
        measurements=sorted(samples)
        print('FICTIONAL V2 PROCESS ADMISSION ms n=8 p50=%.3f '
              'p95-nearest=%.3f max=%.3f'%(
                  (measurements[3]+measurements[4])/2,
                  measurements[-1],measurements[-1]),flush=True)


if __name__=='__main__':
    unittest.main()
