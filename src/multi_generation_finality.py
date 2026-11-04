"""Bounded, strictly observational authenticated multi-generation custody review.

All trusted predecessor pins and generations are caller supplied and must be
independently retained. This verifier never persists or advances trust state,
replays operations, clears fences, or claims actual independent custody.
"""
from dataclasses import dataclass

from .cross_observer_history import CrossObserverRound
from .independent_checkpoint_boundary import _hex
from .read_only_pin_quorum import ReadOnlyPinQuorum
from .secure_engine import Denied


@dataclass(frozen=True)
class GenerationReadback:
    quorum: ReadOnlyPinQuorum
    observer_a: object
    observer_b: object
    reservation: str
    event_digest: str
    expected_pin: CrossObserverRound


@dataclass(frozen=True)
class HistoryObservation:
    sequence: int
    head_a: str
    head_b: str
    generation_count: int
    independently_custodied: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


def verify_authenticated_generations(generations, *, held_origin):
    """Reject gaps/forks/replays across a complete bounded evidence sequence.

    The previous result becomes an *ephemeral comparison* only. This NEVER
    writes, returns a newly trusted pin, or updates any source/trust anchor.
    A separate human-approved, external persistence protocol is still needed.
    """
    if (type(held_origin) is not CrossObserverRound
            or type(generations) not in (tuple,list)
            or not 2 <= len(generations) <= 16):
        raise Denied('Bounded independently pinned history required')
    current=held_origin
    used=set()
    for step in generations:
        if (type(step) is not GenerationReadback
                or type(step.quorum) is not ReadOnlyPinQuorum
                or type(step.expected_pin) is not CrossObserverRound
                or step.expected_pin != current
                or not _hex(step.reservation) or not _hex(step.event_digest)):
            raise Denied('Missing or conflicting generation identity')
        # Reuse of the same reservation across history steps is a replay,
        # regardless of whether a provider manufactures fresh signed heads.
        if step.reservation in used:
            raise Denied('Repeated reservation in signed history')
        used.add(step.reservation)
        read=step.quorum.verify_authenticated(
            step.observer_a,step.observer_b,
            reservation=step.reservation,
            event_digest=step.event_digest,
            expected_pin=current)
        if (read.sequence != current.sequence+1
                or not _hex(read.head_a) or not _hex(read.head_b)):
            raise Denied('Nonmonotonic or malformed signed history')
        current=CrossObserverRound(
            read.sequence,current.signer_a,current.signer_b,
            read.head_a,read.head_b)
    return HistoryObservation(
        current.sequence,current.head_a,current.head_b,len(generations))
