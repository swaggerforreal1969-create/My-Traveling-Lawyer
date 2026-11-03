"""SQLite cross-process review acceptance with real SecureCore and fictional data."""
import multiprocessing as mp
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.source_observation import SourceObservation
from src.second_source_review import SecondSourceReview


def _review_worker(path, token, matter, evidence, observation, start, ready, outcome):
    core = SecureCore(path)
    review = SecondSourceReview(core)
    ready.put(True)
    try:
        if not start.wait(15):
            outcome.put('timeout')
            return
        try:
            review.record(token, matter, evidence, observation,
                          'corroborated_manually',
                          'Fictional manual review from separate process')
            outcome.put('committed')
        except (EvidenceInvalid, Denied):
            outcome.put('denied')
        except Exception as exc:
            outcome.put('unexpected:' + type(exc).__name__)
    finally:
        core.close()


def _crash_review_worker(path, token, matter, evidence, observation, phase):
    """Test-only child intentionally exits without an acknowledgment."""
    core = SecureCore(path)
    review = SecondSourceReview(core)
    if phase == 'precommit':
        def crash_before_audit(actor, action, target):
            if action == 'research.second_source_review':
                os._exit(37)
            return original_audit(actor, action, target)
        original_audit = core._audit
        core._audit = crash_before_audit
    review.record(token, matter, evidence, observation,
                  'corroborated_manually',
                  'Fictional second human review with process crash')
    if phase == 'postcommit':
        os._exit(38)
    os._exit(39)


class CrossProcessReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fictional.sqlite3'
        self.core = SecureCore(self.path)
        firm = self.core.provision_firm('Fictional Law Practice')
        self.author_id, self.author = self.core.provision_user(firm, 'Fictional Author')
        self.r1id, self.r1 = self.core.provision_user(firm, 'Reviewer 1')
        self.r2id, self.r2 = self.core.provision_user(firm, 'Reviewer 2')
        self.mid = self.core.create_matter(self.author, 'PRIVATE FICTIONAL MATTER')['id']
        self.core.grant(self.author, self.mid, self.r1id, 'editor', 1)
        self.core.grant(self.author, self.mid, self.r2id, 'editor', 2)
        self.eid = ResearchEvidence(self.core).add(self.author, self.mid, 'Fictional Authority',
            'https://example.org/fake', 'Imaginary legal quotation')['id']
        self.obs = SourceObservation(self.core)
        self.oid = self.observe('Fictional observed text')
        self.reviews = SecondSourceReview(self.core)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def observe(self, text):
        return self.obs.capture(self.author, self.mid, self.eid, text,
            'Manually observed fictional reference')['observation_id']

    def count(self):
        return self.core.db.execute(
            'SELECT count(*) FROM source_second_review').fetchone()[0]

    def audit_count(self):
        return self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='research.second_source_review'"
        ).fetchone()[0]

    def launch(self, tokens, before_release=None):
        ctx = mp.get_context('spawn')
        gate, ready, outcome = ctx.Event(), ctx.Queue(), ctx.Queue()
        workers = [ctx.Process(target=_review_worker, args=(
            str(self.path), token, self.mid, self.eid, self.oid,
            gate, ready, outcome)) for token in tokens]
        for worker in workers:
            worker.start()
        try:
            for _ in workers:
                self.assertTrue(ready.get(timeout=20))
            if before_release is not None:
                before_release()
            gate.set()
            results = [outcome.get(timeout=25) for _ in workers]
            for worker in workers:
                worker.join(timeout=10)
                self.assertEqual(worker.exitcode, 0)
            return results
        finally:
            gate.set()
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=10)
            ready.close()
            outcome.close()

    def test_independent_processes_exactly_one_review_and_audit(self):
        result = self.launch((self.r1, self.r2))
        self.assertCountEqual(result, ['committed', 'denied'])
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.audit_count(), 1)
        self.assertTrue(self.core.verify_audit())
        self.assertEqual(self.reviews.history(
            self.author, self.mid, self.eid)['second_reviews'][0]['observation_id'], self.oid)

    def test_revocation_while_process_waits_denies_review(self):
        result = self.launch((self.r1,), before_release=lambda: self.core.revoke_token(self.r1))
        self.assertEqual(result, ['denied'])
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.audit_count(), 0)

    def test_superseding_observation_while_process_waits_denies_stale(self):
        result = self.launch((self.r1,), before_release=lambda: self.observe('Newer fake source'))
        self.assertEqual(result, ['denied'])
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.audit_count(), 0)

    def test_audit_failure_rolls_back_review_insert(self):
        with patch.object(self.core, '_audit', side_effect=RuntimeError('Injected audit failure')):
            with self.assertRaises(RuntimeError):
                self.reviews.record(self.r1, self.mid, self.eid, self.oid,
                    'corroborated_manually','Fictional reviewer with failed audit')
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.core.verify_audit())
        self.reviews.record(self.r1, self.mid, self.eid, self.oid,
            'corroborated_manually','Fictional retry after known aborted transaction')
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.audit_count(), 1)


    def run_crash(self, phase, expected_exit):
        ctx = mp.get_context('spawn')
        worker = ctx.Process(target=_crash_review_worker, args=(
            str(self.path), self.r1, self.mid, self.eid, self.oid, phase))
        worker.start()
        try:
            worker.join(timeout=20)
            self.assertFalse(worker.is_alive(), 'Review child timed out')
            self.assertEqual(worker.exitcode, expected_exit)
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)

    def test_sigexit_before_audit_rolls_back_insert_and_allows_review(self):
        self.run_crash('precommit', 37)
        self.assertEqual(self.count(), 0)
        self.assertEqual(self.audit_count(), 0)
        self.assertTrue(self.core.verify_audit())
        self.reviews.record(self.r2, self.mid, self.eid, self.oid,
            'corroborated_manually', 'Fictional review after confirmed rollback')
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.audit_count(), 1)
        self.assertTrue(self.core.verify_audit())

    def test_lost_ack_after_commit_persists_single_review_and_audit(self):
        self.run_crash('postcommit', 38)
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.audit_count(), 1)
        self.assertTrue(self.core.verify_audit())
        # Read-only reconciliation after acknowledgment loss: no write replay.
        from src.research_write_recovery import reconcile_research_write
        row = self.core.db.execute(
            'SELECT id FROM source_second_review WHERE matter_id=?',
            (self.mid,)).fetchone()
        observed = reconcile_research_write(
            self.core, self.r1, self.mid, 'source.second_review', row['id'])
        self.assertEqual(observed.status, 'observed_local_commit')
        self.assertFalse(observed.independent_audit_verified)
        with self.assertRaises(EvidenceInvalid):
            self.reviews.record(self.r2, self.mid, self.eid, self.oid,
                'corroborated_manually', 'Duplicate after uncertain acknowledgment')
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.audit_count(), 1)



if __name__ == '__main__':
    unittest.main()
