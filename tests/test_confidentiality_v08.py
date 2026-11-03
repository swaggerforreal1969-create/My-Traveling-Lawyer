import unittest
from unittest.mock import patch
from src.assistant_service import AssistantService, AssistantInvalid, AssistantUnavailable
class ConfidentialityTests(unittest.TestCase):
    def setUp(self): self.s=AssistantService('https://example.com/v1/chat/completions','fake','fake');self.s.allowed_host='example.com'
    def test_default_is_confidential(self):
        with patch('src.assistant_service.build_opener',side_effect=AssertionError('must not transmit')):
            result=self.s.respond('privileged fictional note')
            self.assertTrue(result['confidential_mode'])
    def test_never_transmit_confidential_even_with_consent(self):
        with patch('src.assistant_service.build_opener',side_effect=AssertionError('must not transmit')):
            with self.assertRaises(AssistantInvalid): self.s.respond('privileged fictional note',external_consent=True)
    def test_explicit_confidential_prohibits_outbound(self):
        with self.assertRaises(AssistantInvalid): self.s.respond('private',external_consent=True,sensitivity='confidential')
    def test_unknown_classification_rejected(self):
        with self.assertRaises(AssistantInvalid): self.s.respond('fictional',sensitivity='unknown')
    def test_synthetic_without_consent_stays_local(self):
        with patch('src.assistant_service.build_opener',side_effect=AssertionError('must not transmit')):
            self.assertEqual(self.s.respond('fictional',sensitivity='synthetic_public')['mode'],'offline')
    def test_explicit_public_and_consent_reaches_provider_boundary(self):
        with patch('src.assistant_service.build_opener') as mocked:
            mocked.return_value.open.side_effect=TimeoutError
            with self.assertRaises(AssistantUnavailable):self.s.respond('fictional',external_consent=True,sensitivity='synthetic_public',template_id='hearing_checklist')
            self.assertTrue(mocked.return_value.open.called)

from tests.test_secure_http import APIIntegrationTests
class ConfidentialityAPITests(unittest.TestCase):
    setUp=APIIntegrationTests.setUp
    tearDown=APIIntegrationTests.tearDown
    call=APIIntegrationTests.call
    def test_confidential_external_request_denied(self):
        code, data, _=self.call('POST','/api/assistant/ask',self.ot,{'question':'privileged fictional scenario','external_consent':True})
        self.assertEqual(code,400)
        self.assertIn('Confidential Mode',data['error'])
    def test_public_without_config_returns_unavailable(self):
        code, data, _=self.call('POST','/api/assistant/ask',self.ot,{'question':'fictional scenario','external_consent':True,'sensitivity':'synthetic_public','template_id':'hearing_checklist'})
        self.assertEqual(code,503)
    def test_permissions_policy_header(self):
        _,_,headers=self.call('GET','/api/me',self.ot)
        self.assertIn('microphone=()',headers['Permissions-Policy'])
        self.assertEqual('no-store',headers['Cache-Control'])
