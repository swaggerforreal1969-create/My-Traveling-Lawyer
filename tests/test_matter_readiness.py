"""Real SQLite, fictional identity and matter workflow readiness acceptance."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.source_observation import SourceObservation
from src.second_source_review import SecondSourceReview
from src.matter_readiness import MatterReadiness

class WorkQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.core=SecureCore(Path(self.temp.name)/'readiness.sqlite3')
        firm=self.core.provision_firm('Fictional Tribunal Advocates')
        self.writer_id,self.writer=self.core.provision_user(firm,'Fictional Writer')
        self.reviewer_id,self.reviewer=self.core.provision_user(firm,'Fictional Reviewer')
        self.viewer_id,self.viewer=self.core.provision_user(firm,'Fictional Viewer')
        outside=self.core.provision_firm('Other Fictional Firm')
        _,self.outsider=self.core.provision_user(outside,'Outside Person')
        self.matter=self.core.create_matter(self.writer,'Imaginary Case')['id']
        self.core.grant(self.writer,self.matter,self.reviewer_id,'editor',1)
        self.core.grant(self.writer,self.matter,self.viewer_id,'viewer',2)
        self.evidence=ResearchEvidence(self.core)
        self.observations=SourceObservation(self.core)
        self.reviews=SecondSourceReview(self.core)
        self.queue=MatterReadiness(self.core)
    def tearDown(self):
        self.core.close();self.temp.cleanup()
    def source(self):
        return self.evidence.add(self.writer,self.matter,'Fictional title','https://example.org/fake','Fictional text')['id']
    def observe(self,eid):
        return self.observations.capture(self.writer,self.matter,eid,'An entirely fictional source observation','Manual mock observation only')['observation_id']
    def review(self,eid,oid,decision='corroborated_manually'):
        self.reviews.record(self.reviewer,self.matter,eid,oid,decision,'Independent fictional review only')
    def test_empty(self):
        r=self.queue.summarize(self.writer,self.matter)
        self.assertEqual(0,r['research_source_count']);self.assertFalse(r['court_filing_approved'])
    def test_unobserved_source(self):
        self.source();r=self.queue.summarize(self.writer,self.matter)
        self.assertEqual(1,r['unresolved_research_count']);self.assertEqual(1,r['research_status_counts']['needs_first_observation'])
    def test_reviewed_never_legal_verified(self):
        eid=self.source();self.review(eid,self.observe(eid));r=self.queue.summarize(self.writer,self.matter)
        self.assertEqual(0,r['unresolved_research_count']);self.assertFalse(r['source_authenticated']);self.assertFalse(r['court_filing_approved'])
    def test_newer_observation_reopens(self):
        eid=self.source();self.review(eid,self.observe(eid));self.observe(eid)
        self.assertEqual(1,self.queue.summarize(self.writer,self.matter)['unresolved_research_count'])
    def test_rejected_still_unresolved(self):
        eid=self.source();self.review(eid,self.observe(eid),'rejected')
        self.assertEqual(1,self.queue.summarize(self.writer,self.matter)['research_status_counts']['rejected_by_second_reviewer'])
    def test_past_user_date_not_court_deadline(self):
        self.core.create_task(self.writer,self.matter,'Fictional followup', (datetime.now(timezone.utc)-timedelta(days=2)).isoformat())
        r=self.queue.summarize(self.writer,self.matter)
        self.assertEqual(1,r['past_user_entered_date_count']);self.assertFalse(r['legal_deadlines_verified'])
    def test_viewer_no_private_source_text(self):
        self.source();s=str(self.queue.summarize(self.viewer,self.matter))
        self.assertNotIn('Fictional text',s);self.assertNotIn('https://example.org',s);self.assertNotIn('Imaginary Case',s)
    def test_outsider_denied(self):
        with self.assertRaises(Denied):self.queue.summarize(self.outsider,self.matter)
    def test_revoked_denied(self):
        self.core.revoke_token(self.writer)
        with self.assertRaises(Denied):self.queue.summarize(self.writer,self.matter)
    def test_source_tamper_denied(self):
        eid=self.source();self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',('changed',eid))
        with self.assertRaises(EvidenceInvalid):self.queue.summarize(self.writer,self.matter)
    def test_review_tamper_denied(self):
        eid=self.source();self.review(eid,self.observe(eid));self.core.db.execute('UPDATE source_second_review SET decision=?',('rejected',))
        with self.assertRaises(EvidenceInvalid):self.queue.summarize(self.writer,self.matter)
    def test_read_does_not_append_business_audit(self):
        self.source();before=self.core.audit_head()['seq'];self.queue.summarize(self.writer,self.matter)
        self.assertEqual(before,self.core.audit_head()['seq'])
    def test_bad_time_denied(self):
        with self.assertRaises(EvidenceInvalid):self.queue.summarize(self.writer,self.matter,now=datetime(2026,11,3))
    def test_no_network(self):
        import socket
        old=socket.socket.connect
        def stop(*args,**kwargs):raise AssertionError('Network attempted')
        socket.socket.connect=stop
        try:self.queue.summarize(self.writer,self.matter)
        finally:socket.socket.connect=old

if __name__=='__main__':unittest.main()
