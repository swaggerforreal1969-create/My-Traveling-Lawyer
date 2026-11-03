import json
import unittest
from unittest.mock import patch
from src.assistant_service import AssistantService, AssistantInvalid
from tests.test_secure_http import APIIntegrationTests

class MinimizedProviderTests(unittest.TestCase):
    def test_external_prompt_requires_whitelisted_template(self):
        a=AssistantService('https://example.com/v1/chat/completions','key','model'); a.allowed_host='example.com'
        with patch('src.assistant_service.build_opener',side_effect=AssertionError('outbound network not allowed')):
            with self.assertRaises(AssistantInvalid):
                a.respond('privileged client notes',external_consent=True,sensitivity='synthetic_public')
    def test_external_prompt_contains_no_user_supplied_text(self):
        a=AssistantService('https://example.com/v1/chat/completions','key','model'); a.allowed_host='example.com'
        class R:
            status=200
            headers={}
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return b'{"choices":[{"message":{"content":"Generic guidance"}}]}'
        with patch('src.assistant_service.build_opener') as opener:
            opener.return_value.open.return_value=R()
            answer=a.respond('SECRET_NAME_9876',external_consent=True,sensitivity='synthetic_public',template_id='hearing_checklist')
            body=opener.return_value.open.call_args.args[0].data.decode()
        self.assertNotIn('SECRET_NAME_9876',body)
        self.assertIn('generic fictional hearing preparation checklist',body)
        self.assertEqual(answer['mode'],'remote_unverified')
    def test_confidential_still_forbidden_even_with_template(self):
        a=AssistantService('https://example.com/v1/chat/completions','key','model'); a.allowed_host='example.com'
        with self.assertRaises(AssistantInvalid):
            a.respond('private',external_consent=True,sensitivity='confidential',template_id='hearing_checklist')

class LockAPITests(unittest.TestCase):
    setUp=APIIntegrationTests.setUp
    tearDown=APIIntegrationTests.tearDown
    call=APIIntegrationTests.call
    def test_lock_revokes_credentials_server_side(self):
        code,data,_=self.call('POST','/api/lock',self.ot,{})
        self.assertEqual(code,200)
        self.assertTrue(data['reauthentication_required'])
        self.assertEqual(self.call('GET','/api/me',self.ot)[0],403)
        self.assertEqual(self.call('GET','/api/matters',self.ot)[0],403)
        self.assertEqual(self.call('POST','/api/assistant/ask',self.ot,{'question':'fictional'})[0],403)
    def test_unauthenticated_lock_denied(self):
        self.assertEqual(self.call('POST','/api/lock',body={})[0],403)
    def test_cross_firm_credential_cannot_unlock_other_firm(self):
        self.call('POST','/api/lock',self.ot,{})
        self.assertEqual(self.call('GET','/api/me',self.bt)[0],200)
        self.assertEqual(self.call('GET','/api/me',self.ot)[0],403)
    def test_external_requires_template_via_api(self):
        code,data,_=self.call('POST','/api/assistant/ask',self.ot,{'question':'SECRET','sensitivity':'synthetic_public','external_consent':True})
        self.assertEqual(code,400)
        self.assertIn('predefined',data['error'])
