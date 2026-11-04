"""Offline v2 Ed25519 public-key trust boundary, with no signing capability.

Trust roots, signer authorization and evaluation time are supplied externally.
This verifies signatures only: it does NOT prove independent key custody,
authenticated transport, external monotonic retention, or production approval.
"""
import hashlib
import re
from dataclasses import dataclass

from .secure_engine import Denied


@dataclass(frozen=True)
class PinnedEd25519Trust:
    signer_id: str
    public_key_raw: bytes
    public_key_sha256: str
    valid_from: int
    valid_until: int
    revoked: bool = False

    def __post_init__(self):
        if (type(self.signer_id) is not str
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',
                                    self.signer_id)
                or type(self.public_key_raw) is not bytes
                or len(self.public_key_raw)!=32
                or type(self.public_key_sha256) is not str
                or self.public_key_sha256!=hashlib.sha256(
                    self.public_key_raw).hexdigest()
                or type(self.valid_from) is not int
                or type(self.valid_until) is not int
                or not 0 <= self.valid_from < self.valid_until
                or type(self.revoked) is not bool):
            raise Denied('Untrusted or malformed Ed25519 public-key pin')


class PinnedEd25519Verifier:
    """Strict signature verifier compatible with injected v2 receipt client."""

    def __init__(self, *, trust, evaluated_at):
        if (type(trust) is not PinnedEd25519Trust
                or type(evaluated_at) is not int
                or not trust.valid_from<=evaluated_at<trust.valid_until
                or trust.revoked):
            raise Denied('Signing identity revoked, expired or not yet valid')
        self.trust=trust
        # No hidden clock access or implicit trust advancement.
        self.evaluated_at=evaluated_at

    def __call__(self, signer_id, payload, signature):
        if (type(signer_id) is not str
                or signer_id!=self.trust.signer_id
                or type(payload) is not bytes or not payload
                or type(signature) is not str
                or not re.fullmatch(r'[0-9a-f]{128}',signature)
                or self.trust.revoked
                or not self.trust.valid_from<=self.evaluated_at<self.trust.valid_until):
            return False
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PublicKey)
            from cryptography.exceptions import InvalidSignature
            public=Ed25519PublicKey.from_public_bytes(self.trust.public_key_raw)
            public.verify(bytes.fromhex(signature),payload)
            return True
        except (ValueError,InvalidSignature,TypeError):
            return False
