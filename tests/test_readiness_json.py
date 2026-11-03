"""Fictional, real SecureCore backed confidential readiness JSON acceptance."""
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.source_observation import SourceObservation
from src.second_source_review import SecondSourceReview
from src.readiness_json import ReadinessJSON
from src.mobile_preview_gateway import PreviewRejected


class JSONReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.db')
        firm = self.core.provision_firm('Imaginary Legal Office')
        self.writer_id, self.writer = self.core.provision_user(firm, 'Imaginary Lawyer')
        self.reviewer_id, self.reviewer = self.core.provision_user(firm, 'Imaginary Reviewer')
        self.matter = self.core.create_matter(self.writer, 'PRIVATE FICTIONAL CASE')['id']
        self.core.grant(self.writer, self.matter, self.reviewer_id, 'editor', 1)
        other = self.core.provision_firm('Other Fictional Firm')
        _, self.outsider = self.core.provision_user(other, 'Outside')
        self.sources = ResearchEvidence(self.core)
        self.obs = SourceObservation(self.core)
        self.second = SecondSourceReview(self.core)
        self.view = ReadinessJSON(self.core)
    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()
    def get(self, token=None):
        r = self.view.prepare(token or self.writer, self.matter)
        return json.loads(r.body), r
    def source(self):
        return self.sources.add(self.writer, self.matter, 'SECRET SOURCE TITLE',
                                'https://example.org/private', 'SECRET EXCERPT')['id']
    def observed(self, evidence):
        return self.obs.capture(self.writer, self.matter, evidence,
                 'Entirely fictional text that cannot leave the server',
                 'Manual fictional observation only')['observation_id']
    def test_01_empty_counts(self):
        data, r = self.get()
        self.assertEqual('mtl.private.readiness.counts.v1', data['schema'])
        self.assertEqual(0, data['open_tasks'])
        self.assertEqual(0, data['research_sources'])
        self.assertEqual(200, r.status)
    def test_02_source_awaits_review(self):
        self.source()
        data, _ = self.get()
        self.assertEqual(1, data['research_needing_procedural_work'])
        self.assertEqual(1, data['review_counts']['needs_first_observation'])
    def test_03_procedural_review_is_not_legal_verification(self):
        e = self.source(); o = self.observed(e)
        self.second.record(self.reviewer, self.matter, e, o, 'corroborated_manually',
                           'Fictional second account review only')
        data, _ = self.get()
        self.assertEqual(0, data['research_needing_procedural_work'])
        for key in ('legal_source_authenticated','legal_deadlines_verified',
                    'court_filing_approved','outbound_ai_transmission',
                    'human_review_is_legal_verification'):
            self.assertIs(data[key], False)
    def test_04_stale_review_reopens(self):
        e=self.source();o=self.observed(e)
        self.second.record(self.reviewer,self.matter,e,o,'corroborated_manually',
                           'Fictional second account review only')
        self.observed(e)
        self.assertEqual(1,self.get()[0]['research_needing_procedural_work'])
    def test_05_never_leak_sensitive_text_or_identifiers(self):
        self.source()
        obj,r=self.get()
        for private in ('PRIVATE FICTIONAL CASE','SECRET SOURCE TITLE',
                        'SECRET EXCERPT','https://example.org/private',self.matter,
                        self.writer,self.reviewer,'evidence_id','observation_id'):
            self.assertNotIn(private, r.body.decode())
        self.assertNotIn('matter_id',obj)
    def test_06_no_store_headers(self):
        _,r=self.get();h=dict(r.headers)
        self.assertEqual('application/json; charset=utf-8',h['Content-Type'])
        self.assertIn('no-store',h['Cache-Control'])
        self.assertEqual(str(len(r.body)),h['Content-Length'])
        self.assertIn('none',h['Content-Security-Policy'])
    def test_07_cross_firm_denied(self):
        with self.assertRaises(Denied):self.get(self.outsider)
    def test_08_revoked_denied(self):
        self.core.revoke_token(self.writer)
        with self.assertRaises(Denied):self.get()
    def test_09_tampered_research_denied(self):
        e=self.source()
        self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',('evil',e))
        with self.assertRaises(EvidenceInvalid):self.get()
    def test_10_tampered_second_review_denied(self):
        e=self.source();o=self.observed(e)
        self.second.record(self.reviewer,self.matter,e,o,'corroborated_manually',
                           'Fictional second account review only')
        self.core.db.execute('UPDATE source_second_review SET decision=?',('rejected',))
        with self.assertRaises(EvidenceInvalid):self.get()
    def test_11_invalid_datetime_denied(self):
        with self.assertRaises(PreviewRejected):
            self.view.prepare(self.writer,self.matter,now=datetime(2026,11,3))
    def test_12_invalid_credential_and_matter(self):
        with self.assertRaises(PreviewRejected):self.view.prepare('short',self.matter)
        with self.assertRaises(PreviewRejected):self.view.prepare(self.writer,'')
    def test_13_no_socket_use(self):
        import socket
        old=socket.socket.connect
        def stop(*a,**kw):raise AssertionError('Network forbidden')
        socket.socket.connect=stop
        try:self.get()
        finally:socket.socket.connect=old
    def test_14_no_business_audit_write(self):
        before=self.core.audit_head()['seq']
        self.get()
        self.assertEqual(before,self.core.audit_head()['seq'])
    def test_15_malformed_upstream_flags_rejected(self):
        original=self.view.readiness.summarize
        def altered(*a,**k):
            s=original(*a,**k);s['court_filing_approved']=True;return s
        self.view.readiness.summarize=altered
        with self.assertRaises(PreviewRejected):self.get()
    def test_16_malformed_upstream_counts_rejected(self):
        original=self.view.readiness.summarize
        def altered(*a,**k):
            s=original(*a,**k);s['research_status_counts']['needs_first_observation']=7;return s
        self.view.readiness.summarize=altered
        with self.assertRaises(PreviewRejected):self.get()

if __name__=='__main__':unittest.main()
