import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from src.secure_engine import SecureCore, Denied, Stale
from src.attorney_journey import AttorneyJourney, JourneyRejected
from src.json_mobile_document import UnsafeReadinessDocument

class Response:
    def __init__(self, body):
        self.status=200
        self.body=body
        self.headers=(('Content-Type','application/json; charset=utf-8'),
            ('Cache-Control','no-store, private'),('X-Content-Type-Options','nosniff'),
            ('Content-Length',str(len(body))))

class ReadinessFixture:
    """Only the readiness provider is a fixture; task and ACL use real SecureCore."""
    def __init__(self, core):
        self.core=core
        self.tamper=None
    def prepare(self, token, mid, *, now=None):
        with self.core.lock:
            actor=self.core._identity(token)
            self.core._role(actor,mid,('owner','editor','viewer'))
            now=now or datetime.now(timezone.utc)
            rows=self.core.db.execute('SELECT due_at FROM tasks WHERE matter_id=? AND completed=0',(mid,)).fetchall()
        data={'schema':'mtl.private.readiness.counts.v1','open_tasks':len(rows),
            'past_user_entered_dates_not_court_deadlines':sum(datetime.fromisoformat(r['due_at'])<now for r in rows),
            'research_sources':0,'research_needing_procedural_work':0,
            'review_counts':{'needs_additional_review':0,'needs_first_observation':0,
            'needs_independent_second_review':0,'rejected_by_second_reviewer':0,
            'two_people_reviewed_unverified':0},
            'legal_source_authenticated':False,'legal_deadlines_verified':False,
            'court_filing_approved':False,'outbound_ai_transmission':False,
            'human_review_is_legal_verification':False}
        if self.tamper: self.tamper(data)
        return Response(json.dumps(data).encode())

class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.core=SecureCore(Path(self.tmp.name)/'test.db')
        self.firm=self.core.provision_firm('Fictional firm');self.owner_id,self.owner=self.core.provision_user(self.firm,'Fictional owner')
        self.viewer_id,self.viewer=self.core.provision_user(self.firm,'Fictional viewer')
        other=self.core.provision_firm('Other firm');_,self.other=self.core.provision_user(other,'Stranger')
        self.mid=self.core.create_matter(self.owner,'PRIVATE TITLE')['id'];self.core.add_note(self.owner,self.mid,'SECRET NOTE')
        self.task=self.core.create_task(self.owner,self.mid,'File memo - fictional', (datetime.now(timezone.utc)+timedelta(days=1)).isoformat())
        self.core.grant(self.owner,self.mid,self.viewer_id,'viewer',1)
        self.provider=ReadinessFixture(self.core);self.journey=AttorneyJourney(self.core,readiness=self.provider)
    def tearDown(self):self.core.close();self.tmp.cleanup()
    def test_workflow_list_open_complete_refresh(self):
        self.assertEqual(len(self.journey.matters(self.owner)['matters']),1)
        before=self.journey.open(self.owner,self.mid)
        self.assertEqual(len(before.workbench['open_tasks']),1)
        after=self.journey.complete_and_refresh(self.owner,self.mid,self.task['id'],1)
        self.assertEqual(len(after.workbench['open_tasks']),0)
        self.assertIn(b'Open tasks',after.readiness_html)
        self.assertTrue(self.core.verify_audit())
    def test_private_data_absent_in_mobile(self):
        doc=self.journey.open(self.owner,self.mid)
        self.assertNotIn(b'SECRET NOTE',doc.readiness_html)
        self.assertNotIn(b'PRIVATE TITLE',doc.readiness_html)
        self.assertNotIn(self.mid.encode(),doc.readiness_html)
        self.assertNotIn(b'<script',doc.readiness_html)
        self.assertIn(b'no-store',str(doc.readiness_headers).encode())
    def test_viewer_can_read_cannot_complete(self):
        self.assertEqual(len(self.journey.open(self.viewer,self.mid).workbench['open_tasks']),1)
        with self.assertRaises(Denied):self.journey.complete_and_refresh(self.viewer,self.mid,self.task['id'],1)
    def test_other_firm_denied(self):
        with self.assertRaises(Denied):self.journey.open(self.other,self.mid)
    def test_same_firm_ungranted_denied(self):
        _,token=self.core.provision_user(self.firm,'Ungrant')
        with self.assertRaises(Denied):self.journey.open(token,self.mid)
    def test_revoked_denied(self):
        self.core.revoke_token(self.owner)
        with self.assertRaises(Denied):self.journey.open(self.owner,self.mid)
    def test_wrong_matter_completion_denied(self):
        other=self.core.create_matter(self.owner,'Other')['id']
        with self.assertRaises(Denied):self.journey.complete_and_refresh(self.owner,other,self.task['id'],1)
    def test_replay_fails_and_single_audit_write(self):
        self.journey.complete_and_refresh(self.owner,self.mid,self.task['id'],1)
        with self.assertRaises(Stale):self.journey.complete_and_refresh(self.owner,self.mid,self.task['id'],1)
        self.assertTrue(self.core.verify_audit())
    def test_forged_legal_claim_fails(self):
        self.provider.tamper=lambda d:d.update(court_filing_approved=True)
        with self.assertRaises(UnsafeReadinessDocument):self.journey.open(self.owner,self.mid)
    def test_mismatched_count_fails(self):
        self.provider.tamper=lambda d:d.update(open_tasks=2)
        with self.assertRaises(JourneyRejected):self.journey.open(self.owner,self.mid)
    def test_concurrent_completion_one_winner(self):
        def run(_):
            try:
                self.journey.complete_and_refresh(self.owner,self.mid,self.task['id'],1)
                return 'ok'
            except Stale:return 'stale'
        with ThreadPoolExecutor(max_workers=6) as ex:out=list(ex.map(run,range(6)))
        self.assertEqual(out.count('ok'),1)
        self.assertEqual(out.count('stale'),5)
    def test_failed_refresh_does_not_retry_write(self):
        self.provider.tamper=lambda d:d.update(court_filing_approved=True)
        with self.assertRaises(UnsafeReadinessDocument):self.journey.complete_and_refresh(self.owner,self.mid,self.task['id'],1)
        # A committed completion remains committed; recovery is read-only.
        self.assertEqual(len(self.core.dashboard(self.owner)['upcoming_tasks']),0)
        self.assertTrue(self.core.verify_audit())

if __name__=='__main__':unittest.main()
