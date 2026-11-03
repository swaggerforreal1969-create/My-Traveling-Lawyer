import unittest
from tests.test_device_challenge_v12 import ChallengeTests
from src.device_challenge import DeviceDenied
from src.secure_engine import Denied

class RevocationTests(unittest.TestCase):
    setUp=ChallengeTests.setUp
    tearDown=ChallengeTests.tearDown
    proof=ChallengeTests.proof
    def test_revoke_blocks_outstanding_proof(self):
        c=self.device.issue(self.token,self.key)
        self.assertEqual({'revoked':True},self.device.revoke(self.token,self.key))
        with self.assertRaises(DeviceDenied):
            self.device.verify(self.token,self.key,c['challenge'],self.proof(c['challenge']))
        with self.assertRaises(DeviceDenied):self.device.issue(self.token,self.key)
    def test_other_firm_cannot_revoke_key(self):
        with self.assertRaises(DeviceDenied):self.device.revoke(self.other_token,self.key)
        self.assertTrue(self.device.issue(self.token,self.key)['challenge'])
    def test_double_revoke_denied(self):
        self.device.revoke(self.token,self.key)
        with self.assertRaises(DeviceDenied):self.device.revoke(self.token,self.key)
    def test_revoked_token_cannot_revoke(self):
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):self.device.revoke(self.token,self.key)
