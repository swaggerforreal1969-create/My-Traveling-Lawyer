"""Keyboard-driven local operator tests; fictional real SecureCore only."""
from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from src.secure_engine import SecureCore
from src.local_operator_cli import LocalOperatorConsole


class LocalOperatorInteractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Fictional Firm')
        self.author_id, self.author = self.core.provision_user(firm, 'Fictional Author')
        self.reviewer_id, self.reviewer = self.core.provision_user(firm, 'Fictional Reviewer')
        self.viewer_id, self.viewer = self.core.provision_user(firm, 'Fictional Reader')
        other = self.core.provision_firm('Other Fictional Firm')
        _, self.outsider = self.core.provision_user(other, 'Outsider')
        self.mid = self.core.create_matter(self.author, 'SECRET MATTER NAME')['id']
        self.core.grant(self.author, self.mid, self.reviewer_id, 'editor', 1)
        self.core.grant(self.author, self.mid, self.viewer_id, 'viewer', 2)
        self.core.create_task(self.author, self.mid, 'SECRET TASK BODY',
                              '2026-10-01T00:00:00Z')
        from src.attorney_research_workflow import AttorneyResearchWorkflow
        flow = AttorneyResearchWorkflow(self.core)
        self.eid = flow.evidence.add(self.author, self.mid, 'SECRET SOURCE',
            'https://example.org/fictional', 'SECRET EXCERPT')['id']
        self.oid = flow.observations.capture(self.author, self.mid, self.eid,
            'SECRET OBSERVATION', 'Human reviewed imaginary source')['observation_id']

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def go(self, token, answers):
        output = []
        iterator = iter(answers)
        def read(prompt):
            return next(iterator)
        console = LocalOperatorConsole(self.core, read=read, write=output.append)
        console.run(token)
        joined = '\n'.join(output)
        for secret in ('SECRET MATTER', 'SECRET TASK', 'SECRET SOURCE',
                       'SECRET EXCERPT', 'SECRET OBSERVATION',
                       self.mid, self.eid, self.oid, token):
            self.assertNotIn(secret, joined)
        return joined

    def count(self, table):
        return self.core.db.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def test_local_interactive_review_and_task_completion(self):
        # Choose matter -> review -> choose entry -> decide -> note -> consent;
        # then task -> choose -> consent -> exit.
        output = self.go(self.reviewer, [
            '1','1','1','1','Second human verified fictional record','YES',
            '2','1','YES','0'])
        self.assertIn('Review committed. Private readiness refreshed.', output)
        self.assertIn('Task completed. Private readiness refreshed.', output)
        self.assertEqual(self.count('source_second_review'), 1)
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0],1)
        self.assertTrue(self.core.verify_audit())

    def test_cancel_review_and_task_without_any_writes(self):
        result = self.go(self.reviewer, ['1','1','1','1',
            'Second human reviewed fake citation','NO','2','1','NO','0'])
        self.assertEqual(self.count('source_second_review'),0)
        self.assertEqual(self.core.db.execute(
            'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0],0)
        self.assertIn('Cancelled; no write performed.', result)

    def test_viewer_denied_write_and_revoked_denied_on_entry(self):
        output = self.go(self.viewer, ['1','2'])
        self.assertIn('Authorization or current state rejected',output)
        self.assertEqual(self.count('source_second_review'),0)
        self.core.revoke_token(self.reviewer)
        output = self.go(self.reviewer, [])
        self.assertIn('Authorization or state rejected',output)
        self.assertEqual(self.count('source_second_review'),0)

    def test_cross_firm_no_matters_no_client_leakage(self):
        output=self.go(self.outsider,[])
        self.assertIn('No authorized matters.',output)

    def test_stale_observation_between_choice_and_submission_is_denied(self):
        answers=iter(['1','1','1','1','Human checked imaginary citation','YES'])
        from src.attorney_research_workflow import AttorneyResearchWorkflow
        flow=AttorneyResearchWorkflow(self.core)
        def read(prompt):
            response=next(answers)
            if prompt.startswith('Type YES'):
                flow.observations.capture(self.author,self.mid,self.eid,
                    'Superseding fictional observation',
                    'Human updated an imagined source')
            return response
        outputs=[]
        LocalOperatorConsole(self.core,read=read,write=outputs.append).run(self.reviewer)
        self.assertEqual(self.count('source_second_review'),0)
        self.assertIn('Authorization or current state rejected', '\n'.join(outputs))

    def test_uncertain_review_refresh_has_no_automatic_replay(self):
        answers=iter(['1','1','1','1','Human checked imaginary citation','YES'])
        outputs=[]
        console=LocalOperatorConsole(self.core,write=outputs.append)
        def read(prompt):
            response=next(answers)
            if prompt.startswith('Type YES'):
                console.operator.workflow.open=lambda *args,**kw: (
                    _ for _ in ()).throw(RuntimeError('Lost local readiness refresh'))
            return response
        console.read=read
        console.run(self.reviewer)
        self.assertIn('COMMITTED, READINESS UNRESOLVED', '\\n'.join(outputs))
        self.assertEqual(self.count('source_second_review'),1)
        self.assertEqual(self.core.db.execute(
            "SELECT count(*) FROM audit_chain WHERE action='research.second_source_review'"
        ).fetchone()[0],1)

    def test_invalid_selection_fails_without_write(self):
        output=self.go(self.reviewer,['1','1','nan','0'])
        self.assertIn('Invalid selection; no action taken.',output)
        self.assertEqual(self.count('source_second_review'),0)


if __name__=='__main__':
    unittest.main()
