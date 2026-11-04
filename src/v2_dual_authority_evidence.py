"""Dual independently PINNED signed-authority policy agreement (offline).

Two different out-of-band Ed25519 authority public keys MUST each sign the
SAME precise custody policy; an exact, externally retained policy generation
and digest anchors both. This proves neither organizational independence,
real trusted time, nor rollback-proof retention. No I/O, signing, trust update,
write admission, replay, network or release authority.
"""
from dataclasses import dataclass

from .secure_engine import Denied
from .v2_asymmetric_trust import PinnedEd25519Trust
from .v2_signed_authority_policy import (
    AuthorityPolicyPin, authorized_v2_verifier)


@dataclass(frozen=True)
class DualAuthorityObservation:
    policy_generation: int
    policy_digest: str
    custody_signer_id: str
    authorities_verified: int = 2
    independently_custodied: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


def verify_dual_authority_policy(*, first_envelope, second_envelope,
                                 first_authority, second_authority,
                                 held_policy, expected_signer, evaluated_at):
    """Require two separately pinned signers and identical signed policy.

    Public keys and the policy generation/digest are supplied by the caller
    from independently verified evidence. Distinct key bytes do not prove
    distinct administrators or providers.
    """
    if (type(first_authority) is not PinnedEd25519Trust
            or type(second_authority) is not PinnedEd25519Trust
            or first_authority.signer_id == second_authority.signer_id
            or first_authority.public_key_sha256 ==
               second_authority.public_key_sha256
            or type(held_policy) is not AuthorityPolicyPin
            or type(first_envelope) is not dict
            or type(second_envelope) is not dict
            or first_envelope.get('policy') != second_envelope.get('policy')):
        raise Denied('Distinct authorities and exact common policy required')
    a=authorized_v2_verifier(
        envelope=first_envelope,authority_trust=first_authority,
        expected_policy=held_policy,expected_signer=expected_signer,
        evaluated_at=evaluated_at)
    b=authorized_v2_verifier(
        envelope=second_envelope,authority_trust=second_authority,
        expected_policy=held_policy,expected_signer=expected_signer,
        evaluated_at=evaluated_at)
    if (a.trust.public_key_sha256 != b.trust.public_key_sha256
            or a.trust.signer_id != b.trust.signer_id):
        raise Denied('Inconsistent authenticated custody signer policy')
    return DualAuthorityObservation(
        held_policy.generation,held_policy.digest,expected_signer),a
