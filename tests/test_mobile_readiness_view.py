"""Real authorization, real matter/source integrity, fictional data only."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import tempfile
import unittest
from html.parser import HTMLParser
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.source_observation import SourceObservation
from src.second_source_review import SecondSourceReview
from src.mobile_readiness_view import MobileReadinessView, PreviewRejected


class Tags(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags=[]
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class MobileReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.core=SecureCore(Path(self.temp.name)/'demo.sqlite3')
        firm=self.core.provision_firm('Fictional Attorneys')
        self.owner_id,self.owner=self.core.provision_user(firm,'Invented Owner')
        self.reviewer_id,self.reviewer=self.core.provision_user(firm,'Invented Reviewer')
        self.viewer_id,self.viewer=self.core.provision_user(firm,'Invented Reader')
        other=self.core.provision_firm('Outside Fictional Firm')
        _,self.outsider=self.core.provision_user(other,'Outside')
        self.matter=self.core.create_matter(self.owner,'TOP SECRET TEST MATTER')['id']
        self.core.grant(self.owner,self.matter,self.reviewer_id,'editor',1)
        self.core.grant(self.owner,self.matter,self.viewer_id,'viewer',2)
        self.evidence=ResearchEvidence(self.core)
        self.observations=SourceObservation(self.core)
        self.reviews=SecondSourceReview(self.core)
        self.view=MobileReadinessView(self.core)
    def tearDown(self):
        self.core.close();self.temp.cleanup()
    def source(self):
        return self.evidence.add(self.owner,self.matter,'PRIVATE LEGAL TITLE','https://example.org/private','PRIVATE EXCERPT')['id']
    def observe(self,eid):
        return self.observations.capture(self.owner,self.matter,eid,'PRIVATE OBSERVATION CONTENT','Mock review note only')['observation_id']
    def test_empty_readiness_renders_mobile_html(self):
        result=self.view.prepare(self.owner,self.matter)
        self.assertEqual(200,result.status)
        self.assertIn(b'Open tasks',result.body)
        self.assertEqual(str(len(result.body)),dict(result.headers)['Content-Length'])
        self.assertIn('no-store',dict(result.headers)['Cache-Control'])
    def test_private_fields_absent(self):
        self.source();self.core.add_note(self.owner,self.matter,'PRIVATE NOTE')
        output=self.view.prepare(self.viewer,self.matter).body.decode()
        for secret in ('TOP SECRET TEST MATTER','PRIVATE LEGAL TITLE','PRIVATE EXCERPT','PRIVATE NOTE','https://example.org/private',self.owner):
            self.assertNotIn(secret,output)
    def test_overdue_user_date_explicitly_not_court_deadline(self):
        past=(datetime.now(timezone.utc)-timedelta(days=3)).isoformat()
        self.core.create_task(self.owner,self.matter,'PRIVATE TASK',past)
        output=self.view.prepare(self.owner,self.matter).body.decode()
        self.assertIn('NOT court deadlines',output)
        self.assertNotIn('PRIVATE TASK',output)
        self.assertIn('>1</strong>',output)
    def test_two_person_review_never_court_approval(self):
        eid=self.source();oid=self.observe(eid)
        self.reviews.record(self.reviewer,self.matter,eid,oid,'corroborated_manually','Manual review only, no legal conclusion')
        html=self.view.prepare(self.owner,self.matter).body.decode()
        self.assertIn('Two people reviewed',html)
        self.assertIn('Not legal advice',html)
    def test_newer_observation_reopens_review(self):
        eid=self.source();oid=self.observe(eid)
        self.reviews.record(self.reviewer,self.matter,eid,oid,'corroborated_manually','Manual review only, no legal conclusion')
        self.observe(eid)
        self.assertIn('Sources needing further procedural work</span><strong>1', self.view.prepare(self.owner,self.matter).body.decode())
    def test_viewer_can_read_but_not_approve(self):
        self.assertEqual(200,self.view.prepare(self.viewer,self.matter).status)
        eid=self.source();oid=self.observe(eid)
        with self.assertRaises(Denied):self.reviews.record(self.viewer,self.matter,eid,oid,'rejected','Fictional rejection review')
    def test_outside_firm_denied(self):
        with self.assertRaises(Denied):self.view.prepare(self.outsider,self.matter)
    def test_revoked_token_denied(self):
        self.core.revoke_token(self.owner)
        with self.assertRaises(Denied):self.view.prepare(self.owner,self.matter)
    def test_tampered_evidence_denied(self):
        eid=self.source();self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',('altered',eid))
        with self.assertRaises(EvidenceInvalid):self.view.prepare(self.owner,self.matter)
    def test_tampered_second_review_denied(self):
        eid=self.source();oid=self.observe(eid)
        self.reviews.record(self.reviewer,self.matter,eid,oid,'corroborated_manually','Manual review only, no legal conclusion')
        self.core.db.execute('UPDATE source_second_review SET decision=?',('rejected',))
        with self.assertRaises(EvidenceInvalid):self.view.prepare(self.owner,self.matter)
    def test_untrusted_id_denied(self):
        with self.assertRaises(PreviewRejected):self.view.prepare(self.owner,'')
    def test_bad_time_denied(self):
        with self.assertRaises(PreviewRejected):self.view.prepare(self.owner,self.matter,now=datetime(2026,11,3))
    def test_no_network(self):
        old=socket.socket.connect
        def deny(*args,**kwargs):raise AssertionError('network attempted')
        socket.socket.connect=deny
        try:self.view.prepare(self.owner,self.matter)
        finally:socket.socket.connect=old
    def test_no_script_or_links(self):
        p=Tags();p.feed(self.view.prepare(self.owner,self.matter).body.decode())
        self.assertFalse({'script','a','form','img'} & {tag for tag,_ in p.tags})
        self.assertIn("connect-src 'none'",dict(self.view.prepare(self.owner,self.matter).headers)['Content-Security-Policy'])
    def test_business_audit_not_appended(self):
        before=self.core.audit_head()['seq'];self.view.prepare(self.owner,self.matter)
        self.assertEqual(before,self.core.audit_head()['seq'])
    def test_disclosure_collapsed_by_default(self):
        p=Tags();p.feed(self.view.prepare(self.owner,self.matter).body.decode())
        details=[attrs for tag,attrs in p.tags if tag=='details']
        self.assertEqual(1,len(details));self.assertNotIn('open',details[0])

if __name__=='__main__':unittest.main()
