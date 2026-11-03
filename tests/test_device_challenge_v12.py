import base64
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from src.secure_engine import SecureCore
from src.device_challenge import DeviceChallenge,DeviceDenied

def b64(x):return base64.urlsafe_b64encode(x).rstrip(b'=').decode()
class ChallengeTests(unittest.TestCase):
 def setUp(self):
  self.core=SecureCore();self.f=self.core.provision_firm('Fictional Firm');self.uid,self.token=self.core.provision_user(self.f,'Attorney');self.other_f=self.core.provision_firm('Other Firm');self.other,self.other_token=self.core.provision_user(self.other_f,'Other Attorney');self.device=DeviceChallenge(self.core);self.private=Ed25519PrivateKey.generate();self.public=b64(self.private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw));self.key=self.device.register(self.token,self.public)
 def tearDown(self):self.core.close()
 def proof(self,nonce):return b64(self.private.sign((self.device.PURPOSE+'\n'+nonce).encode()))
 def test_valid_proof(self):
  c=self.device.issue(self.token,self.key);self.assertTrue(self.device.verify(self.token,self.key,c['challenge'],self.proof(c['challenge']))['verified'])
 def test_replay_denied(self):
  c=self.device.issue(self.token,self.key);self.device.verify(self.token,self.key,c['challenge'],self.proof(c['challenge']))
  with self.assertRaises(DeviceDenied):self.device.verify(self.token,self.key,c['challenge'],self.proof(c['challenge']))
 def test_forged_signature_denied(self):
  c=self.device.issue(self.token,self.key)
  with self.assertRaises(DeviceDenied):self.device.verify(self.token,self.key,c['challenge'],b64(Ed25519PrivateKey.generate().sign(b'wrong')))
 def test_cross_firm_denied(self):
  with self.assertRaises(DeviceDenied):self.device.issue(self.other_token,self.key)
 def test_cross_firm_verify_denied(self):
  c=self.device.issue(self.token,self.key)
  with self.assertRaises(DeviceDenied):self.device.verify(self.other_token,self.key,c['challenge'],self.proof(c['challenge']))
 def test_expiry_denied(self):
  c=self.device.issue(self.token,self.key);self.core.db.execute('UPDATE device_challenges SET expires=0')
  with self.assertRaises(DeviceDenied):self.device.verify(self.token,self.key,c['challenge'],self.proof(c['challenge']))
 def test_mismatched_purpose_denied(self):
  c=self.device.issue(self.token,self.key)
  with self.assertRaises(DeviceDenied):self.device.verify(self.token,self.key,c['challenge'],b64(self.private.sign(c['challenge'].encode())))
 def test_revoked_token_denied(self):
  c=self.device.issue(self.token,self.key);self.core.revoke_token(self.token)
  from src.secure_engine import Denied
  with self.assertRaises(Denied):self.device.verify(self.token,self.key,c['challenge'],self.proof(c['challenge']))
 def test_concurrent_single_winner(self):
  c=self.device.issue(self.token,self.key);proof=self.proof(c['challenge'])
  def attempt(_):
   try:self.device.verify(self.token,self.key,c['challenge'],proof);return True
   except DeviceDenied:return False
  with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(attempt,range(6)))
  self.assertEqual(1,sum(results))
 def test_bad_public_key_denied(self):
  with self.assertRaises(DeviceDenied):self.device.register(self.token,'invalid')
 def test_persistent_challenge_and_replay(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'db.sqlite';a=SecureCore(path);f=a.provision_firm('demo');u,t=a.provision_user(f,'test');x=DeviceChallenge(a);k=x.register(t,self.public);c=x.issue(t,k);a.close()
   b=SecureCore(path);y=DeviceChallenge(b);self.assertTrue(y.verify(t,k,c['challenge'],self.proof(c['challenge']))['verified']);b.close()
   z=SecureCore(path);v=DeviceChallenge(z)
   with self.assertRaises(DeviceDenied):v.verify(t,k,c['challenge'],self.proof(c['challenge']))
   z.close()
if __name__=='__main__':unittest.main()
