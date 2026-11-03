import tempfile
import threading
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from src.secure_engine import SecureCore, Denied, Stale, Invalid
from src.attorney_workbench import AttorneyWorkbench

class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.core=SecureCore(Path(self.tmp.name)/'fictional.db')
        self.firm=self.core.provision_firm('Fictional Firm')
        self.uid,self.token=self.core.provision_user(self.firm,'Owner')
        self.uid2,self.viewer=self.core.provision_user(self.firm,'Viewer')
        self.otherfirm=self.core.provision_firm('Other Fictional Firm')
        _,self.outsider=self.core.provision_user(self.otherfirm,'Outsider')
        self.matter=self.core.create_matter(self.token,'CONFIDENTIAL imaginary matter')['id']
        self.wb=AttorneyWorkbench(self.core)
        self.task=self.core.create_task(self.token,self.matter,'Review fictional discovery',(datetime.now(timezone.utc)-timedelta(days=2)).isoformat())['id']
    def tearDown(self):
        self.core.close();self.tmp.cleanup()
    def test_owner_end_to_end(self):
        idx=self.wb.matters(self.token)
        self.assertEqual(len(idx['matters']),1)
        snapshot=self.wb.matter(self.token,self.matter)
        self.assertTrue(snapshot['can_complete_tasks'])
        self.assertTrue(snapshot['open_tasks'][0]['past_user_entered_date'])
        self.assertFalse(snapshot['legal_deadlines_verified'])
        result=self.wb.complete(self.token,self.matter,self.task,snapshot['open_tasks'][0]['version'])
        self.assertTrue(result['completed'])
        self.assertEqual(len(self.wb.matter(self.token,self.matter)['open_tasks']),0)
        self.assertTrue(self.core.verify_audit())
    def test_viewer_can_read_but_cannot_complete(self):
        self.core.grant(self.token,self.matter,self.uid2,'viewer',1)
        self.assertFalse(self.wb.matter(self.viewer,self.matter)['can_complete_tasks'])
        with self.assertRaises(Denied):self.wb.complete(self.viewer,self.matter,self.task,1)
    def test_cross_firm_denied(self):
        self.assertEqual(self.wb.matters(self.outsider)['matters'],[])
        with self.assertRaises(Denied): self.wb.matter(self.outsider,self.matter)
    def test_ungranted_same_firm_denied(self):
        with self.assertRaises(Denied): self.wb.matter(self.viewer,self.matter)
    def test_wrong_matter_denied_without_mutating_task(self):
        other=self.core.create_matter(self.token,'Other matter')['id']
        with self.assertRaises(Denied):self.wb.complete(self.token,other,self.task,1)
        self.assertEqual(len(self.wb.matter(self.token,self.matter)['open_tasks']),1)
    def test_stale_completion_does_not_replay(self):
        self.wb.complete(self.token,self.matter,self.task,1)
        with self.assertRaises(Stale):self.wb.complete(self.token,self.matter,self.task,1)
    def test_revoked_credential_denied(self):
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied): self.wb.matters(self.token)
        with self.assertRaises(Denied): self.wb.matter(self.token,self.matter)
    def test_bad_inputs_rejected(self):
        for v in (True,0,'1',-1):
            with self.subTest(v=v),self.assertRaises(Invalid):self.wb.complete(self.token,self.matter,self.task,v)
        with self.assertRaises(Invalid):self.wb.matter(self.token,'')
    def test_no_notes_leak_and_no_legal_approval(self):
        self.core.add_note(self.token,self.matter,'ULTRA PRIVATE CONFIDENTIAL NOTE')
        output=repr(self.wb.matter(self.token,self.matter))
        self.assertNotIn('ULTRA PRIVATE',output)
        self.assertNotIn('CONFIDENTIAL imaginary matter',output)
        self.assertFalse(self.wb.matter(self.token,self.matter)['court_filing_approved'])
    def test_concurrent_same_version_exactly_one_completion(self):
        results=[]
        def run():
            try:self.wb.complete(self.token,self.matter,self.task,1);results.append('done')
            except Stale:results.append('stale')
        threads=[threading.Thread(target=run) for _ in range(6)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(results.count('done'),1)
        self.assertEqual(results.count('stale'),5)
        self.assertTrue(self.core.verify_audit())

if __name__=='__main__':unittest.main()
