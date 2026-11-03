import os,sys,tempfile,unittest
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.secure_engine import SecureCore,Denied
from src.audit_witness import generate_demo_keypair,sign_head,verify_core_against_pin,verify_signature

class SecurityV10(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'db.sqlite'
  self.core=SecureCore(self.path);f=self.core.provision_firm('Fake Firm');self.uid,self.token=self.core.provision_user(f,'Attorney')
 def tearDown(self):self.core.close();self.temp.cleanup()
 def test_idle_expiry_denied_without_browser(self):
  self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',((datetime.now(timezone.utc)-timedelta(seconds=301)).isoformat(),sha256(self.token.encode()).hexdigest()))
  with self.assertRaises(Denied):self.core.list_matters(self.token)
 def test_idle_boundary_recent(self):
  self.assertEqual([],self.core.list_matters(self.token))
 def test_future_clock_anomaly(self):
  self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',((datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),sha256(self.token.encode()).hexdigest()))
  with self.assertRaises(Denied):self.core.list_matters(self.token)
 def test_new_rotation_is_live(self):
  new=self.core.rotate_token(self.token)['token']
  with self.assertRaises(Denied):self.core.list_matters(self.token)
  self.assertEqual([],self.core.list_matters(new))
 def test_reopen_persists_expiry(self):
  self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),sha256(self.token.encode()).hexdigest()))
  self.core.close();self.core=SecureCore(self.path)
  with self.assertRaises(Denied):self.core.list_matters(self.token)
 def test_signed_head_and_append(self):
  private,public=generate_demo_keypair()
  self.core.create_matter(self.token,'Example')
  checkpoint=sign_head(self.core.audit_head(),private)
  self.assertTrue(verify_core_against_pin(self.core,checkpoint,public))
  self.core.create_matter(self.token,'Another')
  self.assertTrue(verify_core_against_pin(self.core,checkpoint,public))
 def test_rollback_rejected(self):
  private,public=generate_demo_keypair()
  old=self.path.read_bytes() if self.path.exists() else b''
  self.core.create_matter(self.token,'First')
  pin=sign_head(self.core.audit_head(),private)
  self.core.db.execute('DELETE FROM audit_chain WHERE seq=(SELECT max(seq) FROM audit_chain)')
  self.assertFalse(verify_core_against_pin(self.core,pin,public))
 def test_forged_signature_rejected(self):
  private,public=generate_demo_keypair(); pin=sign_head(self.core.audit_head(),private)
  pin['head']['seq']+=1
  self.assertFalse(verify_signature(pin,public))
 def test_fork_rejected(self):
  private,public=generate_demo_keypair(); self.core.create_matter(self.token,'M1')
  pin=sign_head(self.core.audit_head(),private)
  self.core.db.execute("UPDATE audit_chain SET target='evil' WHERE seq=1")
  self.assertFalse(verify_core_against_pin(self.core,pin,public))
 def test_wrong_signer_rejected(self):
  private,public=generate_demo_keypair();_,other=generate_demo_keypair()
  self.assertFalse(verify_core_against_pin(self.core,sign_head(self.core.audit_head(),private),other))

if __name__=='__main__':unittest.main()
