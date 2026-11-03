import unittest
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import tests.test_secure_http as fixtures

def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

class DeviceRevocationHTTP(unittest.TestCase):
    setUp=fixtures.APIIntegrationTests.setUp
    tearDown=fixtures.APIIntegrationTests.tearDown
    call=fixtures.APIIntegrationTests.call
    def test_revoke_cancels_challenge_via_api(self):
        private=Ed25519PrivateKey.generate()
        pub=b64(private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw))
        status,registration,_=self.call('POST','/api/device/register',self.ot,{'public_key':pub})
        self.assertEqual(201,status)
        key=registration['key_id']
        status,challenge,_=self.call('POST','/api/device/challenge',self.ot,{'key_id':key})
        self.assertEqual(200,status)
        self.assertEqual(403,self.call('POST','/api/device/revoke',self.bt,{'key_id':key})[0])
        self.assertEqual(200,self.call('POST','/api/device/revoke',self.ot,{'key_id':key})[0])
        signature=b64(private.sign(('mtl-device-stepup-v1\n'+challenge['challenge']).encode()))
        status,_,_=self.call('POST','/api/device/verify',self.ot,{'key_id':key,'challenge':challenge['challenge'],'signature':signature})
        self.assertEqual(403,status)
