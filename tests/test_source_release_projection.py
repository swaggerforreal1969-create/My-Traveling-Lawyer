"""Real-core, fictional-data adversarial tests for legal review projection."""
import tempfile
import unittest
from pathlib import Path
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.source_observation import SourceObservation
from src.second_source_review import SecondSourceReview
from src.source_release_projection import SourceReleaseProjection


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'demo.sqlite3'
        self.core = SecureCore(self.path)
        firm = self.core.provision_firm('Imaginary Partners')
        self.writer_id, self.writer = self.core.provision_user(firm, 'Fictional Writer')
        self.reviewer_id, self.reviewer = self.core.provision_user(firm, 'Fictional Reviewer')
        self.viewer_id, self.viewer = self.core.provision_user(firm, 'Fictional Viewer')
        other_firm = self.core.provision_firm('Other Fictional Firm')
        _, self.outsider = self.core.provision_user(other_firm, 'Fictional Outsider')
        self.matter = self.core.create_matter(self.writer, 'Invented hearing')['id']
        self.core.grant(self.writer, self.matter, self.reviewer_id, 'editor', 1)
        self.core.grant(self.writer, self.matter, self.viewer_id, 'viewer', 2)
        self.evidence = ResearchEvidence(self.core)
        self.obs = SourceObservation(self.core)
        self.second = SecondSourceReview(self.core)
        self.projection = SourceReleaseProjection(self.core)
        self.source = self.evidence.add(self.writer, self.matter,
            'Invented precedent', 'https://example.org/fictional', 'Invented text only')['id']

    def tearDown(self):
        self.core.close()
        self.temp.cleanup()

    def observe(self):
        return self.obs.capture(self.writer, self.matter, self.source,
            'An entirely fictional source excerpt', 'Mock human observation only')['observation_id']

    def review(self, observation, decision='corroborated_manually'):
        return self.second.record(self.reviewer, self.matter, self.source,
            observation, decision, 'The fictional second reviewer checked the record')

    def get(self, token=None):
        return self.projection.project(token or self.writer, self.matter)

    def test_initial_source_needs_observation(self):
        self.assertEqual('needs_first_observation', self.get()['sources'][0]['procedural_status'])

    def test_single_observation_needs_independent_review(self):
        self.observe()
        self.assertEqual('needs_independent_second_review', self.get()['sources'][0]['procedural_status'])

    def test_two_people_never_certifies_law(self):
        self.review(self.observe())
        record = self.get()['sources'][0]
        self.assertEqual('two_people_reviewed_unverified', record['procedural_status'])
        self.assertFalse(record['usable_without_attorney_validation'])
        self.assertFalse(self.get()['court_filing_approved'])
        self.assertFalse(self.get()['legal_authorities_verified_by_software'])

    def test_rejected_and_further_review(self):
        for decision, status in [('rejected', 'rejected_by_second_reviewer'),
                                 ('needs_further_review', 'needs_additional_review')]:
            with self.subTest(decision=decision):
                self.review(self.observe(), decision)
                self.assertEqual(status, self.get()['sources'][0]['procedural_status'])

    def test_new_observation_invalidates_old_manual_corroboration(self):
        self.review(self.observe())
        self.observe()
        self.assertEqual('needs_independent_second_review', self.get()['sources'][0]['procedural_status'])

    def test_source_excerpt_tamper_fails_closed(self):
        self.observe()
        self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?', ('corrupt', self.source))
        with self.assertRaises(EvidenceInvalid): self.get()

    def test_observation_tamper_fails_closed(self):
        self.observe()
        self.core.db.execute('UPDATE source_observation SET captured_text=?', ('corrupt',))
        with self.assertRaises(EvidenceInvalid): self.get()

    def test_second_review_tamper_fails_closed(self):
        self.review(self.observe())
        self.core.db.execute('UPDATE source_second_review SET decision=?', ('rejected',))
        with self.assertRaises(EvidenceInvalid): self.get()

    def test_cross_firm_denied(self):
        with self.assertRaises(Denied): self.get(self.outsider)

    def test_revoked_credential_denied(self):
        self.core.revoke_token(self.writer)
        with self.assertRaises(Denied): self.get(self.writer)

    def test_viewer_can_inspect_without_raw_text(self):
        self.review(self.observe())
        response = self.get(self.viewer)
        self.assertEqual(1, len(response['sources']))
        self.assertNotIn('excerpt', str(response))
        self.assertNotIn('https://', str(response))
        self.assertNotIn('fictional source excerpt', str(response))

    def test_persistence_after_restart(self):
        self.review(self.observe())
        self.core.close()
        self.core = SecureCore(self.path)
        self.projection = SourceReleaseProjection(self.core)
        self.assertEqual('two_people_reviewed_unverified', self.get()['sources'][0]['procedural_status'])

    def test_invalid_matter_and_no_network(self):
        with self.assertRaises(EvidenceInvalid): self.projection.project(self.writer, '')
        import unittest.mock as mock
        with mock.patch('socket.socket.connect', side_effect=AssertionError('network attempt')):
            self.assertEqual(1, len(self.get()['sources']))

    def test_no_business_audit_append_on_projection(self):
        self.observe()
        before = self.core.audit_head()['seq']
        self.get()
        self.assertEqual(before, self.core.audit_head()['seq'])

    def test_source_collection_limit_fails_closed(self):
        for index in range(100):
            self.evidence.add(self.writer, self.matter,
                'Invented ' + str(index), 'https://example.org/fictional', 'Fictional excerpt')
        with self.assertRaises(EvidenceInvalid): self.get()


if __name__ == '__main__': unittest.main()
