"""Actual SecureCore local reviewer inbox and concurrency acceptance. Fictional only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from src.secure_engine import SecureCore, Denied
from src.research_evidence import EvidenceInvalid
from src.attorney_research_workflow import AttorneyResearchWorkflow


class PrivateReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.core=SecureCore(Path(self.tmp.name)/'fictional.sqlite3')
        firm=self.core.provision_firm('Fictional Practice')
        self.author_id,self.author=self.core.provision_user(firm,'Fictional Author')
        self.reviewer_id,self.reviewer=self.core.provision_user(firm,'Fictional Reviewer A')
        self.reviewer2_id,self.reviewer2=self.core.provision_user(firm,'Fictional Reviewer B')
        self.viewer_id,self.viewer=self.core.provision_user(firm,'Reader')
        other=self.core.provision_firm('Outside Fictional Firm')
        _,self.outsider=self.core.provision_user(other,'Outsider')
        self.mid=self.core.create_matter(self.author,'SECRET MATTER')['id']
        self.core.grant(self.author,self.mid,self.reviewer_id,'editor',1)
        self.core.grant(self.author,self.mid,self.reviewer2_id,'editor',2)
        self.core.grant(self.author,self.mid,self.viewer_id,'viewer',3)
        self.workflow=AttorneyResearchWorkflow(self.core)
        self.eid=self.workflow.evidence.add(self.author,self.mid,'SECRET TITLE',
             'https://example.org/fictional','SECRET EXCERPT')['id']
        self.oid=self.observe('First fictional capture')

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def observe(self,text):
        return self.workflow.observations.capture(self.author,self.mid,self.eid,
            text,'Manually captured imaginary authority')['observation_id']

    def queue(self,token=None,matter=None):
        return self.workflow.pending_second_reviews(
            self.reviewer if token is None else token,
            self.mid if matter is None else matter)

    def test_only_latest_current_reviewable_and_no_secrets(self):
        queue=self.queue()
        self.assertEqual(queue['schema'],'mtl.private.review.queue.v1')
        self.assertEqual(queue['items'],[{'evidence_id':self.eid,
            'observation_id':self.oid,'status':'needs_independent_second_review'}])
        for key in ('official_source_authenticated','legal_authority_current',
                    'court_filing_approved','independent_audit_verified'):
            self.assertIs(queue[key],False)
        for private in ('SECRET TITLE','SECRET EXCERPT','SECRET MATTER',
                        'https://example.org/fictional'):
            self.assertNotIn(private,str(queue))
        self.assertEqual(self.queue(self.author)['items'],[])

    def test_new_observation_replaces_old_review_target(self):
        new=self.observe('Superseding fictional capture')
        self.assertEqual(self.queue()['items'][0]['observation_id'],new)
        with self.assertRaises(EvidenceInvalid):
            self.workflow.reviews.record(self.reviewer,self.mid,self.eid,self.oid,
                 'corroborated_manually','Old observation should not be reviewed')
        self.workflow.reviews.record(self.reviewer,self.mid,self.eid,new,
            'corroborated_manually','Second human checked latest fake source')
        self.assertEqual(self.queue()['items'],[])

    def test_two_concurrent_reviewers_only_one_write(self):
        def submit(token):
            try:
                self.workflow.reviews.record(token,self.mid,self.eid,self.oid,
                    'corroborated_manually','Independent review of imaginary source')
                return 'written'
            except EvidenceInvalid:
                return 'denied'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(submit,(self.reviewer,self.reviewer2)))
        self.assertCountEqual(outcomes,['written','denied'])
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0],1)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='research.second_source_review'"
        ).fetchone()[0],1)
        self.assertTrue(self.core.verify_audit())

    def test_viewer_cross_firm_other_matter_revocation_denied(self):
        with self.assertRaises(Denied): self.queue(self.viewer)
        with self.assertRaises(Denied): self.queue(self.outsider)
        unrelated=self.core.create_matter(self.author,'Unrelated case')['id']
        with self.assertRaises(Denied): self.queue(matter=unrelated)
        self.core.revoke_token(self.reviewer)
        with self.assertRaises(Denied): self.queue()
        with self.assertRaises(Denied):
            self.workflow.reviews.record(self.reviewer,self.mid,self.eid,self.oid,
                'corroborated_manually','Revoked reviewer cannot write')
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0],0)

    def test_corrupt_observation_and_audit_fail_closed(self):
        self.core.db.execute('UPDATE source_observation SET note=? WHERE observation_id=?',
                             ('FORGED',self.oid))
        with self.assertRaises(EvidenceInvalid): self.queue()
        self.core.db.execute('UPDATE source_observation SET note=? WHERE observation_id=?',
                             ('Manually captured imaginary authority',self.oid))
        self.core.db.execute("UPDATE audit_chain SET row_hash='FORGED' WHERE seq=1")
        with self.assertRaises(EvidenceInvalid): self.queue()

    def test_duplicate_review_not_reoffered(self):
        self.workflow.reviews.record(self.reviewer,self.mid,self.eid,self.oid,
            'needs_further_review','Second human requests more fictional review')
        self.assertEqual(self.queue(self.reviewer2)['items'],[])
        new=self.observe('Later updated source')
        self.assertEqual(self.queue(self.reviewer2)['items'][0]['observation_id'],new)


if __name__=='__main__':
    unittest.main()
