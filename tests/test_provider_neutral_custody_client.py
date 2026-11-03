"""Separate local process custody transport acceptance: FICTIONAL fixtures ONLY."""
import hashlib
import hmac
import multiprocessing
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from src.checkpoint_admission_prototype import LocalCheckpointAdmissionPrototype
from src.independent_checkpoint_boundary import PinnedCheckpoint
from src.provider_neutral_custody_client import (
    AuthenticatedCustodyTransport, CustodyClient)
from src.secure_engine import Denied

PIN=PinnedCheckpoint(0,'a'*64,'synthetic-witness')
KEY=b'synthetic-transport-signing-key-not-production'
RES='b'*64
NONCE='c'*64
EVENT='d'*64


def sign(signer,data):
    if signer != PIN.signer_id:raise ValueError('signer mismatch')
    return hmac.new(KEY,data,hashlib.sha256).hexdigest()


def verify(signer,data,signature):
    return (signer==PIN.signer_id and
            hmac.compare_digest(sign(signer,data),signature))


def serve(conn, path):
    """A separate TEST process, not an independent custody operator."""
    active=True
    provider=LocalCheckpointAdmissionPrototype(
        path,genesis=PIN,
        authenticate=lambda credential: active and credential=='synthetic-credential',
        sign=sign, signer_id=PIN.signer_id)
    try:
        while True:
            op,args=conn.recv()
            if op=='stop':break
            if op=='revoke':
                active=False
                provider.revoke_signer()
                conn.send(('ok',{}))
                continue
            try:
                if not active or args.get('credential')!='synthetic-credential':
                    raise Denied('Access denied')
                if op=='admit':
                    pin=args['expected']
                    reply=provider.admit(
                        credential=args['credential'],
                        reservation=args['reservation'],nonce=args['nonce'],
                        event_digest=args['event_digest'],
                        expected=PinnedCheckpoint(pin['sequence'],pin['digest'],
                                                  pin['signer_id']))
                elif op=='read_head':
                    reply=provider.read_head()
                elif op=='read_event':
                    reply=provider.read_event(args['sequence'])
                else:
                    raise Denied('Unsupported synthetic transport operation')
                conn.send(('ok',reply))
            except Exception as exc:
                conn.send(('denied',type(exc).__name__))
    except EOFError:
        pass
    finally:
        conn.close()


class SeparateProcessCustodyClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'synthetic-custody.sqlite3'
        ctx=multiprocessing.get_context('spawn')
        self.parent,child=ctx.Pipe()
        self.proc=ctx.Process(target=serve,args=(child,str(self.path)))
        self.proc.start()
        child.close()
        self.lock=threading.Lock()
        self.wire=AuthenticatedCustodyTransport(
            request=self.send,transport_authenticated=True)
        self.client=CustodyClient(
            transport=self.wire,pinned=PIN,verify_signature=verify)

    def tearDown(self):
        if self.proc.is_alive():
            try:self.send('stop',{})
            except Exception:pass
        self.proc.join(8)
        if self.proc.is_alive():
            self.proc.terminate();self.proc.join(4)
        self.parent.close()
        self.tmp.cleanup()

    def send(self,op,args):
        with self.lock:
            self.parent.send((op,args))
            if op=='stop':return {}
            if not self.parent.poll(8):
                raise TimeoutError('Synthetic provider acknowledgment lost')
            status,reply=self.parent.recv()
            if status!='ok':raise Denied('Provider refused request')
            return reply

    def admit(self,**kw):
        args={'credential':'synthetic-credential',
              'reservation':RES,'nonce':NONCE,
              'event_digest':EVENT,'explicit_authorization':True}
        args.update(kw)
        return self.client.admit_once(**args)

    def read(self,**kw):
        args={'credential':'synthetic-credential',
              'reservation':RES,'event_digest':EVENT}
        args.update(kw)
        return self.client.reconcile_read_only(**args)

    def test_cross_process_auth_admission_and_readback(self):
        ack=self.admit()
        observed=self.read(acknowledgment=ack)
        self.assertEqual(observed.sequence,1)
        self.assertFalse(observed.independently_custodied)

    def test_explicit_authorization_required(self):
        with self.assertRaises(Denied):
            self.admit(explicit_authorization=False)
        self.assertEqual(self.admit()['sequence'],1)

    def test_credential_denied_before_admission_and_readback(self):
        with self.assertRaises(Denied):
            self.admit(credential='forged')
        self.admit()
        with self.assertRaises(Denied):
            self.read(credential='forged')

    def test_lost_ack_no_replay_read_only_reconcile(self):
        original=self.wire._request
        def lost(op,args):
            result=original(op,args)
            if op=='admit':raise TimeoutError('lost postcommit ack')
            return result
        self.wire._request=lost
        with self.assertRaises(Denied):self.admit()
        self.assertEqual(self.read().sequence,1)
        # Do not retry uncertain admission; provider would reject duplicate.
        self.wire._request=original
        with self.assertRaises(Denied):self.admit()

    def test_concurrent_clients_one_predecessor(self):
        other=CustodyClient(transport=self.wire,pinned=PIN,
                           verify_signature=verify)
        out=[]
        barrier=threading.Barrier(2)
        def attempt(client,res,nonce):
            barrier.wait()
            try:out.append(('ok',client.admit_once(
                credential='synthetic-credential',reservation=res,
                nonce=nonce,event_digest=EVENT,explicit_authorization=True)))
            except Denied:out.append(('denied',None))
        a=threading.Thread(target=attempt,args=(self.client,RES,NONCE))
        b=threading.Thread(target=attempt,args=(other,'e'*64,'f'*64))
        a.start();b.start();a.join(10);b.join(10)
        self.assertEqual(sorted(x[0] for x in out),['denied','ok'])

    def test_revoked_signer_denies_readback_and_future_writes(self):
        self.admit()
        self.send('revoke',{})
        with self.assertRaises(Denied):self.read()
        with self.assertRaises(Denied):
            self.admit(reservation='e'*64,nonce='f'*64)

    def test_substituted_history_fails_pinned_readback(self):
        self.admit()
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE checkpoint_events SET event_digest=?',
                       ('f'*64,))
        with self.assertRaises(Denied):self.read()

    def test_fake_trust_root_and_forged_verifier_denied(self):
        self.admit()
        altered=CustodyClient(transport=self.wire,
            pinned=PinnedCheckpoint(0,'f'*64,PIN.signer_id),
            verify_signature=verify)
        with self.assertRaises(Denied):
            altered.reconcile_read_only(credential='synthetic-credential',
                                        reservation=RES,event_digest=EVENT)
        invalid=CustodyClient(transport=self.wire,pinned=PIN,
                              verify_signature=lambda *args:False)
        with self.assertRaises(Denied):
            invalid.reconcile_read_only(credential='synthetic-credential',
                                        reservation=RES,event_digest=EVENT)

    def test_missing_transport_authentication_fails_before_requests(self):
        with self.assertRaises(Denied):
            AuthenticatedCustodyTransport(
                request=self.send,transport_authenticated=False)

    def test_malformed_and_unsupported_wire_operation_denied(self):
        with self.assertRaises(Denied):
            self.wire.exchange('admin_reset',{})
        with self.assertRaises(Denied):
            self.wire.exchange('admit',[])  # no permissive payload coercion


if __name__=='__main__':
    unittest.main()
