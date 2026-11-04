"""Fictional multi-generation signed custody acceptance across true subprocesses."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from src.authenticated_pin_source import AuthenticatedPinSource
from src.cross_observer_history import CrossObserverRound
from src.multi_generation_finality import (
    GenerationReadback, verify_authenticated_generations)
from src.read_only_pin_quorum import ReadOnlyPinQuorum
from src.secure_engine import Denied
from test_authenticated_pin_process import WORKER, ROOT
from test_authenticated_pin_source import FixtureSignedReader, KEY_A, KEY_B
from test_dual_witness_history import CrossObserverContinuityTests

FIELDS=('sequence','signer_a','signer_b','head_a','head_b')


class SignedHistoryGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        fixture=CrossObserverContinuityTests()
        _,genesis=fixture.make_observers()
        self.origin=fixture.check(genesis)
        self.steps=[]
        current=self.origin
        for i in range(3):
            reservation=('%064x'%(100+i))
            event=('%064x'%(200+i))
            _,observed=fixture.make_observers(
                sequence=current.sequence+1,prior=current,
                reservation=reservation,event=event)
            pa=FixtureSignedReader(current,'fixture-pin-source-A',KEY_A)
            pb=FixtureSignedReader(current,'fixture-pin-source-B',KEY_B)
            source_a=pa.source()
            source_b=pb.source()
            step=GenerationReadback(
                quorum=ReadOnlyPinQuorum(primary=source_a,secondary=source_b),
                observer_a=observed[0],observer_b=observed[1],
                reservation=reservation,event_digest=event,
                expected_pin=current)
            self.steps.append((step,pa,pb))
            # This is an offline fixture preparing the NEXT generation.
            # No application API writes or advances trusted pins.
            computed=fixture.check(observed,prior=current,
                                   reservation=reservation,event=event)
            current=computed
        self.expected_final=current

    def check(self,steps=None,origin=None):
        if steps is None:steps=[step for step,_,_ in self.steps]
        return verify_authenticated_generations(
            steps,held_origin=self.origin if origin is None else origin)

    def test_three_consecutive_signed_generations_only_observational(self):
        r=self.check()
        self.assertEqual(r.generation_count,3)
        self.assertEqual(r.sequence,self.origin.sequence+3)
        self.assertEqual((r.head_a,r.head_b),
                         (self.expected_final.head_a,self.expected_final.head_b))
        self.assertFalse(r.independently_custodied)
        self.assertFalse(r.permits_fence_clearance)
        self.assertFalse(r.permits_write_replay)

    def test_missing_skipped_or_swapped_generation_denied(self):
        steps=[x[0] for x in self.steps]
        with self.assertRaises(Denied):self.check([steps[0],steps[2]])
        with self.assertRaises(Denied):self.check([steps[1],steps[0],steps[2]])
        with self.assertRaises(Denied):
            self.check(origin=CrossObserverRound(
                self.origin.sequence-1,self.origin.signer_a,
                self.origin.signer_b,'0'*64,'1'*64))

    def test_duplicate_exact_reservation_denied(self):
        from dataclasses import replace
        steps=[x[0] for x in self.steps]
        repeated=replace(steps[1],reservation=steps[0].reservation)
        with self.assertRaises(Denied):
            self.check([steps[0],repeated,steps[2]])

    def test_forked_or_compromised_one_signer_denied(self):
        self.steps[1][2].reply['pin']['head_b']='0'*64
        with self.assertRaises(Denied):self.check()

    def test_independent_process_restarts_each_signed_generation(self):
        env=os.environ.copy()
        env['PYTHONPATH']=str(ROOT)+os.pathsep+str(ROOT/'tests')
        measurements=[]
        for i,(step,pa,pb) in enumerate(self.steps):
            folder=Path(self.tmp.name)
            path_a=folder/('generation-%d-A.json'%i)
            path_b=folder/('generation-%d-B.json'%i)
            path_a.write_text(json.dumps(pa.reply),encoding='utf-8')
            path_b.write_text(json.dumps(pb.reply),encoding='utf-8')
            before=path_a.read_bytes(),path_b.read_bytes()
            # Existing worker independently reconstructs the next generation
            # with its fixed c/d event identity. Generate fresh *matching*
            # signed fixture history to test each actual subprocess.
            from test_dual_witness_history import CrossObserverContinuityTests
            base=CrossObserverContinuityTests()
            _,matching=base.make_observers(
                sequence=step.expected_pin.sequence+1,
                prior=step.expected_pin,reservation='c'*64,event='d'*64)
            self.assertEqual(
                base.check(matching,prior=step.expected_pin,
                           reservation='c'*64,event='d'*64).sequence,
                step.expected_pin.sequence+1)
            args={'stage':'normal','a':str(path_a),'b':str(path_b),
                  'pin':{k:getattr(step.expected_pin,k) for k in FIELDS}}
            for _ in range(2):
                started=time.perf_counter()
                child=subprocess.run([sys.executable,'-c',WORKER],
                    input=json.dumps(args)+'\n',text=True,
                    capture_output=True,cwd=str(ROOT),env=env,timeout=12)
                measurements.append((time.perf_counter()-started)*1000)
                self.assertEqual(child.returncode,0,child.stderr)
                observed=json.loads(child.stdout)
                self.assertEqual(observed['status'],'verified')
                self.assertFalse(observed['clear'])
                self.assertFalse(observed['replay'])
            self.assertEqual(before,(path_a.read_bytes(),path_b.read_bytes()))
        vals=sorted(measurements)
        print('FICTIONAL THREE GENERATION RESTART ms n=6 '
              'p50=%.3f p95-nearest=%.3f max=%.3f'%(
                  (vals[2]+vals[3])/2,vals[-1],vals[-1]),flush=True)


if __name__=='__main__':
    unittest.main()
