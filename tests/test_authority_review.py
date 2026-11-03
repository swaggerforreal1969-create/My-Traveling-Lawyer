import tempfile
import unittest
from pathlib import Path
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.authority_review import AuthorityReview


class HumanAuthorityReviewTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.db = Path(self.t.name) / 'mock.db'
        self.core = SecureCore(self.db)
        self.firm = self.core.provision_firm('Fictional Firm')
        self.owner, self.token = self.core.provision_user(self.firm, 'Mock Attorney')
        self.viewer, self.viewer_token = self.core.provision_user(self.firm, 'Mock Viewer')
        other = self.core.provision_firm('Imaginary Second Firm')
        self.other, self.other_token = self.core.provision_user(other, 'Other Firm Attorney')
        self.mid = self.core.create_matter(self.token, 'Fictional claim')['id']
        self.rm = ResearchEvidence(self.core)
        self.review = AuthorityReview(self.core)
        self.eid = self.rm.add(self.token, self.mid, 'Invented citation', 'https://example.org/fake', 'This is fictional source text.')['id']

    def tearDown(self):
        self.core.close()
        self.t.cleanup()

    def do_review(self, **kw):
        return self.review.record(kw.get('token', self.token), kw.get('matter_id', self.mid),
            kw.get('evidence_id', self.eid), kw.get('decision', 'checked_against_original'),
            kw.get('note', 'I manually compared the fictional citation with a fictional source.'))

    def test_authorized_attestation_remains_human_only(self):
        d = self.do_review()
        self.assertTrue(d['human_attestation_recorded'])
        self.assertFalse(d['legal_authority_verified_by_software'])
        self.assertEqual(1, len(self.review.history(self.token, self.mid, self.eid)['reviews']))

    def test_ungranted_other_firm_denied(self):
        with self.assertRaises(Denied): self.do_review(token=self.other_token)
        with self.assertRaises(Denied): self.review.history(self.other_token, self.mid, self.eid)

    def test_viewer_can_read_but_not_attest(self):
        self.core.grant(self.token, self.mid, self.viewer, 'viewer', 1)
        with self.assertRaises(Denied): self.do_review(token=self.viewer_token)
        self.assertEqual([], self.review.history(self.viewer_token, self.mid, self.eid)['reviews'])

    def test_forged_or_wrong_matter_evidence_denied(self):
        other_mid = self.core.create_matter(self.token, 'Fictional second claim')['id']
        with self.assertRaises(EvidenceInvalid): self.do_review(matter_id=other_mid)
        with self.assertRaises(EvidenceInvalid): self.do_review(evidence_id='0' * 32)

    def test_input_validation(self):
        for decision in ('verified', 'authenticated', 'approved', ''):
            with self.subTest(decision=decision), self.assertRaises(EvidenceInvalid):
                self.do_review(decision=decision)
        with self.assertRaises(EvidenceInvalid): self.do_review(note='x')
        with self.assertRaises(EvidenceInvalid): self.do_review(evidence_id='../../etc/passwd')

    def test_append_only_reassessment(self):
        self.do_review(decision='checked_against_original')
        self.do_review(decision='needs_recheck')
        events = self.review.history(self.token, self.mid, self.eid)['reviews']
        self.assertEqual(['checked_against_original', 'needs_recheck'], [r['decision'] for r in events])
        self.assertEqual(2, len({x['event_id'] for x in events}))

    def test_existing_evidence_tampering_fails_closed(self):
        with self.core.lock, self.core.db:
            self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?', ('tampered', self.eid))
        with self.assertRaises(EvidenceInvalid): self.do_review()

    def test_reopen_persists_history(self):
        self.do_review()
        self.core.close()
        self.core = SecureCore(self.db)
        self.review = AuthorityReview(self.core)
        self.assertEqual(1, len(self.review.history(self.token, self.mid, self.eid)['reviews']))

    def test_revoked_token_denied(self):
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied): self.do_review()

    def test_wrong_firm_cannot_guess_event(self):
        self.do_review()
        self.assertEqual([], self.core.list_matters(self.other_token))
        with self.assertRaises(Denied): self.review.history(self.other_token, self.mid, self.eid)


if __name__ == '__main__': unittest.main()