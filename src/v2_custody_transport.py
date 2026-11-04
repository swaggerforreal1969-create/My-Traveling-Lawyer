"""Provider-neutral v2 signed nonce contract: no builtin network or signer.

A caller injects an authenticated exchange and a separately configured trusted
asymmetric verifier. A boolean transport_authenticated flag is a CONTRACT
ASSERTION, not demonstrated external identity or independent custody.
No retries, pin advancement, fence clearance, deployment, or client data.
"""
import json
from dataclasses import dataclass

from .independent_checkpoint_boundary import PinnedCheckpoint, _digest, _hex
from .nonce_bound_custody import SCHEMA, FIELDS, EXACT
from .provider_neutral_custody_client import AuthenticatedCustodyTransport
from .secure_engine import Denied


@dataclass(frozen=True)
class V2TransportObservation:
    status: str
    sequence: int
    latest_sequence: int
    nonce_authenticated: bool = True
    independently_custodied: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


class NonceBoundCustodyClientV2:
    """Explicit one-shot v2 admission and independent read-only historical view."""

    def __init__(self, *, transport, predecessor, verify_signature):
        if (not isinstance(transport, AuthenticatedCustodyTransport)
                or not isinstance(predecessor, PinnedCheckpoint)
                or type(predecessor.sequence) is not int
                or predecessor.sequence < 0
                or not _hex(predecessor.digest)
                or not callable(verify_signature)):
            raise Denied('V2 custody transport or trusted predecessor unavailable')
        self.transport=transport
        self.predecessor=predecessor
        self.verify_signature=verify_signature

    @staticmethod
    def _identity(nonce, reservation, event_digest):
        if not all(_hex(x) for x in (nonce,reservation,event_digest)):
            raise Denied('Exact v2 operation identity required')

    def admit_once(self, *, credential, nonce, reservation, event_digest,
                   explicit_authorization):
        if explicit_authorization is not True:
            raise Denied('Human authorization required for v2 admission')
        self._identity(nonce,reservation,event_digest)
        # Deliberately no retry. Acknowledgment is NOT signed finality.
        reply=self.transport.exchange('v2_admit',{
            'credential':credential,'schema':SCHEMA,'nonce':nonce,
            'reservation':reservation,'event_digest':event_digest,
            'expected':{'sequence':self.predecessor.sequence,
                        'digest':self.predecessor.digest,
                        'signer_id':self.predecessor.signer_id}})
        if (set(reply)!={'sequence','head_digest'}
                or type(reply['sequence']) is not int
                or reply['sequence']!=self.predecessor.sequence+1
                or not _hex(reply['head_digest'])):
            raise Denied('Ambiguous unsigned v2 custody acknowledgment')
        return reply

    def reconcile_read_only(self, *, credential, nonce, reservation,
                            event_digest, retained_latest, max_events=16):
        self._identity(nonce,reservation,event_digest)
        root=self.predecessor
        tip=retained_latest
        if (not isinstance(tip,PinnedCheckpoint)
                or type(tip.sequence) is not int
                or tip.signer_id!=root.signer_id
                or not _hex(tip.digest)
                or type(max_events) is not int
                or not 1<=max_events<=16
                or not root.sequence<tip.sequence
                or tip.sequence-root.sequence>max_events):
            raise Denied('Externally held v2 finality pins invalid')

        def read_tip():
            reply=self.transport.exchange('v2_read_latest',
                                           {'credential':credential,'schema':SCHEMA})
            if (set(reply)!={'sequence','head_digest'}
                    or type(reply['sequence']) is not int
                    or not _hex(reply['head_digest'])):
                raise Denied('Malformed v2 readback latest')
            return reply

        before=read_tip()
        if (before['sequence'],before['head_digest'])!=(tip.sequence,tip.digest):
            raise Denied('V2 current tip differs from independently held pin')
        prior=root.digest
        matches=[]
        for seq in range(root.sequence+1,tip.sequence+1):
            head=self.transport.exchange('v2_read_head_at',{
                'credential':credential,'schema':SCHEMA,'sequence':seq})
            if (set(head)!=EXACT or type(head.get('sequence')) is not int
                    or head['sequence']!=seq or head['schema']!=SCHEMA
                    or head['previous']!=prior
                    or head['signer_id']!=root.signer_id
                    or not all(_hex(head.get(k)) for k in
                               ('nonce_digest','reservation_digest','event_digest'))
                    or not isinstance(head['signature'],str)
                    or not 1<=len(head['signature'])<=512):
                raise Denied('Signed v2 head malformed or forked')
            normalized={k:head[k] for k in FIELDS}
            payload=json.dumps(normalized,sort_keys=True,separators=(',',':'),
                               ensure_ascii=True).encode('ascii')
            try:
                valid=self.verify_signature(root.signer_id,payload,
                                            head['signature'])
            except Exception as exc:
                raise Denied('Trusted v2 signature verifier unavailable') from exc
            if valid is not True:
                raise Denied('Untrusted v2 signed head')
            prior=_digest(normalized)
            if (head['nonce_digest']==_digest({'nonce':nonce})
                    and head['reservation_digest']==_digest({'reservation':reservation})
                    and head['event_digest']==event_digest):
                matches.append(seq)
        if prior!=tip.digest or read_tip()!=before or len(matches)!=1:
            raise Denied('V2 final history changed or exact signed nonce absent')
        return V2TransportObservation('signed_exact_nonce_observed',
                                      matches[0],tip.sequence)
