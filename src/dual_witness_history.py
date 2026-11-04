"""Two separately pinned, independently signed read-only history observations.

This is an offline provider-neutral verification contract. Distinct Python
objects or signing IDs do NOT prove administrative independence. The caller
must establish that separately outside this module before any release claim.
No writes, provider provisioning, trust-on-first-use, fence clearance or replay.
"""
from dataclasses import dataclass

from .independent_checkpoint_boundary import CheckpointReadbackBoundary, _hex
from .secure_engine import Denied


@dataclass(frozen=True)
class DualWitnessObservation:
    status: str
    sequence: int
    first_head_digest: str
    second_head_digest: str
    independently_custodied: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


class DualWitnessHistory:
    """Require two distinct pinned signer identities and independent readers.

    Readbacks must each verify a *single exact event/reservation* against their
    OWN independently supplied predecessor pin and signature verifier.
    The head digests may differ because the two signers attest separately.
    Both must agree on exact sequence, which is not enough to establish a
    globally monotonic history without externally managed forward pins.
    """

    def __init__(self, *, first, second):
        if (not isinstance(first, CheckpointReadbackBoundary)
                or not isinstance(second, CheckpointReadbackBoundary)
                or first is second or first.provider is second.provider
                or first.pinned.signer_id == second.pinned.signer_id
                or first.pinned.sequence != second.pinned.sequence
                or first.pinned.sequence < 0):
            raise Denied('Two distinct pinned witnesses required')
        self.first, self.second = first, second

    def verify(self, *, reservation, event_digest):
        if not _hex(reservation) or not _hex(event_digest):
            raise Denied('Invalid dual-witness operation identity')
        # Each verifier checks its own exact predecessor/signature/event.
        # A lost, stale, forked or mismatched witness is failure for the
        # entire observation. Never downgrade to one-witness acceptance.
        left = self.first.verify(
            reservation=reservation, event_digest=event_digest)
        right = self.second.verify(
            reservation=reservation, event_digest=event_digest)
        if (left.sequence != right.sequence
                or left.reservation_digest != right.reservation_digest
                or left.signer_id == right.signer_id
                or left.sequence != self.first.pinned.sequence + 1):
            raise Denied('Witnesses disagree about finalized operation')
        return DualWitnessObservation(
            'two_pinned_signatures_match_exact_operation',
            left.sequence, left.head_digest, right.head_digest)
