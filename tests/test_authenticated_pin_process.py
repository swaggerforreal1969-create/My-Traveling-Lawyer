"""Independent subprocess authenticated pin acceptance. FICTIONAL KEYS ONLY.

No production credential, external custody, network, or write clearance.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

from src.cross_observer_history import CrossObserverRound
from src.secure_engine import Denied
from test_dual_witness_history import CrossObserverContinuityTests
from test_authenticated_pin_source import FixtureSignedReader, KEY_A, KEY_B

ROOT=Path(__file__).resolve().parents[1]
WORKER=r"""
import json, os, signal, sys
from src.authenticated_pin_source import AuthenticatedPinSource
from src.offline_signed_pin_fixture import OfflineSignedPinFixtureReader
from src.read_only_pin_quorum import ReadOnlyPinQuorum
from src.cross_observer_history import CrossObserverRound
from test_dual_witness_history import CrossObserverContinuityTests
from test_authenticated_pin_source import KEY_A, KEY_B
import hashlib,hmac
args=json.loads(sys.stdin.readline())
if args["stage"]=="before":
    os.kill(os.getpid(),signal.SIGKILL)
pin=CrossObserverRound(**args["pin"])
def make_signed_source(path,label,key):
    def verify(signer,payload,signature):
        return (signer==label and hmac.compare_digest(
            hmac.new(key,payload,hashlib.sha256).hexdigest(),signature))
    return AuthenticatedPinSource(
        reader=OfflineSignedPinFixtureReader(path),
        signer_id=label,verify_signature=verify)
a=make_signed_source(args["a"],"fixture-pin-source-A",KEY_A)
b=make_signed_source(args["b"],"fixture-pin-source-B",KEY_B)
fixture=CrossObserverContinuityTests()
_,observed=fixture.make_observers(sequence=pin.sequence+1,prior=pin,
                                 reservation='c'*64,event='d'*64)
try:
    result=ReadOnlyPinQuorum(primary=a,secondary=b).verify_authenticated(
        observed[0],observed[1],reservation='c'*64,
        event_digest='d'*64,expected_pin=pin)
    if args["stage"]=="after":
        os.kill(os.getpid(),signal.SIGKILL)
    print(json.dumps({"status":"verified","sequence":result.sequence,
        "custody":result.independently_custodied,
        "replay":result.permits_write_replay,
        "clear":result.permits_fence_clearance}),flush=True)
except Exception as exc:
    print(json.dumps({"status":"denied","kind":type(exc).__name__}),flush=True)
"""


class AuthenticatedPinSubprocessAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.a=Path(self.temp.name)/'fictional-source-A.json'
        self.b=Path(self.temp.name)/'fictional-source-B.json'
        fixture=CrossObserverContinuityTests()
        _,early=fixture.make_observers()
        self.pin=fixture.check(early)
        self.first=FixtureSignedReader(
            self.pin,'fixture-pin-source-A',KEY_A)
        self.second=FixtureSignedReader(
            self.pin,'fixture-pin-source-B',KEY_B)
        self.save()

    def save(self):
        self.a.write_text(json.dumps(self.first.reply),encoding='utf-8')
        self.b.write_text(json.dumps(self.second.reply),encoding='utf-8')

    def start(self,stage='normal'):
        env=os.environ.copy()
        env['PYTHONPATH']=str(ROOT)+os.pathsep+str(ROOT/'tests')
        args={'stage':stage,'a':str(self.a),'b':str(self.b),
              'pin':{k:getattr(self.pin,k) for k in
                     ('sequence','signer_a','signer_b','head_a','head_b')}}
        return subprocess.Popen([sys.executable,'-c',WORKER],
            cwd=str(ROOT),env=env,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True),args

    def run_worker(self,stage='normal'):
        process,args=self.start(stage)
        out,err=process.communicate(json.dumps(args)+'\n',timeout=12)
        return process.returncode,out,err

    def test_restart_twice_preserves_authenticated_read_only(self):
        original=self.a.read_bytes(),self.b.read_bytes()
        for _ in range(2):
            code,out,err=self.run_worker()
            self.assertEqual(code,0,err)
            result=json.loads(out)
            self.assertEqual(result['status'],'verified')
            self.assertEqual(result['sequence'],self.pin.sequence+1)
            self.assertFalse(result['custody'])
            self.assertFalse(result['replay'])
            self.assertFalse(result['clear'])
        self.assertEqual(original,(self.a.read_bytes(),self.b.read_bytes()))

    def test_two_concurrent_processes_observe_same_pinned_identity(self):
        first,args=self.start()
        second,other=self.start()
        try:
            out1,err1=first.communicate(json.dumps(args)+'\n',timeout=12)
            out2,err2=second.communicate(json.dumps(other)+'\n',timeout=12)
            self.assertEqual((first.returncode,second.returncode),(0,0),
                             (err1,err2))
            self.assertEqual(json.loads(out1)['status'],'verified')
            self.assertEqual(json.loads(out2)['status'],'verified')
        finally:
            for process in (first,second):
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=4)

    def test_tampered_detached_signature_rejected_after_restart(self):
        self.second.reply['signature']='0'*64
        self.save()
        code,out,err=self.run_worker()
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['status'],'denied')

    def test_coordinated_signed_rollback_rejected_against_held_pin(self):
        for witness in (self.first,self.second):
            witness.reply['pin']['sequence']-=1
            witness.sign()
        self.save()
        code,out,err=self.run_worker()
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['status'],'denied')

    def test_symlink_and_partial_signed_envelope_fail_closed(self):
        self.b.write_bytes(b'{"schema":')
        code,out,err=self.run_worker()
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['status'],'denied')
        self.b.unlink()
        self.b.symlink_to(self.a)
        code,out,err=self.run_worker()
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['status'],'denied')

    @unittest.skipUnless(os.name=='posix','Real SIGKILL requires POSIX')
    def test_sigkill_before_and_after_signed_observation_no_file_writes(self):
        before=self.a.read_bytes(),self.b.read_bytes()
        for stage in ('before','after'):
            with self.subTest(stage=stage):
                code,out,err=self.run_worker(stage)
                self.assertEqual(code,-signal.SIGKILL,(out,err))
        self.assertEqual(before,(self.a.read_bytes(),self.b.read_bytes()))

    def test_fictional_process_latency_p50_p95(self):
        samples=[]
        for _ in range(8):
            started=time.perf_counter()
            code,out,err=self.run_worker()
            samples.append((time.perf_counter()-started)*1000)
            self.assertEqual(code,0,err)
            self.assertEqual(json.loads(out)['status'],'verified')
        sorted_ms=sorted(samples)
        p50=(sorted_ms[3]+sorted_ms[4])/2
        p95=sorted_ms[-1]
        self.assertGreaterEqual(p95,p50)
        print('FICTIONAL SIGNED PIN SUBPROCESS ms n=8 p50=%.3f '
              'p95-nearest=%.3f max=%.3f'%(p50,p95,max(samples)),flush=True)


if __name__=='__main__':
    unittest.main()
