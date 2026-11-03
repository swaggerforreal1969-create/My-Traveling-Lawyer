"""Fictional source-observation tests; no automatic legal research or network."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.source_observation import SourceObservation


class SourceObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fictional.sqlite3'
        self.core = SecureCore(self.path)
        firm = self.core.provision_firm('Imaginary Legal Office')
        self.owner, self.token = self.core.provision_user(firm, 'Invented Attorney')
        self.viewer, self.viewer_token = self.core.provision_user(firm, 'Mock Reader')
        other = self.core.provision_firm('Different Fictional Practice')
        _, self.outsider = self.core.provision_user(other, 'Fictional Outsider')
        self.matter = self.core.create_matter(self.token, 'Fictional Dispute')['id']
        self.core.grant(self.token, self.matter, self.viewer, 'viewer', 1)
        self.research = ResearchEvidence(self.core)
        self.evidence = self.research.add(self.token,self.matter,'Imaginary Appeal',
            'https://example.org/fictional-decision','Imaginary decision text')['id']
        self.observations = SourceObservation(self.core)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def capture(self):
        return self.observations.capture(self.token,self.matter,self.evidence,
                    'Exact fictional observation text', 'Manually checked illustrative excerpt')

    def test_capture_flags_are_never_official(self):
        r = self.capture()
        self.assertFalse(r['official_source_authenticated'])
        self.assertFalse(r['current_legal_authority_verified'])
        self.assertFalse(r['network_accessed'])

    def test_history_integrity_and_metadata_only(self):
        self.capture()
        h=self.observations.history(self.token,self.matter,self.evidence)
        self.assertTrue(h['local_hash_integrity'])
        self.assertEqual(1,len(h['observations']))
        self.assertNotIn('captured_text',h['observations'][0])

    def test_viewer_can_read_but_not_capture(self):
        self.capture()
        self.assertEqual(1,len(self.observations.history(self.viewer_token,self.matter,self.evidence)['observations']))
        with self.assertRaises(Denied):
            self.observations.capture(self.viewer_token,self.matter,self.evidence,'Mock snapshot','More than twelve characters')

    def test_outsider_and_wrong_matter_denied(self):
        for token, matter in ((self.outsider,self.matter),(self.token,'nonexistent')):
            with self.assertRaises(Denied):
                self.observations.history(token,matter,self.evidence)

    def test_revoked_token_denied(self):
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):self.capture()

    def test_reject_wrong_evidence(self):
        with self.assertRaises(EvidenceInvalid):
            self.observations.capture(self.token,self.matter,'f'*32,'Mock text','Human review comment here')

    def test_reject_invalid_text_and_note(self):
        for body,note in (('', 'This is adequate note'), ('abc','short'),('x'*12001,'Adequate human observation')):
            with self.assertRaises(EvidenceInvalid):
                self.observations.capture(self.token,self.matter,self.evidence,body,note)

    def test_tampered_original_research_denied(self):
        self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',('altered',self.evidence))
        with self.assertRaises(EvidenceInvalid):self.capture()

    def test_tampered_observation_text_denied(self):
        self.capture()
        self.core.db.execute('UPDATE source_observation SET captured_text=?',('altered',))
        with self.assertRaises(EvidenceInvalid):self.observations.history(self.token,self.matter,self.evidence)

    def test_tampered_metadata_denied(self):
        self.capture()
        self.core.db.execute('UPDATE source_observation SET note=?',('changed metadata',))
        with self.assertRaises(EvidenceInvalid):self.observations.history(self.token,self.matter,self.evidence)

    def test_mismatched_original_digest_denied(self):
        self.capture()
        self.core.db.execute('UPDATE source_observation SET evidence_digest=?',('fake',))
        with self.assertRaises(EvidenceInvalid):self.observations.history(self.token,self.matter,self.evidence)

    def test_restart_persistence(self):
        self.capture()
        self.core.close()
        self.core=SecureCore(self.path)
        self.observations=SourceObservation(self.core)
        h=self.observations.history(self.token,self.matter,self.evidence)
        self.assertEqual(1,len(h['observations']))

    def test_no_outbound_network(self):
        with patch('socket.socket.connect',side_effect=AssertionError('network attempted')):
            self.capture()
            self.observations.history(self.token,self.matter,self.evidence)

    def test_recorded_audit(self):
        before=self.core.audit_head()['seq']
        self.capture()
        self.assertGreater(self.core.audit_head()['seq'],before)

    def test_read_only_history_no_audit_write(self):
        self.capture()
        before=self.core.audit_head()['seq']
        self.observations.history(self.token,self.matter,self.evidence)
        self.assertEqual(before,self.core.audit_head()['seq'])

if __name__=='__main__':unittest.main()
