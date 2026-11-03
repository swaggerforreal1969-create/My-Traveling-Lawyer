"""Fictional-only two-person source review adversarial integration."""
import tempfile
import unittest
from pathlib import Path
from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.source_observation import SourceObservation
from src.second_source_review import SecondSourceReview


class SecondReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'app.db'
        self.c=SecureCore(self.path)
        f=self.c.provision_firm('Imaginary Firm')
        self.writer_id,self.writer=self.c.provision_user(f,'Fictional Writer')
        self.reviewer_id,self.reviewer=self.c.provision_user(f,'Fictional Reviewer')
        self.viewer_id,self.viewer=self.c.provision_user(f,'Fictional Reader')
        outsider_f=self.c.provision_firm('Imaginary Other')
        _,self.outsider=self.c.provision_user(outsider_f,'Invented Other')
        self.m=self.c.create_matter(self.writer,'Invented case')['id']
        self.c.grant(self.writer,self.m,self.reviewer_id,'editor',1)
        self.c.grant(self.writer,self.m,self.viewer_id,'viewer',2)
        self.e=ResearchEvidence(self.c).add(self.writer,self.m,'Imaginary Opinion',
                'https://example.org/imaginary','Completely fictional law excerpt')['id']
        self.obs=SourceObservation(self.c)
        self.o=self.obs.capture(self.writer,self.m,self.e,'Invented excerpt text.',
                'Recorded only fictional source content')['observation_id']
        self.second=SecondSourceReview(self.c)
    def tearDown(self):
        self.c.close();self.tmp.cleanup()
    def review(self,**kw):
        d={'token':self.reviewer,'matter_id':self.m,'evidence_id':self.e,
           'observation_id':self.o,'decision':'corroborated_manually',
           'note':'Second person inspected the imaginary statement'}
        d.update(kw)
        return self.second.record(**d)
    def test_two_distinct_accounts_and_disclaimers(self):
        r=self.review()
        self.assertTrue(r['second_human_account']);self.assertFalse(r['official_source_authenticated'])
        self.assertFalse(r['legal_authority_current'])
    def test_self_review_denied(self):
        with self.assertRaises(EvidenceInvalid):self.review(token=self.writer)
    def test_viewer_review_denied(self):
        with self.assertRaises(Denied):self.review(token=self.viewer)
    def test_cross_firm_denied(self):
        with self.assertRaises(Denied):self.review(token=self.outsider)
    def test_revoked_denied(self):
        self.c.revoke_token(self.reviewer)
        with self.assertRaises(Denied):self.review()
    def test_double_sign_denied(self):
        self.review()
        with self.assertRaises(EvidenceInvalid):self.review()
    def test_incorrect_observation_denied(self):
        with self.assertRaises(EvidenceInvalid):self.review(observation_id='a'*32)
    def test_wrong_evidence_denied(self):
        with self.assertRaises(EvidenceInvalid):self.review(evidence_id='b'*32)
    def test_modified_source_denied(self):
        self.c.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',('tampered',self.e))
        with self.assertRaises(EvidenceInvalid):self.review()
    def test_modified_original_observation_denied(self):
        self.c.db.execute('UPDATE source_observation SET captured_text=? WHERE observation_id=?',('tampered',self.o))
        with self.assertRaises(EvidenceInvalid):self.review()
    def test_history_tamper_denied(self):
        self.review();self.c.db.execute('UPDATE source_second_review SET decision=?',('rejected',))
        with self.assertRaises(EvidenceInvalid):self.second.history(self.writer,self.m,self.e)
    def test_viewer_reads_but_cannot_write(self):
        self.review();self.assertEqual(1,len(self.second.history(self.viewer,self.m,self.e)['second_reviews']))
    def test_persists_restart(self):
        self.review();self.c.close();self.c=SecureCore(self.path)
        self.second=SecondSourceReview(self.c)
        self.assertEqual(1,len(self.second.history(self.reviewer,self.m,self.e)['second_reviews']))
    def test_bad_decision_and_note(self):
        with self.assertRaises(EvidenceInvalid):self.review(decision='officially_verified')
        with self.assertRaises(EvidenceInvalid):self.review(note='short')
    def test_read_only_history(self):
        self.review();prior=self.c.audit_head()['seq'];self.second.history(self.viewer,self.m,self.e)
        self.assertEqual(prior,self.c.audit_head()['seq'])

if __name__=='__main__':unittest.main()
