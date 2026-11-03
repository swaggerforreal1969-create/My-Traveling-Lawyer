import unittest
import tempfile
from pathlib import Path
from src.secure_engine import SecureCore, Denied, Stale, Invalid

class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.core=SecureCore()
        self.firm=self.core.provision_firm('Imaginary Firm')
        self.owner,self.owner_token=self.core.provision_user(self.firm,'Owner')
        self.editor,self.editor_token=self.core.provision_user(self.firm,'Editor')
        self.viewer,self.viewer_token=self.core.provision_user(self.firm,'Viewer')
        self.other_firm=self.core.provision_firm('Second Firm')
        self.outsider,self.out_token=self.core.provision_user(self.other_firm,'Outsider')
        self.m=self.core.create_matter(self.owner_token,'Fictional Matter')
    def tearDown(self):self.core.close()
    def assertDenied(self, fn, *args):
        with self.assertRaises(Denied):fn(*args)
    def test_owner_reads_own(self):self.assertEqual(1,len(self.core.list_matters(self.owner_token)))
    def test_ungranted_colleague_cannot_read(self):self.assertDenied(self.core.read_notes,self.editor_token,self.m['id'])
    def test_other_firm_cannot_read(self):self.assertDenied(self.core.read_notes,self.out_token,self.m['id'])
    def test_other_firm_cannot_grant(self):self.assertDenied(self.core.grant,self.owner_token,self.m['id'],self.outsider,'editor',1)
    def test_viewer_can_read(self):
        self.core.grant(self.owner_token,self.m['id'],self.viewer,'viewer',1)
        self.assertEqual([],self.core.read_notes(self.viewer_token,self.m['id']))
    def test_viewer_cannot_write(self):
        self.core.grant(self.owner_token,self.m['id'],self.viewer,'viewer',1)
        self.assertDenied(self.core.add_note,self.viewer_token,self.m['id'],'Secret')
    def test_editor_can_write(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        self.core.add_note(self.editor_token,self.m['id'],'Fictional')
        self.assertEqual(1,len(self.core.read_notes(self.owner_token,self.m['id'])))
    def test_editor_cannot_grant(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        self.assertDenied(self.core.grant,self.editor_token,self.m['id'],self.viewer,'viewer',2)
    def test_stale_grant_denied(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        with self.assertRaises(Stale):self.core.grant(self.owner_token,self.m['id'],self.viewer,'viewer',1)
        self.assertDenied(self.core.read_notes,self.viewer_token,self.m['id'])
    def test_revocation(self):
        self.core.revoke_token(self.owner_token)
        self.assertDenied(self.core.list_matters,self.owner_token)
    def test_fake_token(self):self.assertDenied(self.core.list_matters,'not_a_valid_token')
    def test_wrong_firm_not_listed(self):self.assertEqual([],self.core.list_matters(self.out_token))
    def test_no_permission_leak_on_unknown_matter(self):self.assertDenied(self.core.read_notes,self.owner_token,'bogus')
    def test_persistent_authorization(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'test.db'
            a=SecureCore(path); fid=a.provision_firm('Test'); uid,token=a.provision_user(fid,'Tester'); a.create_matter(token,'Test'); a.close()
            b=SecureCore(path); self.assertEqual(1,len(b.list_matters(token)));b.close()
    def test_invalid_role(self):
        with self.assertRaises(Invalid):self.core.grant(self.owner_token,self.m['id'],self.editor,'owner',1)
    def test_missing_token(self):self.assertDenied(self.core.list_matters,None)
    def test_viewer_cannot_see_another_matter(self):
        self.core.grant(self.owner_token,self.m['id'],self.viewer,'viewer',1)
        new=self.core.create_matter(self.owner_token,'Other case')
        self.assertDenied(self.core.read_notes,self.viewer_token,new['id'])
    def test_stale_cannot_escalate(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'viewer',1)
        with self.assertRaises(Stale):self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        self.assertDenied(self.core.add_note,self.editor_token,self.m['id'],'Nope')

if __name__=='__main__':unittest.main()
