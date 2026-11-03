"""Offline, fictional-only source intake adversarial acceptance."""
import tempfile
import unittest
from pathlib import Path
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.official_source_intake import OfficialSourceIntake

class OfficialSourceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'data.db'
  self.c=SecureCore(self.path)
  f=self.c.provision_firm('Invented Firm');self.uid,self.t=self.c.provision_user(f,'Imaginary Lawyer')
  self.vid,self.v=self.c.provision_user(f,'Reader');self.other=self.c.provision_firm('Other Firm')
  _,self.x=self.c.provision_user(self.other,'Other')
  self.m=self.c.create_matter(self.t,'Imaginary hearing')['id']
  self.c.grant(self.t,self.m,self.vid,'viewer',1)
  self.e=ResearchEvidence(self.c).add(self.t,self.m,'Invented case','https://example.org/example','Fictional extract')['id']
  self.s=OfficialSourceIntake(self.c,['opinions.example.gov'])
 def tearDown(self):
  self.c.close();self.tmp.cleanup()
 def capture(self, **kw):
  args={'token':self.t,'matter_id':self.m,'evidence_id':self.e,
        'url':'https://opinions.example.gov/cases/fictional','document':b'FICTIONAL PDF BYTES',
        'note':'Reviewed supplied imaginary document; no original verification.'};args.update(kw)
  return self.s.record(**args)
 def test_accepted_is_not_officially_verified(self):
  result=self.capture();self.assertTrue(result['configured_host_matched']);self.assertFalse(result['official_source_authenticated']);self.assertFalse(result['network_accessed'])
 def test_history_does_not_disclose_document(self):
  self.capture();data=self.s.list_records(self.v,self.m,self.e);self.assertEqual(1,len(data['records']));self.assertNotIn('FICTIONAL PDF',str(data))
 def test_viewer_write_denied(self):
  with self.assertRaises(Denied):self.capture(token=self.v)
 def test_cross_firm_denied(self):
  with self.assertRaises(Denied):self.capture(token=self.x)
 def test_revoked_denied(self):
  self.c.revoke_token(self.t)
  with self.assertRaises(Denied):self.capture()
 def test_wrong_evidence_denied(self):
  with self.assertRaises(EvidenceInvalid):self.capture(evidence_id='0'*32)
 def test_modified_research_denied(self):
  self.c.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',('altered',self.e))
  with self.assertRaises(EvidenceInvalid):self.capture()
 def test_tampered_record_detected(self):
  self.capture();self.c.db.execute('UPDATE official_source_intake SET reviewed_note=?',('altered',))
  with self.assertRaises(EvidenceInvalid):self.s.list_records(self.t,self.m,self.e)
 def test_phishing_subdomain_denied(self):
  with self.assertRaises(EvidenceInvalid):self.capture(url='https://opinions.example.gov.attacker.test/x')
 def test_http_denied(self):
  with self.assertRaises(EvidenceInvalid):self.capture(url='http://opinions.example.gov/x')
 def test_userinfo_denied(self):
  with self.assertRaises(EvidenceInvalid):self.capture(url='https://attacker@opinions.example.gov/x')
 def test_nonstandard_port_denied(self):
  with self.assertRaises(EvidenceInvalid):self.capture(url='https://opinions.example.gov:8443/x')
 def test_localhost_denied(self):
  with self.assertRaises(EvidenceInvalid):OfficialSourceIntake(self.c,['127.0.0.1'])
 def test_document_oversize_denied(self):
  with self.assertRaises(EvidenceInvalid):self.capture(document=b'a'*(128*1024+1))
 def test_no_automatic_network(self):
  import socket
  original=socket.socket.connect
  def blocked(*a,**kw):raise AssertionError('Network attempted')
  socket.socket.connect=blocked
  try:self.capture()
  finally:socket.socket.connect=original
 def test_restart_persistence(self):
  self.capture();self.c.close();self.c=SecureCore(self.path)
  s=OfficialSourceIntake(self.c,['opinions.example.gov'])
  self.assertEqual(1,len(s.list_records(self.t,self.m,self.e)['records']))

if __name__=='__main__':unittest.main()
