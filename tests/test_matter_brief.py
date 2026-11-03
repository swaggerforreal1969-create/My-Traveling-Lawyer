"""Fictional test fixtures for local matter briefing; no network or AI calls."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.authority_review import AuthorityReview
from src.matter_brief import MatterBrief


class MatterBriefTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.folder.name) / 'data.sqlite3')
        f = self.core.provision_firm('Fictional Law Group')
        self.uid, self.token = self.core.provision_user(f, 'Invented Lawyer')
        self.viewer_id, self.viewer_token = self.core.provision_user(f, 'Fictional Reader')
        other = self.core.provision_firm('Other Invented Firm')
        _, self.outsider = self.core.provision_user(other, 'Other Lawyer')
        self.mid = self.core.create_matter(self.token, 'Imaginary case')['id']
        self.core.grant(self.token, self.mid, self.viewer_id, 'viewer', 1)
        self.research = ResearchEvidence(self.core)
        self.reviews = AuthorityReview(self.core)
        self.brief = MatterBrief(self.core)

    def tearDown(self):
        self.core.close()
        self.folder.cleanup()

    def add_source(self):
        return self.research.add(self.token, self.mid, 'Fabricated case',
            'https://example.org/invented', 'Fictional authority excerpt text.')['id']

    def test_empty_brief_explicit_guardrails(self):
        b = self.brief.prepare(self.token, self.mid)
        self.assertEqual('mtl.matter.preparation.v1', b['schema'])
        self.assertFalse(b['legal_deadlines_verified'])
        self.assertFalse(b['outbound_ai_transmission'])
        self.assertEqual([], b['research_sources'])

    def test_cross_firm_and_ungranted_denied(self):
        with self.assertRaises(Denied): self.brief.prepare(self.outsider, self.mid)
        with self.assertRaises(Denied): self.brief.prepare(self.token, 'invented-other-id')

    def test_viewer_allowed_without_write(self):
        self.core.add_note(self.token, self.mid, 'Fictional client asked for a summary.')
        b = self.brief.prepare(self.viewer_token, self.mid)
        self.assertEqual(1, len(b['notes']))
        with self.assertRaises(Denied): self.core.add_note(self.viewer_token, self.mid, 'Cannot write')

    def test_past_user_entered_task_is_not_court_rule(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.core.create_task(self.token, self.mid, 'Review invented facts', past)
        b = self.brief.prepare(self.token, self.mid)
        self.assertTrue(b['open_tasks'][0]['past_user_entered_due_time'])
        self.assertFalse(b['legal_deadlines_verified'])
        self.assertIn('court deadlines', ' '.join(b['risk_notices']))

    def test_human_attestation_not_software_verification(self):
        eid = self.add_source()
        self.reviews.record(self.token, self.mid, eid, 'checked_against_original',
            'Checked the fictional authority against the mock original.')
        b = self.brief.prepare(self.token, self.mid)
        s = b['research_sources'][0]
        self.assertEqual('checked_against_original', s['last_human_assessment'])
        self.assertFalse(s['software_verified'])

    def test_latest_recheck_surfaces_as_risk(self):
        eid = self.add_source()
        self.reviews.record(self.token, self.mid, eid, 'checked_against_original',
            'Checked initial imaginary citation content with mock original.')
        self.reviews.record(self.token, self.mid, eid, 'needs_recheck',
            'The imaginary authority may be stale, recheck before use.')
        b = self.brief.prepare(self.token, self.mid)
        self.assertEqual('needs_recheck', b['research_sources'][0]['last_human_assessment'])
        self.assertTrue(any('research sources' in x for x in b['risk_notices']))

    def test_tampered_source_fails_closed(self):
        eid = self.add_source()
        self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?', ('tampered', eid))
        with self.assertRaises(EvidenceInvalid): self.brief.prepare(self.token, self.mid)

    def test_tampered_review_digest_fails_closed(self):
        eid = self.add_source()
        self.reviews.record(self.token, self.mid, eid, 'rejected', 'This fictional citation is rejected in review.')
        self.core.db.execute('UPDATE authority_review_events SET evidence_digest=?', ('wrong',))
        with self.assertRaises(EvidenceInvalid): self.brief.prepare(self.token, self.mid)

    def test_revoked_token_denied(self):
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied): self.brief.prepare(self.token, self.mid)

    def test_bounded_snapshot_rejects_overflow(self):
        for i in range(101):
            self.core.add_note(self.token, self.mid, f'Fictional note {i}')
        with self.assertRaises(EvidenceInvalid): self.brief.prepare(self.token, self.mid)

    def test_naive_time_is_rejected(self):
        with self.assertRaises(EvidenceInvalid):
            self.brief.prepare(self.token, self.mid, now=datetime(2026, 11, 3))

    def test_read_only_snapshot_no_new_audit(self):
        before = self.core.audit_head()['seq']
        self.brief.prepare(self.token, self.mid)
        self.assertEqual(before, self.core.audit_head()['seq'])


if __name__ == '__main__':
    unittest.main()
