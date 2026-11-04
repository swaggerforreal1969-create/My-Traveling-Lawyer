"""Real subprocess and offline filesystem trust-pin fault acceptance.

FICTIONAL fixtures only. The 'expected' pin is passed from the parent, not a
genuinely independent custodian. Local file snapshots are rollbackable and
cannot authorize production custody or a write-fence clearance.
"""
from dataclasses import asdict
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
from src.offline_fixture_pin_reader import OfflineFixturePinReader
from test_dual_witness_history import CrossObserverContinuityTests

ROOT=Path(__file__).resolve().parents[1]
WORKER=r'''
import json,os,signal,sys
from src.offline_fixture_pin_reader import OfflineFixturePinReader
from src.cross_observer_history import CrossObserverRound
from src.read_only_pin_quorum import ReadOnlyPinQuorum
from test_dual_witness_history import CrossObserverContinuityTests
args=json.loads(sys.stdin.readline())
if args["stage"]=="before_read":
    os.kill(os.getpid(),signal.SIGKILL)
expected=CrossObserverRound(**args["expected"])
fixture=CrossObserverContinuityTests()
_,observers=fixture.make_observers(sequence=expected.sequence+1,
    prior=expected,reservation='c'*64,event='d'*64)
pin=ReadOnlyPinQuorum(
    primary=OfflineFixturePinReader(args["first"]),
    secondary=OfflineFixturePinReader(args["second"]))
try:
    result=pin.verify(observers[0],observers[1],reservation='c'*64,
                      event_digest='d'*64,expected_pin=expected)
    if args["stage"]=="after_read":
        os.kill(os.getpid(),signal.SIGKILL)
    print(json.dumps({"result":"verified","sequence":result.sequence,
                      "custody":result.independently_custodied,
                      "replay":result.permits_write_replay,
                      "clear":result.permits_fence_clearance}),flush=True)
except Exception as exc:
    print(json.dumps({"result":"denied","kind":type(exc).__name__}),flush=True)
'''


class IndependentProcessPinAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.first=Path(self.tmp.name)/'observer-A.pin.json'
        self.second=Path(self.tmp.name)/'observer-B.pin.json'
        fixture=CrossObserverContinuityTests()
        _,observers=fixture.make_observers()
        self.expected=fixture.check(observers)
        self.write(self.first,self.expected)
        self.write(self.second,self.expected)

    @staticmethod
    def write(path,round_):
        data={key:getattr(round_,key) for key in
              ('sequence','signer_a','signer_b','head_a','head_b')}
        path.write_text(json.dumps(data,sort_keys=True),encoding='utf-8')

    def run_worker(self,stage='normal'):
        env=os.environ.copy()
        env['PYTHONPATH']=str(ROOT)+os.pathsep+str(ROOT/'tests')
        args={'stage':stage,'first':str(self.first),'second':str(self.second),
              'expected':{key:getattr(self.expected,key) for key in
                ('sequence','signer_a','signer_b','head_a','head_b')}}
        p=subprocess.Popen([sys.executable,'-c',WORKER],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            cwd=str(ROOT),env=env,text=True)
        out,err=p.communicate(json.dumps(args)+'\n',timeout=12)
        return p.returncode,out,err

    def test_restart_two_clean_independent_processes_read_only(self):
        before=[p.read_bytes() for p in (self.first,self.second)]
        for _ in range(2):
            code,out,err=self.run_worker()
            self.assertEqual(code,0,err)
            value=json.loads(out)
            self.assertEqual((value['result'],value['sequence']),
                             ('verified',self.expected.sequence+1))
            self.assertFalse(value['custody'])
            self.assertFalse(value['replay'])
            self.assertFalse(value['clear'])
        self.assertEqual(before,[p.read_bytes() for p in (self.first,self.second)])

    def test_both_local_files_rolled_back_against_separate_expected(self):
        earlier=CrossObserverRound(self.expected.sequence-1,
            self.expected.signer_a,self.expected.signer_b,
            '0'*64,'1'*64)
        self.write(self.first,earlier)
        self.write(self.second,earlier)
        code,out,err=self.run_worker()
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['result'],'denied')

    def test_single_corrupt_file_and_split_view_denied(self):
        self.second.write_bytes(b'{"sequence":')
        code,out,err=self.run_worker()
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['result'],'denied')
        self.write(self.second,CrossObserverRound(self.expected.sequence,
            self.expected.signer_a,self.expected.signer_b,
            '2'*64,self.expected.head_b))
        code,out,err=self.run_worker()
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['result'],'denied')

    def test_symlink_pin_rejected(self):
        self.second.unlink()
        self.second.symlink_to(self.first)
        code,out,err=self.run_worker()
        self.assertEqual(code,0,err)
        self.assertEqual(json.loads(out)['result'],'denied')

    @unittest.skipUnless(os.name=='posix','SIGKILL requires POSIX')
    def test_real_sigkill_before_read_and_after_observation(self):
        before=[p.read_bytes() for p in (self.first,self.second)]
        for stage in ('before_read','after_read'):
            with self.subTest(stage=stage):
                code,out,err=self.run_worker(stage)
                self.assertEqual(code,-signal.SIGKILL,(out,err))
        self.assertEqual(before,[p.read_bytes() for p in (self.first,self.second)])

    def test_process_restart_latency_p50_p95_fictional(self):
        samples=[]
        for _ in range(8):
            begin=time.perf_counter()
            code,out,err=self.run_worker()
            samples.append((time.perf_counter()-begin)*1000)
            self.assertEqual(code,0,err)
            self.assertEqual(json.loads(out)['result'],'verified')
        ordered=sorted(samples)
        p50=(ordered[3]+ordered[4])/2
        p95=ordered[7]
        self.assertGreaterEqual(p95,p50)
        print('FICTIONAL PIN RESTART ms: n=8 p50=%.3f p95-nearest=%.3f max=%.3f'%
              (p50,p95,max(samples)),flush=True)


if __name__=='__main__':
    unittest.main()
