"""Bounded historical signed custody reconciliation after lost acknowledgments.

Uses independently held genesis/predecessor AND latest checkpoint commitments.
Checks every signed intermediate event, plus a stable observed latest head.
No nonce attestation: v1 signed heads omit nonce. No trust advancement, retry,
fence clearance, external egress, or claims about independent custodians.
"""
import json
from dataclasses import dataclass
from .independent_checkpoint_boundary import PinnedCheckpoint, _digest, _hex
from .secure_engine import Denied

HEAD_FIELDS={'sequence','previous','event_digest','reservation_digest',
             'signer_id','signature'}
EVENT_FIELDS={'sequence','reservation_digest','event_digest','commit_state'}


@dataclass(frozen=True)
class HistoricalCustodyObservation:
    status: str
    operation_sequence: int
    latest_sequence: int
    inspected_events: int
    independently_custodied: bool = False
    nonce_authenticated: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


class HistoricalCustodyReadback:
    def __init__(self, *, provider, verify_signature, predecessor,
                 retained_latest, max_events=16):
        if (not isinstance(predecessor,PinnedCheckpoint)
                or not isinstance(retained_latest,PinnedCheckpoint)
                or predecessor.signer_id!=retained_latest.signer_id
                or type(predecessor.sequence) is not int
                or type(retained_latest.sequence) is not int
                or not 0<=predecessor.sequence<retained_latest.sequence
                or not _hex(predecessor.digest)
                or not _hex(retained_latest.digest)
                or type(max_events) is not int or not 1<=max_events<=16
                or retained_latest.sequence-predecessor.sequence>max_events
                or not callable(verify_signature)
                or provider is None or
                not all(callable(getattr(provider,m,None)) for m in
                        ('read_head_at','read_event','read_head'))):
            raise Denied('Historical custody trust pins or bounded provider absent')
        self.provider=provider
        self.verify_signature=verify_signature
        self.predecessor=predecessor
        self.retained_latest=retained_latest
        self.max_events=max_events

    def _signed_head(self,head,*,seq,previous):
        if (type(head) is not dict or set(head)!=HEAD_FIELDS
                or type(head.get('sequence')) is not int
                or head['sequence']!=seq
                or head['previous']!=previous
                or head['signer_id']!=self.predecessor.signer_id
                or not _hex(head['event_digest'])
                or not _hex(head['reservation_digest'])
                or not isinstance(head['signature'],str)
                or not 1<=len(head['signature'])<=512):
            raise Denied('Historical signed head malformed or forked')
        normalized={name:head[name] for name in HEAD_FIELDS if name!='signature'}
        message=json.dumps(normalized,sort_keys=True,separators=(',',':'),
                           ensure_ascii=True).encode('ascii')
        try:
            valid=self.verify_signature(
                self.predecessor.signer_id,message,head['signature'])
        except Exception as exc:
            raise Denied('Historical signature verifier unavailable') from exc
        if valid is not True:
            raise Denied('Historical checkpoint signature invalid')
        return _digest(normalized)

    def verify(self, *, reservation, event_digest):
        if not _hex(reservation) or not _hex(event_digest):
            raise Denied('Exact historical operation required')
        expected_reservation=_digest({'reservation':reservation})
        try:
            initial=self.provider.read_head()
            if type(initial) is not dict:
                raise Denied('Current checkpoint unavailable')
            latest_seq=initial.get('sequence')
            if type(latest_seq) is not int or latest_seq!=self.retained_latest.sequence:
                raise Denied('Current checkpoint does not match retained tip')
            prev=self.predecessor.digest
            matches=[]
            for seq in range(self.predecessor.sequence+1,
                             self.retained_latest.sequence+1):
                head=self.provider.read_head_at(seq)
                event=self.provider.read_event(seq)
                digest=self._signed_head(head,seq=seq,previous=prev)
                if (type(event) is not dict or set(event)!=EVENT_FIELDS
                        or type(event['sequence']) is not int
                        or event['sequence']!=seq
                        or event['commit_state']!='committed'
                        or event['reservation_digest']!=head['reservation_digest']
                        or event['event_digest']!=head['event_digest']):
                    raise Denied('Historical signed event and readback disagree')
                if (head['reservation_digest']==expected_reservation and
                        head['event_digest']==event_digest):
                    matches.append(seq)
                prev=digest
            if prev!=self.retained_latest.digest:
                raise Denied('Final history differs from independently retained tip')
            # Check live head against the trusted final historical head; the
            # provider cannot return an old head during this bounded operation.
            final=self.provider.read_head()
            if (final!=initial or final!=head):
                raise Denied('Current checkpoint changed during historical readback')
        except Denied:
            raise
        except Exception as exc:
            raise Denied('Historical custody readback unavailable') from exc
        if len(matches)!=1:
            raise Denied('Exact historical operation missing or ambiguous')
        return HistoricalCustodyObservation(
            'signed_historical_operation_observed',matches[0],
            self.retained_latest.sequence,
            self.retained_latest.sequence-self.predecessor.sequence)
