"""Defensive fictional-only audit mirror and authorization regression."""
import tempfile
import unittest
from pathlib import Path
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence

class AuditMirrorFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'fictional.sqlite3'
        self.core=SecureCore(self.path)
        firm=self.core.provision_firm('Fictional law firm')
        _,self.owner=self.core.provision_user(firm,'Fictional owner')
        self.matter=self.core.create_matter(self.owner,'Imaginary matter')['id']
        other=self.core.provision_firm('Unrelated fictional firm')
        _,self.outside=self.core.provision_user(other,'Outsider')
    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()
    def test_valid_history_reopens(self):
        self.assertTrue(self.core.verify_audit())
        self.core.create_task(self.owner,self.matter,'Fictional task','2030-01-01T00:00:00Z')
        self.core.close()
        self.core=SecureCore(self.path)
        self.assertTrue(self.core.verify_audit())
    def test_deleted_chain_fails_instead_of_becoming_valid_genesis(self):
        self.core.db.execute('DELETE FROM audit_chain')
        self.assertFalse(self.core.verify_audit())
    def test_truncated_chain_fails(self):
        ResearchEvidence(self.core).add(self.owner,self.matter,
            'Fictional source','https://example.org/imagined','Imaginary excerpt')
        self.assertTrue(self.core.verify_audit())
        self.core.db.execute(
            'DELETE FROM audit_chain WHERE seq=(SELECT max(seq) FROM audit_chain)')
        self.assertFalse(self.core.verify_audit())
    def test_deleted_mirror_fails(self):
        self.core.db.execute('DELETE FROM audit')
        self.assertFalse(self.core.verify_audit())
    def test_altered_mirror_fails(self):
        self.core.db.execute("UPDATE audit SET action='forged' WHERE seq=1")
        self.assertFalse(self.core.verify_audit())
    def test_altered_hash_fails(self):
        self.core.db.execute("UPDATE audit_chain SET row_hash='bad' WHERE seq=1")
        self.assertFalse(self.core.verify_audit())
    def test_cross_firm_read_denied(self):
        with self.assertRaises(Denied):
            self.core.read_notes(self.outside,self.matter)
        self.assertTrue(self.core.verify_audit())
    def test_new_empty_database_still_valid(self):
        empty=SecureCore(Path(self.tmp.name)/'empty.sqlite3')
        try:
            self.assertTrue(empty.verify_audit())
        finally:
            empty.close()
