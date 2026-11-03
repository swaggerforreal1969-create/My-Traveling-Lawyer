"""End-to-end tests: genuine local research / observation / independent review services."""
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from src.secure_engine import SecureCore, Denied, Stale
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.source_observation import SourceObservation
from src.second_source_review import SecondSourceReview
from src.attorney_journey import AttorneyJourney


class RealResearchJourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        self.firm = self.core.provision_firm('Fictional Law LLC')
        self.owner, self.token = self.core.provision_user(self.firm, 'Lawyer 1')
        self.reviewer_id, self.reviewer_token = self.core.provision_user(self.firm, 'Lawyer 2')
        self.viewer_id, self.viewer_token = self.core.provision_user(self.firm, 'Viewer')
        self.other_firm = self.core.provision_firm('Other Fictional Firm')
        _, self.other_token = self.core.provision_user(self.other_firm, 'Other Lawyer')
        self.mid = self.core.create_matter(self.token, 'CONFIDENTIAL MATTER TITLE')['id']
        self.core.grant(self.token, self.mid, self.reviewer_id, 'editor', 1)
        self.core.grant(self.token, self.mid, self.viewer_id, 'viewer', 2)
        self.core.add_note(self.token, self.mid, 'SECRET PRIVILEGED NOTE')
        self.task = self.core.create_task(self.token, self.mid, 'SECRET TASK DESCRIPTION',
                                         '2026-10-01T00:00:00+00:00')
        self.evidence = ResearchEvidence(self.core)
        self.observation = SourceObservation(self.core)
        self.review = SecondSourceReview(self.core)
        self.eid = self.evidence.add(self.token, self.mid, 'SECRET SOURCE TITLE',
                       'https://example.org/fictional-authority', 'SECRET RESEARCH EXCERPT')['id']
        self.journey = AttorneyJourney(self.core)
        self.now = datetime(2026,11,3,tzinfo=timezone.utc)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def snapshot(self, token=None):
        return self.journey.open(token or self.token, self.mid, now=self.now)

    def check_private(self, snap):
        html = snap.readiness_html
        for secret in (b'CONFIDENTIAL MATTER TITLE', b'SECRET PRIVILEGED NOTE',
                       b'SECRET TASK DESCRIPTION', b'SECRET SOURCE TITLE',
                       b'SECRET RESEARCH EXCERPT', self.mid.encode(), self.eid.encode()):
            self.assertNotIn(secret, html)
        self.assertIn(b'Not legal advice', html)
        self.assertIn(b'No AI transmission', html)

    def test_full_lifecycle_and_task_completion(self):
        initial=self.snapshot(); self.check_private(initial)
        self.assertIn(b'First source observation required', initial.readiness_html)
        obs=self.observation.capture(self.token,self.mid,self.eid,'Manual fictional source text',
                                     'First lawyer manually observed local test text')
        self.assertIn(b'Second human review required',self.snapshot().readiness_html)
        with self.assertRaises(EvidenceInvalid):
            self.review.record(self.token,self.mid,self.eid,obs['observation_id'],
                'corroborated_manually','First lawyer cannot countersign their own observation')
        self.review.record(self.reviewer_token,self.mid,self.eid,obs['observation_id'],
                'corroborated_manually','Second lawyer checked fictional source locally')
        confirmed=self.snapshot();self.check_private(confirmed)
        self.assertIn(b'Two people reviewed; law unverified',confirmed.readiness_html)
        self.assertNotIn(b'court_filing_approved":true',confirmed.readiness_html)
        updated=self.journey.complete_and_refresh(self.token,self.mid,self.task['id'],1,now=self.now)
        self.assertEqual(len(updated.workbench['open_tasks']),0)
        self.assertIn(b'Open tasks</span><strong>0',updated.readiness_html)
        self.assertTrue(self.core.verify_audit())
        with self.assertRaises(Stale):
            self.journey.complete_and_refresh(self.token,self.mid,self.task['id'],1,now=self.now)

    def test_new_observation_invalidates_prior_two_person_review(self):
        first=self.observation.capture(self.token,self.mid,self.eid,'Earlier fictional original text',
                                       'First observation procedural note')
        self.review.record(self.reviewer_token,self.mid,self.eid,first['observation_id'],
                'corroborated_manually','Second operator review procedural only')
        self.assertIn(b'Two people reviewed; law unverified',self.snapshot().readiness_html)
        self.observation.capture(self.token,self.mid,self.eid,'Newer fictional source text',
                                  'New observation requires new second review')
        self.assertIn(b'Second human review required',self.snapshot().readiness_html)

    def test_viewer_read_only_but_readiness_allowed(self):
        self.check_private(self.snapshot(self.viewer_token))
        with self.assertRaises(Denied):
            self.observation.capture(self.viewer_token,self.mid,self.eid,'Fictional text',
                                     'Viewer must not observe this record')
        with self.assertRaises(Denied):
            self.journey.complete_and_refresh(self.viewer_token,self.mid,self.task['id'],1,now=self.now)

    def test_cross_firm_revocation_and_wrong_matter(self):
        with self.assertRaises(Denied): self.snapshot(self.other_token)
        second=self.core.create_matter(self.token,'SECOND PRIVATE MATTER')['id']
        with self.assertRaises(Denied):
            self.journey.complete_and_refresh(self.token,second,self.task['id'],1,now=self.now)
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied): self.snapshot()

    def test_corrupted_observation_fails_closed(self):
        obs=self.observation.capture(self.token,self.mid,self.eid,'Fictional captured paragraph',
                                     'Observed manually for the test matter')
        self.core.db.execute('UPDATE source_observation SET captured_text=? WHERE observation_id=?',
                             ('SECRET FORGED CONTENT',obs['observation_id']))
        with self.assertRaises(EvidenceInvalid): self.snapshot()

    def test_corrupted_second_review_fails_closed(self):
        obs=self.observation.capture(self.token,self.mid,self.eid,'Fictional captured paragraph',
                                     'Observed manually for the test matter')
        rev=self.review.record(self.reviewer_token,self.mid,self.eid,obs['observation_id'],
                               'corroborated_manually','Valid fictional manual review note')
        self.core.db.execute('UPDATE source_second_review SET decision=? WHERE id=?',
                             ('rejected',rev['review_id']))
        with self.assertRaises(EvidenceInvalid):self.snapshot()


if __name__=='__main__':unittest.main()
