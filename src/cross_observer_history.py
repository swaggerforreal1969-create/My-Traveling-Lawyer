"""Read-only split-view detection across two observers and successive checkpoints.

The caller supplies separately obtained, immutable, independently retained
prior observations and trust roots. No writes, network, auto-trust, custody
assertions, local fence clearance, or automated trust-pin advancement.
"""
from dataclasses import dataclass

from .dual_witness_history import DualWitnessHistory
from .independent_checkpoint_boundary import _hex
from .secure_engine import Denied


@dataclass(frozen=True)
class CrossObserverRound:
    sequence: int
    signer_a: str
    signer_b: str
    head_a: str
    head_b: str
    independently_custodied: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


def verify_observers(observer_a, observer_b, *, reservation,
                     event_digest, previous=None):
    """Compare exact operation and signed heads from two separate observers.

    Every observer must independently verify two differently signed events.
    For each signer, both observers must see the SAME normalized signed head.
    Previous accepted heads are supplied explicitly, never learned on first
    use or silently advanced. A dishonest provider can still collude with
    another dishonest provider; operational independence is out of scope.
    """
    if (not isinstance(observer_a, DualWitnessHistory)
            or not isinstance(observer_b, DualWitnessHistory)
            or observer_a is observer_b
            or not _hex(reservation) or not _hex(event_digest)):
        raise Denied('Two valid cross-observer checkpoints required')
    paths=(observer_a.first,observer_a.second,
           observer_b.first,observer_b.second)
    if len({id(x.provider) for x in paths})!=4:
        raise Denied('Observers must use distinct readback instances')
    a1,a2,b1,b2=paths
    if (a1.pinned.signer_id!=b1.pinned.signer_id
            or a2.pinned.signer_id!=b2.pinned.signer_id
            or a1.pinned.signer_id==a2.pinned.signer_id
            or a1.pinned!=b1.pinned or a2.pinned!=b2.pinned
            or a1.pinned.sequence!=a2.pinned.sequence):
        raise Denied('Observer trust pins or signer identities disagree')
    if previous is not None:
        if (not isinstance(previous,CrossObserverRound)
                or type(previous.sequence) is not int
                or a1.pinned.sequence!=previous.sequence
                or a1.pinned.signer_id!=previous.signer_a
                or a2.pinned.signer_id!=previous.signer_b
                or a1.pinned.digest!=previous.head_a
                or a2.pinned.digest!=previous.head_b):
            raise Denied('Externally retained predecessor continuity failed')
    first=observer_a.verify(reservation=reservation,event_digest=event_digest)
    second=observer_b.verify(reservation=reservation,event_digest=event_digest)
    if (first.sequence!=second.sequence
            or first.sequence!=a1.pinned.sequence+1
            or first.first_head_digest!=second.first_head_digest
            or first.second_head_digest!=second.second_head_digest):
        raise Denied('Split-view signed checkpoint history detected')
    return CrossObserverRound(first.sequence,a1.pinned.signer_id,
                              a2.pinned.signer_id,first.first_head_digest,
                              first.second_head_digest)
