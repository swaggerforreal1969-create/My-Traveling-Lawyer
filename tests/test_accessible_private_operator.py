"""Accessible script-free operator summary against real local fictional SecureCore."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.secure_engine import SecureCore, Denied
from src.private_attorney_operator import PrivateAttorneyOperator
from src.private_operator_document import render_private_operator, UnsafeOperatorDocument


class AccessibleOperatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Fictional Firm')
        self.owner_id, self.owner = self.core.provision_user(firm, 'Fictional Owner')
        self.editor_id, self.editor = self.core.provision_user(firm, 'Fictional Reviewer')
        self.viewer_id, self.viewer = self.core.provision_user(firm, 'Fictional Reader')
        other = self.core.provision_firm('Other Fictional Firm')
        _, self.outsider = self.core.provision_user(other, 'Outsider')
        self.mid = self.core.create_matter(self.owner, 'PRIVATE CLIENT CASE')['id']
        self.core.grant(self.owner, self.mid, self.editor_id, 'editor', 1)
        self.core.grant(self.owner, self.mid, self.viewer_id, 'viewer', 2)
        self.core.create_task(self.owner, self.mid, 'SECRET TASK TEXT',
                              '2026-10-01T00:00:00Z')
        self.operator = PrivateAttorneyOperator(self.core)
        self.eid = self.operator.workflow.evidence.add(
            self.owner, self.mid, 'SECRET RESEARCH TITLE',
            'https://example.org/fictional', 'SECRET RESEARCH EXCERPT')['id']
        self.oid = self.operator.workflow.observations.capture(
            self.owner, self.mid, self.eid, 'SECRET OBSERVATION',
            'Manual observation from fictional source')['observation_id']

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def test_accessible_real_editor_summary_and_content_security(self):
        doc = self.operator.open_accessible_summary(self.editor, self.mid)
        html = doc.html.decode('utf-8')
        self.assertIn('<main id="content">', html)
        self.assertIn('<h1>Private attorney work summary</h1>', html)
        self.assertIn('aria-labelledby="task-heading"', html)
        self.assertIn('role="status"', html)
        self.assertIn('Review work awaiting a second human', html)
        self.assertIn('1</strong> open tasks', html)
        self.assertIn('No court filing is approved', html)
        self.assertNotIn('<script', html)
        self.assertNotIn('<form', html)
        for secret in ('SECRET TASK TEXT', 'PRIVATE CLIENT CASE', 'SECRET RESEARCH TITLE',
                       'SECRET RESEARCH EXCERPT', 'SECRET OBSERVATION',
                       self.mid, self.eid, self.oid, self.editor):
            self.assertNotIn(secret, html)
        headers = dict(doc.headers)
        self.assertIn("script-src 'none'", headers['Content-Security-Policy'])
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual(int(headers['Content-Length']), len(doc.html))

    def test_viewer_read_only_with_no_reviewer_queue(self):
        html = self.operator.open_accessible_summary(self.viewer, self.mid).html
        self.assertIn(b'Review work unavailable to reader', html)
        self.assertNotIn(b'Review work awaiting a second human', html)

    def test_revocation_and_cross_firm_deny_before_rendering(self):
        with self.assertRaises(Denied):
            self.operator.open_accessible_summary(self.outsider, self.mid)
        self.core.revoke_token(self.editor)
        with self.assertRaises(Denied):
            self.operator.open_accessible_summary(self.editor, self.mid)

    def test_forged_flags_count_and_role_fail_closed(self):
        real = self.operator.select_matter(self.editor, self.mid)
        forged = (
            replace(real, court_filing_approved=True),
            replace(real, official_law_verified=True),
            replace(real, external_ai_transmission=True),
            replace(real, open_task_count=-1),
            replace(real, open_task_count=True),
            replace(real, pending_second_review_count=101),
            replace(real, can_complete_tasks=False),
            replace(real, schema='untrusted.operator.v2'),
        )
        for value in forged:
            with self.subTest(value=value):
                with self.assertRaises(UnsafeOperatorDocument):
                    render_private_operator(value)

    def test_review_changes_counts_without_persisting_page(self):
        initial = self.operator.open_accessible_summary(self.editor, self.mid).html
        self.assertIn(b'awaiting a second human: <strong>1</strong>', initial)
        self.operator.decide_review(self.editor, self.mid, self.eid, self.oid,
            'corroborated_manually', 'Second human reviewed invented evidence')
        after = self.operator.open_accessible_summary(self.editor, self.mid).html
        self.assertIn(b'awaiting a second human: <strong>0</strong>', after)
        self.assertNotEqual(initial, after)


if __name__ == '__main__':
    unittest.main()
