"""Offline read-only two-source predecessor pin consensus before signed history.

An injected reader is only a contract. Caller must independently establish
provider control, authenticated transport, and rollback-resistant retention.
No default storage/network, trust-on-first-use, writes, pin updates, or release
authority. Local fixture pins are explicitly NOT external custody.
"""
from dataclasses import dataclass

from .cross_observer_history import CrossObserverRound, verify_observers
from .independent_checkpoint_boundary import _hex, _identity
from .secure_engine import Denied


@dataclass(frozen=True)
class PinnedReadbackObservation:
    sequence: int
    head_a: str
    head_b: str
    independently_custodied: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


class _ConstantPinSource:
    """A typed already-held anchor, never fetched or trust-on-first-use."""
    def __init__(self, value):
        self.value=value
    def read_pin(self):
        return self.value


class ReadOnlyPinQuorum:
    """Compare separately retained predecessor pins before/after readback."""

    def __init__(self, *, primary, secondary):
        if (primary is None or secondary is None or primary is secondary
                or not callable(getattr(primary,'read_pin',None))
                or not callable(getattr(secondary,'read_pin',None))):
            raise Denied('Two distinct read-only predecessor sources required')
        # Sources that claim cryptographic authentication must be anchored to
        # DIFFERENT independently supplied signer identities, not merely two
        # reader objects using the same signer/key. Legacy unsigned fixture
        # readers remain supported only as experimental read-only inputs.
        one=getattr(primary,'signer_id',None)
        two=getattr(secondary,'signer_id',None)
        if (one is not None or two is not None) and (
                not _identity(one) or not _identity(two) or one==two):
            raise Denied('Distinct authenticated predecessor signers required')
        self.primary=primary
        self.secondary=secondary

    def verify_authenticated(self, observer_a, observer_b, *,
                             reservation, event_digest, expected_pin):
        """Strict opt-in read-only boundary: no anonymous or unpinned sources.

        Existing verify() is experimental and intentionally accepts offline
        unsigned fixture readers for compatibility. Callers demanding an
        authenticated custody CONTRACT must use this entrypoint. Real provider
        independence and rollback-proof retention still need external proof.
        """
        from .authenticated_pin_source import AuthenticatedPinSource
        if (type(self.primary) is not AuthenticatedPinSource
                or type(self.secondary) is not AuthenticatedPinSource
                or self.primary.signer_id == self.secondary.signer_id
                or type(expected_pin) is not CrossObserverRound):
            raise Denied('Authenticated pin sources and external anchor required')
        return self.verify(observer_a,observer_b,reservation=reservation,
                           event_digest=event_digest,expected_pin=expected_pin)

    @staticmethod
    def _read(source):
        try:
            value=source.read_pin()
        except Exception as exc:
            raise Denied('Independent predecessor read unavailable') from exc
        if (type(value) is not CrossObserverRound
                or type(value.sequence) is not int or value.sequence < 0
                or not _identity(value.signer_a) or not _identity(value.signer_b)
                or value.signer_a == value.signer_b
                or not _hex(value.head_a) or not _hex(value.head_b)
                or value.independently_custodied is not False
                or value.permits_write_replay is not False
                or value.permits_fence_clearance is not False):
            raise Denied('Malformed predecessor pin; no readback permitted')
        return value

    def verify(self, observer_a, observer_b, *, reservation, event_digest,
               expected_pin=None):
        """Optional externally held exact pin prevents coordinated reader rollback.

        The caller MUST independently authenticate/retain expected_pin. An
        attacker-controlled local copy does not provide rollback resistance.
        """
        if expected_pin is not None:
            if (type(expected_pin) is not CrossObserverRound
                    or self._read(_ConstantPinSource(expected_pin))!=expected_pin):
                raise Denied('Invalid externally held predecessor anchor')
        first=self._read(self.primary)
        second=self._read(self.secondary)
        if first != second:
            raise Denied('Predecessor sources disagree or are rolled back')
        if expected_pin is not None and first != expected_pin:
            raise Denied('Both pin readers diverge from externally held anchor')
        result=verify_observers(observer_a,observer_b,
                                reservation=reservation,
                                event_digest=event_digest,previous=first)
        # External readers may change during signed readback. Do not promote
        # a result if their head changed or they served divergent snapshots.
        after_primary=self._read(self.primary)
        after_secondary=self._read(self.secondary)
        if (after_primary != first or after_secondary != first
                or (expected_pin is not None and after_primary != expected_pin)):
            raise Denied('Predecessor changed during signed readback')
        return PinnedReadbackObservation(
            result.sequence,result.head_a,result.head_b)
