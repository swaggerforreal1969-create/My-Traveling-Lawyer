"""Fictional ephemeral authority + custody keys: trust-root adversarial acceptance."""
import hashlib
import json
import unittest
from dataclasses import replace

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from src.v2_asymmetric_trust import PinnedEd25519Trust
from src.v2_signed_authority_policy import (
    AuthorityPolicyPin, SCHEMA, authorized_v2_verifier)
from src.secure_engine import Denied

AUTH='fictional-external-authority'
SIGNER='fictional-custody-operator'


def rawkey(secret):
    return secret.public_key().public_bytes(
        serialization.Encoding.Raw,serialization.PublicFormat.Raw)


def canonical(policy):
    return json.dumps(policy,sort_keys=True,separators=(',',':'),
                      ensure_ascii=True).encode('ascii')


class SignedAuthorityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.authority=Ed25519PrivateKey.generate()
        self.signer=Ed25519PrivateKey.generate()
        key=rawkey(self.authority)
        self.root=PinnedEd25519Trust(
            AUTH,key,hashlib.sha256(key).hexdigest(),100,900)
        self.policy={'schema':SCHEMA,'generation':7,'signer_id':SIGNER,
                     'public_key_hex':rawkey(self.signer).hex(),
                     'valid_from':200,'valid_until':700,'revoked':False}
        self.pin=AuthorityPolicyPin(7,hashlib.sha256(
            canonical(self.policy)).hexdigest())
        self.envelope=self.sign_policy(self.policy)

    def sign_policy(self,policy):
        return {'policy':dict(policy),
                'signature':self.authority.sign(canonical(policy)).hex()}

    def verified(self,**override):
        values=dict(envelope=self.envelope,authority_trust=self.root,
                    expected_policy=self.pin,expected_signer=SIGNER,
                    evaluated_at=500)
        values.update(override)
        return authorized_v2_verifier(**values)

    def test_valid_authority_pin_produces_real_ed25519_verifier(self):
        verifier=self.verified()
        payload=b'exact fictional nonce-bound signed head'
        self.assertTrue(verifier(SIGNER,payload,self.signer.sign(payload).hex()))
        self.assertFalse(verifier(SIGNER,payload,'0'*128))

    def test_substituted_key_with_same_signer_is_rejected(self):
        alternate=Ed25519PrivateKey.generate()
        changed=dict(self.policy,public_key_hex=rawkey(alternate).hex())
        with self.assertRaises(Denied):
            self.verified(envelope=self.sign_policy(changed))

    def test_signed_old_policy_or_unauthorized_rotation_denied(self):
        changed=dict(self.policy,generation=6)
        with self.assertRaises(Denied):
            self.verified(envelope=self.sign_policy(changed))
        changed=dict(self.policy,signer_id='other-custodian')
        with self.assertRaises(Denied):
            self.verified(envelope=self.sign_policy(changed))

    def test_forged_dates_and_revocation_denied_even_if_signed(self):
        for changed in (dict(self.policy,valid_until=999),
                        dict(self.policy,revoked=True)):
            with self.subTest(changed=changed),self.assertRaises(Denied):
                self.verified(envelope=self.sign_policy(changed))
        with self.assertRaises(Denied):
            self.verified(evaluated_at=701)
        with self.assertRaises(Denied):
            self.verified(evaluated_at=199)

    def test_unpinned_new_authority_key_cannot_replace_root(self):
        fake=Ed25519PrivateKey.generate()
        envelope={'policy':dict(self.policy),
                  'signature':fake.sign(canonical(self.policy)).hex()}
        with self.assertRaises(Denied):
            self.verified(envelope=envelope)
        with self.assertRaises(Denied):
            self.verified(authority_trust=replace(self.root,revoked=True))

    def test_tampering_signature_or_schema_denied(self):
        with self.assertRaises(Denied):
            self.verified(envelope={'policy':dict(self.policy),
                                    'signature':'0'*128})
        changed=dict(self.policy,schema='legacy-v1')
        with self.assertRaises(Denied):
            self.verified(envelope=self.sign_policy(changed))
        with self.assertRaises(Denied):
            self.verified(envelope={'policy':dict(self.policy),
                'signature':self.envelope['signature'],'trust_on_first_use':True})

    def test_absent_external_pin_or_untrusted_metadata_rejected(self):
        with self.assertRaises(Denied):
            self.verified(expected_policy=None)
        with self.assertRaises(Denied):
            self.verified(expected_policy=AuthorityPolicyPin(8,self.pin.digest))
        with self.assertRaises(Denied):
            self.verified(evaluated_at=True)

    def test_modified_public_key_fingerprint_fails_at_configuration(self):
        with self.assertRaises(Denied):
            PinnedEd25519Trust(
                AUTH,self.root.public_key_raw,'f'*64,100,900)

    def test_transport_nonce_receipt_with_signed_policy_verifier(self):
        from test_v2_asymmetric_trust import FictionalAsymmetricCustodyTests
        from src.v2_custody_transport import NonceBoundCustodyClientV2
        from src.v2_asymmetric_trust import PinnedEd25519Verifier
        # The signed policy verifier itself is exercised using exact receipt
        # signatures; independent real-provider operations remain unaccepted.
        from src.nonce_bound_custody import FIELDS,SCHEMA as RECEIPT_SCHEMA
        head={'schema':RECEIPT_SCHEMA,'sequence':1,'previous':'a'*64,
              'nonce_digest':'b'*64,'reservation_digest':'c'*64,
              'event_digest':'d'*64,'signer_id':SIGNER}
        payload=canonical(head)
        self.assertTrue(self.verified()(SIGNER,payload,
                                        self.signer.sign(payload).hex()))
        altered=dict(head,nonce_digest='e'*64)
        self.assertFalse(self.verified()(SIGNER,canonical(altered),
                                         self.signer.sign(payload).hex()))


if __name__=='__main__':
    unittest.main()
