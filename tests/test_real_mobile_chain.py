"""Actual SecureCore -> ResearchEvidence -> AuthorityReview -> MatterBrief ->
MobileMatterView -> MobilePreviewGateway, with fictional data only.
No fake credential, authorization, renderer or briefing providers.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.secure_engine import SecureCore, Denied
from src.research_evidence import ResearchEvidence, EvidenceInvalid
from src.authority_review import AuthorityReview
from src.matter_brief import MatterBrief
from src.mobile_matter_view import render_mobile_brief
from src.mobile_preview_gateway import MobilePreviewGateway, PreviewRejected


class RealAuthenticatedMobileChain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name) / 'fictional.sqlite3')
        firm = self.core.provision_firm('Invented Law Firm')
        self.owner_id, self.token = self.core.provision_user(firm, 'Fictional Attorney')
        self.viewer_id, self.viewer_token = self.core.provision_user(firm, 'Imagined Paralegal')
        other = self.core.provision_firm('Other Invented Firm')
        _, self.outsider = self.core.provision_user(other, 'Outside Lawyer')
        self.mid = self.core.create_matter(self.token, 'Imaginary hearing')['id']
        self.core.grant(self.token, self.mid, self.viewer_id, 'viewer', 1)
        self.research = ResearchEvidence(self.core)
        self.reviews = AuthorityReview(self.core)
        self.gateway = MobilePreviewGateway(self.core)
        self.instant = datetime(2026, 11, 3, 16, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.core.close()
        self.tmp.cleanup()

    def source(self, title='Imaginary authority'):
        return self.research.add(
            self.token, self.mid, title,
            'https://example.org/fictional-authority',
            'Invented excerpt. Not actual legal authority.')['id']

    def render(self, token=None, matter_id=None):
        return self.gateway.prepare(token or self.token, matter_id or self.mid, now=self.instant)

    def test_complete_owner_auth_to_html(self):
        self.core.add_note(self.token, self.mid, 'Invented note for fictional client')
        past = (self.instant - timedelta(days=1)).isoformat()
        self.core.create_task(self.token, self.mid, 'Review the imagined case', past)
        eid = self.source()
        self.reviews.record(self.token, self.mid, eid, 'needs_recheck',
                            'Manual fictional review marked the source stale.')
        resp = self.render()
        headers = dict(resp.headers)
        self.assertEqual(200, resp.status)
        self.assertEqual(str(len(resp.body)), headers['Content-Length'])
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual('DENY', headers['X-Frame-Options'])
        html = resp.body.decode('utf-8')
        self.assertIn('Imaginary hearing', html)
        self.assertIn('Review the imagined case', html)
        self.assertIn('needs_recheck', html)
        self.assertIn('Past user-entered date', html)
        self.assertIn('Not actual legal authority', self.research.list(self.token, self.mid)['sources'][0]['excerpt'])
        self.assertNotIn(self.token, html)
        self.assertNotIn('<script', html)
        self.assertNotIn('<a href', html)

    def test_viewer_authorized_but_cannot_review(self):
        eid = self.source()
        self.assertEqual(200, self.render(self.viewer_token).status)
        with self.assertRaises(Denied):
            self.reviews.record(self.viewer_token, self.mid, eid, 'rejected',
                                'Viewer is not authorized to record this assessment.')

    def test_cross_firm_denied_before_rendering(self):
        with patch('src.mobile_preview_gateway.render_mobile_brief', side_effect=AssertionError('should not call renderer')):
            with self.assertRaises(Denied):
                self.render(self.outsider)

    def test_ungranted_same_firm_denied(self):
        firm = self.core._identity(self.token)['firm_id']
        _, unknown = self.core.provision_user(firm, 'Unassigned Fictional Lawyer')
        with self.assertRaises(Denied):
            self.render(unknown)

    def test_revoked_credential_denied(self):
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):
            self.render()

    def test_expired_credential_denied(self):
        import hashlib
        digest = hashlib.sha256(self.token.encode()).hexdigest()
        self.core.db.execute('UPDATE credentials SET expires_at=? WHERE token_digest=?',
                             ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),digest))
        with self.assertRaises(Denied):
            self.render()

    def test_idle_credential_denied(self):
        import hashlib
        digest = hashlib.sha256(self.token.encode()).hexdigest()
        self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
                             ((datetime.now(timezone.utc)-timedelta(seconds=301)).isoformat(),digest))
        with self.assertRaises(Denied):
            self.render()

    def test_tampered_evidence_fails_closed(self):
        eid = self.source()
        self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?',('changed illegally',eid))
        with self.assertRaises(EvidenceInvalid):
            self.render()

    def test_tampered_review_digest_fails_closed(self):
        eid = self.source()
        self.reviews.record(self.token,self.mid,eid,'checked_against_original',
                            'Fictional manual assessment was completed.')
        self.core.db.execute('UPDATE authority_review_events SET evidence_digest=? WHERE evidence_id=?',
                             ('altered',eid))
        with self.assertRaises(EvidenceInvalid):
            self.render()

    def test_unreviewed_source_is_not_verified(self):
        self.source()
        html = self.render().body.decode()
        self.assertIn('not_reviewed',html)
        self.assertIn('No automatic court-deadline or authority verification',html)

    def test_injection_payload_remains_text(self):
        self.core.add_note(self.token,self.mid,'<img src=x onerror=alert(1)>')
        html = self.render().body.decode()
        self.assertIn('&lt;img',html)
        self.assertNotIn('<img',html)

    def test_no_network_provider_calls(self):
        import socket
        with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
            response = self.render()
            self.assertEqual(200,response.status)

    def test_no_new_business_audit_event_for_read(self):
        before=self.core.audit_head()['seq']
        self.render()
        self.assertEqual(before,self.core.audit_head()['seq'])

    def test_second_matter_denied_without_grant(self):
        other_firm=self.core.provision_firm('Another Imaginary Office')
        _,other_token=self.core.provision_user(other_firm,'Fictional Owner')
        other_mid=self.core.create_matter(other_token,'Unrelated imaginary matter')['id']
        with self.assertRaises(Denied):
            self.render(self.token,other_mid)

    def test_export_size_limit_rejects_without_partial_html(self):
        # Fails before returning a partial HTML preview.
        for i in range(101):
            self.core.add_note(self.token,self.mid,f'Invented note {i}')
        with self.assertRaises(EvidenceInvalid):
            self.render()

    def test_whole_chain_restart_persists_human_review(self):
        eid=self.source()
        self.reviews.record(self.token,self.mid,eid,'needs_recheck',
                            'Fictional reviewer requested a fresh check.')
        self.core.close()
        self.core = SecureCore(Path(self.tmp.name)/'fictional.sqlite3')
        ResearchEvidence(self.core)
        AuthorityReview(self.core)
        self.gateway=MobilePreviewGateway(self.core)
        html=self.render().body.decode()
        self.assertIn('needs_recheck',html)


if __name__ == '__main__':
    unittest.main()
