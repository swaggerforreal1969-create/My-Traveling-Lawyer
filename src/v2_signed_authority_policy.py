"""V2 custody policy verified under an OUT-OF-BAND Ed25519 authority root.

The immutable authority public-key fingerprint AND expected policy generation
and digest must be independently supplied. Signed policy alone cannot prevent
rollback; local DB, signer assertions, untrusted clocks or TOFU do not qualify.
No private keys, network, automatic policy updates or release authorization.
"""
import hashlib
import json
import re
from dataclasses import dataclass

from .secure_engine import Denied
from .v2_asymmetric_trust import PinnedEd25519Trust, PinnedEd25519Verifier

SCHEMA='mtl.custody.ed25519-authority-policy.v1'
POLICY_FIELDS={'schema','generation','signer_id','public_key_hex',
               'valid_from','valid_until','revoked'}
ENVELOPE_FIELDS={'policy','signature'}


def _canonical(data):
    return json.dumps(data,sort_keys=True,separators=(',',':'),
                      ensure_ascii=True).encode('ascii')


@dataclass(frozen=True)
class AuthorityPolicyPin:
    generation: int
    digest: str

    def __post_init__(self):
        if (type(self.generation) is not int or self.generation<1
                or type(self.digest) is not str
                or not re.fullmatch('[0-9a-f]{64}',self.digest)):
            raise Denied('Independent policy generation and digest required')


def authorized_v2_verifier(*, envelope, authority_trust, expected_policy,
                           expected_signer, evaluated_at):
    """Verify an exact signed policy anchored to separately retained evidence.

    The authority public key is NEVER learned from the envelope.
    External source/time validity is an unproven operational dependency.
    """
    if (type(authority_trust) is not PinnedEd25519Trust
            or type(expected_policy) is not AuthorityPolicyPin
            or type(expected_signer) is not str
            or type(evaluated_at) is not int
            or type(envelope) is not dict or set(envelope)!=ENVELOPE_FIELDS):
        raise Denied('Independently pinned authority configuration required')
    policy=envelope['policy']
    signature=envelope['signature']
    if (type(policy) is not dict or set(policy)!=POLICY_FIELDS
            or policy['schema']!=SCHEMA
            or type(policy['generation']) is not int
            or policy['generation']!=expected_policy.generation
            or type(policy['signer_id']) is not str
            or policy['signer_id']!=expected_signer
            or type(policy['public_key_hex']) is not str
            or not re.fullmatch('[0-9a-f]{64}',policy['public_key_hex'])
            or type(policy['valid_from']) is not int
            or type(policy['valid_until']) is not int
            or not 0<=policy['valid_from']<policy['valid_until']
            or type(policy['revoked']) is not bool
            or type(signature) is not str
            or not re.fullmatch('[0-9a-f]{128}',signature)):
        raise Denied('Malformed or unauthorized signed custody policy')
    message=_canonical(policy)
    if hashlib.sha256(message).hexdigest()!=expected_policy.digest:
        raise Denied('Custody policy differs from independently retained pin')
    authority=PinnedEd25519Verifier(trust=authority_trust,
                                    evaluated_at=evaluated_at)
    if authority(authority_trust.signer_id,message,signature) is not True:
        raise Denied('Authority signature invalid')
    if policy['revoked'] or not policy['valid_from']<=evaluated_at<policy['valid_until']:
        raise Denied('Custody signer expired, revoked or not yet valid')
    pubkey=bytes.fromhex(policy['public_key_hex'])
    signer_trust=PinnedEd25519Trust(
        signer_id=policy['signer_id'],
        public_key_raw=pubkey,
        public_key_sha256=hashlib.sha256(pubkey).hexdigest(),
        valid_from=policy['valid_from'],valid_until=policy['valid_until'],
        revoked=policy['revoked'])
    return PinnedEd25519Verifier(trust=signer_trust,evaluated_at=evaluated_at)
