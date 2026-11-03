"""End-to-end offline provider-preflight acceptance with real SecureCore."""
from pathlib import Path
import hashlib
import json
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from src.secure_engine import SecureCore, Denied
from src.ai_outbound_boundary import ConfidentialAIRequest, OutboundDenied
from src.ai_provider_dry_run import OfflineProviderAdapter, ProviderPacketDenied

class OfflineProviderAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.tmp.name)/'demo.sqlite')
        firm = self.core.provision_firm('Invented Test Firm')
        _, self.token = self.core.provision_user(firm,'Invented Lawyer')
        self.mid = self.core.create_matter(self.token, 'Sensitive fictional title ABCDEF')['id']
        self.boundary = ConfidentialAIRequest(self.core)
        self.adapter = OfflineProviderAdapter()
    def tearDown(self):
        self.core.close(); self.tmp.cleanup()
    def packet(self, template='fictional_agenda'):
        grant = self.boundary.authorize(self.token,self.mid,template,explicit_opt_in=True)['grant']
        return self.boundary.prepare(self.token,self.mid,template,grant)
    def deny(self, packet, **kwargs):
        with self.assertRaises(ProviderPacketDenied):self.adapter.prepare(packet,**kwargs)
    def test_full_real_auth_to_adapter(self):
        result = self.adapter.prepare(self.packet())
        self.assertFalse(result['network_sent'])
        self.assertFalse(result['provider_configured'])
        self.assertFalse(result['contains_matter_data'])
        self.assertNotIn(self.mid,result['body'].decode())
        self.assertNotIn('ABCDEF',result['body'].decode())
        self.assertEqual(hashlib.sha256(result['body']).hexdigest(),result['body_sha256'])
    def test_both_allowlisted_templates(self):
        for name in ConfidentialAIRequest.TEMPLATES:
            with self.subTest(name=name):
                body=json.loads(self.adapter.prepare(self.packet(name))['body'])
                self.assertEqual(ConfidentialAIRequest.TEMPLATES[name], body['messages'][0]['content'])
    def test_no_user_text(self):
        self.deny(self.packet(),user_content='secret fictional client information')
    def test_no_external_endpoint(self):
        self.deny(self.packet(),endpoint='https://example.com/ai')
    def test_no_provider_credentials(self):
        self.deny(self.packet(),provider_credentials='fictional-secret')
    def test_no_network_even_if_requested(self):
        self.deny(self.packet(),network_enabled=True)
    def test_integer_true_is_not_bool_false(self):
        self.deny(self.packet(),network_enabled=0)
    def test_tampered_content(self):
        p=self.packet();p['prompt']+=' real invented client details';self.deny(p)
    def test_tampered_digest(self):
        p=self.packet();p['prompt_sha256']='0'*64;self.deny(p)
    def test_unknown_template(self):
        p=self.packet();p['template_id']='custom';self.deny(p)
    def test_added_matter_id_rejected(self):
        p=self.packet();p['matter_id']=self.mid;self.deny(p)
    def test_removed_flag_rejected(self):
        p=self.packet();del p['network_sent'];self.deny(p)
    def test_wrong_type_safety_flag_rejected(self):
        p=self.packet();p['fictional_only']=1;self.deny(p)
    def test_false_safety_flag_rejected(self):
        p=self.packet();p['contains_matter_data']=True;self.deny(p)
    def test_no_socket_usage(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('network attempted')):
            with patch.object(socket.socket,'connect_ex',side_effect=AssertionError('network attempted')):
                self.adapter.prepare(self.packet())
    def test_revoked_token_stops_preflight(self):
        self.core.revoke_token(self.token)
        with self.assertRaises(Denied):self.packet()
    def test_replayed_opt_in_fails_prior_to_provider(self):
        grant=self.boundary.authorize(self.token,self.mid,'fictional_agenda',explicit_opt_in=True)['grant']
        self.adapter.prepare(self.boundary.prepare(self.token,self.mid,'fictional_agenda',grant))
        with self.assertRaises(OutboundDenied):self.boundary.prepare(self.token,self.mid,'fictional_agenda',grant)

if __name__ == '__main__':unittest.main()
