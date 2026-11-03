"""Offline verifier for an *externally administered* signed checkpoint.

This is only a read-only acceptance interface. It does not provision a service,
store signing keys, admit reservations, clear local fences or claim custody.
A caller MUST independently pin the predecessor head AND signing identity and
supply a real cryptographic signature verifier before accepting a provider.
Fixture signatures in tests are NOT an independent security acceptance.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from .secure_engine import Denied

HEX = re.compile(r"^[0-9a-f]{64}$")
IDENTITY = re.compile(r"^[a-zA-Z0-9_.:-]{1,80}$")


def _digest(payload):
    return sha256(json.dumps(payload, sort_keys=True,
                             separators=(",", ":"), ensure_ascii=True)
                  .encode("ascii")).hexdigest()


def _hex(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def _identity(value):
    return isinstance(value, str) and IDENTITY.fullmatch(value) is not None


@dataclass(frozen=True)
class PinnedCheckpoint:
    sequence: int
    digest: str
    signer_id: str


@dataclass(frozen=True)
class VerifiedReadback:
    """Verified *against caller-supplied trust*, not an official release gate."""
    sequence: int
    head_digest: str
    reservation_digest: str
    signer_id: str
    independently_custodied: bool = False


class CheckpointReadbackBoundary:
    """Verify one contiguous committed checkpoint with independent readback.

    provider.read_event(seq) and provider.read_head() are READ-ONLY operations;
    proposal is an untrusted write acknowledgment, never proof on its own.
    Signature verification is mandatory and supplied by the caller with an
    independently pinned public key/trust root. No built-in test key or signer.
    """

    def __init__(self, *, provider, verify_signature, pinned):
        if (provider is None or not callable(getattr(provider, "read_head", None))
                or not callable(getattr(provider, "read_event", None))
                or not callable(verify_signature)
                or not isinstance(pinned, PinnedCheckpoint)
                or type(pinned.sequence) is not int or pinned.sequence < 0
                or not _hex(pinned.digest) or not _identity(pinned.signer_id)):
            raise Denied("Independent checkpoint configuration incomplete")
        self.provider = provider
        self.verify_signature = verify_signature
        self.pinned = pinned

    def verify(self, *, reservation, event_digest, proposal=None):
        """Require contiguous, signed, pinned head AND exact readback event.

        Return an observation only. The local write fence is never cleared.
        Repeated/stale, multi-step gaps, signer rotation and ambiguous reads
        fail closed until separate authorized re-pinning/incident review.
        """
        if not _hex(reservation) or not _hex(event_digest):
            raise Denied("Invalid exact checkpoint reservation or event digest")
        try:
            head = self.provider.read_head()
            event = self.provider.read_event(self.pinned.sequence + 1)
        except Exception as exc:
            raise Denied("Independent readback unavailable") from exc
        if type(head) is not dict or type(event) is not dict:
            raise Denied("Invalid checkpoint readback")
        # Reject unexpected properties to prevent downgrade/policy confusion.
        if set(head) != {"sequence", "previous", "event_digest", "reservation_digest",
                         "signer_id", "signature"}:
            raise Denied("Unrecognized checkpoint head format")
        if set(event) != {"sequence", "reservation_digest", "event_digest",
                          "commit_state"}:
            raise Denied("Unrecognized checkpoint event format")
        seq = head["sequence"]
        if type(seq) is not int or seq != self.pinned.sequence + 1:
            raise Denied("Stale, skipped or rolled-back checkpoint sequence")
        if (head["previous"] != self.pinned.digest
                or head["signer_id"] != self.pinned.signer_id
                or not _hex(head["event_digest"])
                or not _hex(head["reservation_digest"])
                or not isinstance(head["signature"], str)
                or len(head["signature"]) > 512):
            raise Denied("Checkpoint trust pin or signer mismatch")
        normalized = {key: head[key] for key in (
            "sequence", "previous", "event_digest",
            "reservation_digest", "signer_id")}
        signed_payload = json.dumps(normalized, sort_keys=True,
                                    separators=(",", ":"), ensure_ascii=True).encode("ascii")
        try:
            valid = self.verify_signature(
                self.pinned.signer_id, signed_payload, head["signature"])
        except Exception as exc:
            raise Denied("Checkpoint signature rejected") from exc
        if valid is not True:
            raise Denied("Checkpoint signature rejected")
        if (type(event["sequence"]) is not int or event["sequence"] != seq
                or event["commit_state"] != "committed"
                or event["reservation_digest"] != head["reservation_digest"]
                or event["event_digest"] != head["event_digest"]):
            raise Denied("Committed checkpoint readback does not match signed head")
        expected_reservation = _digest({"reservation": reservation})
        if (head["reservation_digest"] != expected_reservation
                or head["event_digest"] != event_digest):
            raise Denied("Exact reservation/event binding mismatch")
        if proposal is not None:
            if (type(proposal) is not dict
                    or set(proposal) != {"sequence", "head_digest"}
                    or type(proposal["sequence"]) is not int
                    or proposal["sequence"] != seq
                    or proposal["head_digest"] != _digest(normalized)):
                raise Denied("Ambiguous or conflicting write acknowledgment")
        return VerifiedReadback(
            seq, _digest(normalized), head["reservation_digest"],
            self.pinned.signer_id)
