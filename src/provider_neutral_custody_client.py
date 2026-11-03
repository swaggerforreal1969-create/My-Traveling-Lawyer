"""Provider-neutral custody wire contract; external egress is NEVER configured.

The caller supplies an authenticated transport implementation, an independently
retained predecessor pin and a verified signature callback. No built-in network,
trust-on-first-use, key store, persistence, signing secret or auto-write replay.

A transport adapter saying it is authenticated is an assertion to be evaluated
independently in real-service acceptance, NOT a proof of operational custody.
"""
from dataclasses import dataclass

from .secure_engine import Denied
from .independent_checkpoint_boundary import (
    CheckpointReadbackBoundary, PinnedCheckpoint, _hex, _digest)


class AuthenticatedCustodyTransport:
    """Strict injectable request interface. No default network implementation."""
    def __init__(self, *, request, transport_authenticated):
        if not callable(request) or transport_authenticated is not True:
            raise Denied('Authenticated custody transport is not configured')
        self._request = request

    def exchange(self, operation, body):
        if operation not in ('admit', 'read_head', 'read_event'):
            raise Denied('Unsupported custody operation')
        if type(body) is not dict:
            raise Denied('Invalid custody request')
        try:
            reply = self._request(operation, dict(body))
        except Exception as exc:
            raise Denied('Custody transport unavailable or ambiguous') from exc
        if type(reply) is not dict:
            raise Denied('Invalid custody transport response')
        return reply


class _Reader:
    def __init__(self, wire, credential):
        self.wire, self.credential = wire, credential

    def read_head(self):
        return self.wire.exchange('read_head', {'credential':self.credential})

    def read_event(self, seq):
        return self.wire.exchange('read_event',
                                  {'credential':self.credential, 'sequence':seq})


@dataclass(frozen=True)
class CustodyObservation:
    status: str
    sequence: int
    head_digest: str
    independently_custodied: bool = False


class CustodyClient:
    """Explicit human-authorized admission, separate readback; NO automatic retry.

    Calling admit_once never repeats itself on transport errors. The result is
    an untrusted acknowledgment, not evidence. A distinct caller-invoked
    readback step checks signed committed history against a pinned root.
    Neither method can clear the GUI's local SQLite write fence.
    """

    def __init__(self, *, transport, pinned, verify_signature):
        if (not isinstance(transport,AuthenticatedCustodyTransport)
                or not isinstance(pinned,PinnedCheckpoint)
                or not callable(verify_signature)):
            raise Denied('Custody client configuration incomplete')
        self.transport=transport
        self.pinned=pinned
        self.verify_signature=verify_signature

    @staticmethod
    def _check_intent(reservation, nonce, event_digest):
        if not all(_hex(v) for v in (reservation,nonce,event_digest)):
            raise Denied('Invalid custody admission intent')

    def admit_once(self, *, credential, reservation, nonce, event_digest,
                   explicit_authorization):
        if explicit_authorization is not True:
            raise Denied('Explicit write authorization required')
        self._check_intent(reservation,nonce,event_digest)
        reply=self.transport.exchange('admit',{
            'credential':credential,
            'reservation':reservation,'nonce':nonce,'event_digest':event_digest,
            'expected':{'sequence':self.pinned.sequence,
                        'digest':self.pinned.digest,
                        'signer_id':self.pinned.signer_id}})
        if (set(reply)!={'sequence','head_digest'}
                or type(reply['sequence']) is not int
                or reply['sequence']!=self.pinned.sequence+1
                or not _hex(reply['head_digest'])):
            raise Denied('Ambiguous custody admission acknowledgment')
        # Intentionally untrusted; requires separate authorized readback.
        return reply

    def reconcile_read_only(self, *, credential, reservation, event_digest,
                            acknowledgment=None):
        if not _hex(reservation) or not _hex(event_digest):
            raise Denied('Invalid custody reconciliation identity')
        reader=_Reader(self.transport,credential)
        verifier=CheckpointReadbackBoundary(
            provider=reader, pinned=self.pinned,
            verify_signature=self.verify_signature)
        result=verifier.verify(
            reservation=reservation,event_digest=event_digest,
            proposal=acknowledgment)
        return CustodyObservation('local_or_provider_readback_observed',
                                  result.sequence,result.head_digest)
