"""Fictional-only consent and egress-boundary tests, no network calls."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from src.secure_engine import SecureCore, Denied
from src.ai_outbound_boundary import ConfidentialAIRequest, OutboundDenied


class AIOutboundTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'fictional.sqlite'
        self.core = SecureCore(self.path)
        firm = self.core.provision_firm('Fictional Law Office')
        self.user, self.token = self.core.provision_user(firm, 'Example Attorney')
        self.viewer, self.viewer_token = self.core.provision_user(firm, 'Example Viewer')
        other_firm = self.core.provision_firm('Other Fictional Office')
        _, self.outsider = self.core.provision_user(other_firm, 'Other Person')
        self.matter = self.core.create_matter(self.token, 'Secret fictitious matter')['id']
        self.second = self.core.create_matter(self.token, 'Another fictitious matter')['id']
        self.core.grant(self.token, self.matter, self.viewer, 'viewer', 1)
        self.boundary = ConfidentialAIRequest(self.core)
    def tearDown(self):
        self.core.close(); self.tmp.cleanup()
    def grant(self, template='fictional_agenda'):
        return self.boundary.authorize(self.token, self.matter, template, explicit_opt_in=True)['grant']
    def test_explicit_opt_in_required(self):
        with self.assertRaises(OutboundDenied): self.boundary.authorize(self.token,self.matter,'fictional_agenda')
    def test_only_literal_true_opt_in(self):
        with self.assertRaises(OutboundDenied): self.boundary.authorize(self.token,self.matter,'fictional_agenda',explicit_opt_in=1)
    def test_only_known_templates(self):
        with self.assertRaises(OutboundDenied): self.boundary.authorize(self.token,self.matter,'private_client_summary',explicit_opt_in=True)
    def test_packet_contains_no_matter_fields_or_inputs(self):
        grant=self.grant(); response=self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)
        self.assertNotIn(self.matter,str(response)); self.assertNotIn('Secret fictitious matter',str(response))
        self.assertNotIn(self.token,str(response)); self.assertNotIn(grant,str(response))
        self.assertFalse(response['network_sent']); self.assertFalse(response['contains_matter_data'])
    def test_replay_denied(self):
        grant=self.grant(); self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)
        with self.assertRaises(OutboundDenied): self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)
    def test_wrong_template_denied_without_consumption(self):
        grant=self.grant()
        with self.assertRaises(OutboundDenied): self.boundary.prepare(self.token,self.matter,'fictional_intake',grant)
        self.assertTrue(self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)['fictional_only'])
    def test_wrong_matter_denied(self):
        grant=self.grant()
        with self.assertRaises(OutboundDenied): self.boundary.prepare(self.token,self.second,'fictional_agenda',grant)
    def test_wrong_credential_denied(self):
        grant=self.grant()
        with self.assertRaises(Denied): self.boundary.prepare(self.outsider,self.matter,'fictional_agenda',grant)
    def test_viewer_denied(self):
        with self.assertRaises(Denied): self.boundary.authorize(self.viewer_token,self.matter,'fictional_agenda',explicit_opt_in=True)
    def test_revoked_credential_denied(self):
        grant=self.grant(); self.core.revoke_token(self.token)
        with self.assertRaises(Denied): self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)
    def test_expired_grant_denied(self):
        grant=self.grant(); self.core.db.execute('UPDATE fictional_ai_authorizations SET expires_at=?',((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),))
        with self.assertRaises(OutboundDenied): self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)
    def test_bad_ttl_denied(self):
        for ttl in (0,121,True,-1,1.5):
            with self.subTest(ttl=ttl),self.assertRaises(OutboundDenied):
                self.boundary.authorize(self.token,self.matter,'fictional_agenda',explicit_opt_in=True,ttl_seconds=ttl)
    def test_no_plaintext_in_db(self):
        grant=self.grant(); row=self.core.db.execute('SELECT * FROM fictional_ai_authorizations').fetchone()
        self.assertNotIn(grant,repr(tuple(row)));self.assertNotIn(self.token,repr(tuple(row)))
    def test_restart_preserves_consumed_state(self):
        grant=self.grant();self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)
        self.core.close();self.core=SecureCore(self.path);self.boundary=ConfidentialAIRequest(self.core)
        with self.assertRaises(OutboundDenied):self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)
    def test_concurrent_consumption_one_wins(self):
        grant=self.grant();out=[];lock=threading.Lock()
        def attempt():
            try:self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant);status='success'
            except OutboundDenied:status='denied'
            with lock:out.append(status)
        ts=[threading.Thread(target=attempt) for _ in range(2)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertEqual(1,out.count('success'));self.assertEqual(1,out.count('denied'))
    def test_no_network_transport(self):
        with patch('socket.socket.connect', side_effect=AssertionError('network used')):
            grant=self.grant();self.boundary.prepare(self.token,self.matter,'fictional_agenda',grant)
    def test_grant_is_one_use_but_not_provider_consent(self):
        item=self.boundary.prepare(self.token,self.matter,'fictional_intake',self.grant('fictional_intake'))
        self.assertFalse(item['provider_configured']);self.assertFalse(item['legal_advice'])

if __name__=='__main__':unittest.main()
