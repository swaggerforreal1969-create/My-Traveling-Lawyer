import unittest
from unittest.mock import patch
from io import BytesIO
from src.assistant_service import AssistantService, AssistantUnavailable, AssistantInvalid
from tests.test_secure_http import APIIntegrationTests

class LocalAssistantTests(unittest.TestCase):
    def setUp(self): self.service=AssistantService(endpoint='',api_key='',model='')
    def test_offline_no_external_transmission(self):
        with patch('src.assistant_service.build_opener',side_effect=AssertionError('network called')):
            x=self.service.respond('Organize a fictional hearing')
        self.assertEqual(x['mode'],'offline');self.assertFalse(x['can_take_actions'])
    def test_consent_without_provider_fails_closed(self):
        with self.assertRaises(AssistantUnavailable):self.service.respond('Draft outline',external_consent=True,sensitivity='synthetic_public',template_id='hearing_checklist')
    def test_invalid_question(self):
        for q in ('', ' '*2,'z'*1201,None,{},17):
            with self.assertRaises(AssistantInvalid):self.service.respond(q)
    def test_reject_local_provider(self):
        for url in ('http://example.com','https://localhost/v1/chat/completions','https://127.0.0.1/api', 'https://user:pass@example.com/api','https://example.com:8443/api'):
            x=AssistantService(url,'fake-key','fake-model')
            with self.assertRaises(AssistantUnavailable):x.respond('Test',external_consent=True,sensitivity='synthetic_public',template_id='hearing_checklist')
    def test_provider_failure_does_not_fake_result(self):
        x=AssistantService('https://example.com/v1/chat/completions','fake','fake');x.allowed_host='example.com'
        with patch('src.assistant_service.build_opener') as opener:
            opener.return_value.open.side_effect=TimeoutError
            with self.assertRaises(AssistantUnavailable):x.respond('Question',external_consent=True,sensitivity='synthetic_public',template_id='hearing_checklist')
    def test_provider_no_automatic_case_data(self):
        class Response:
            status=200
            headers={}
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,size):return b'{"choices":[{"message":{"content":"Example checklist"}}]}'
        x=AssistantService('https://example.com/v1/chat/completions','fake','fake');x.allowed_host='example.com'
        with patch('src.assistant_service.build_opener') as opener:
            opener.return_value.open.return_value=Response()
            result=x.respond('Outline a fictional hearing',external_consent=True,sensitivity='synthetic_public',template_id='hearing_checklist')
        body=opener.return_value.open.call_args.args[0].data.decode()
        self.assertIn('generic fictional hearing preparation checklist',body)
        self.assertNotIn('Outline a fictional hearing',body)
        self.assertNotIn('matter_id',body)
        self.assertEqual(result['mode'],'remote_unverified')
        self.assertFalse(result['verified_legal_sources'])

class AssistantAPITests(unittest.TestCase):
    setUp=APIIntegrationTests.setUp
    tearDown=APIIntegrationTests.tearDown
    call=APIIntegrationTests.call
    matter=APIIntegrationTests.matter
    def test_authentication_required(self):
        self.assertEqual(403,self.call('GET','/api/assistant/status')[0])
        self.assertEqual(403,self.call('POST','/api/assistant/ask',body={'question':'Test'})[0])
    def test_local_assistant_authenticated(self):
        status,data,_=self.call('POST','/api/assistant/ask',self.ot,{'question':'Fictional question'})
        self.assertEqual(status,200);self.assertEqual(data['mode'],'offline')
        self.assertFalse(data['verified_legal_sources'])
    def test_remote_unconfigured_returns_503(self):
        status,data,_=self.call('POST','/api/assistant/ask',self.ot,{'question':'Fictional question','external_consent':True,'sensitivity':'synthetic_public','template_id':'hearing_checklist'})
        self.assertEqual(status,503);self.assertIn('unavailable',data['error'])
    def test_invalid_payload(self):
        self.assertEqual(400,self.call('POST','/api/assistant/ask',self.ot,{'question':'q','external_consent':'true'})[0])
        self.assertEqual(400,self.call('POST','/api/assistant/ask',self.ot,{'question':'x'*2000})[0])
    def test_revoked_cannot_use_assistant(self):
        self.call('POST','/api/logout',self.ot,{})
        self.assertEqual(403,self.call('POST','/api/assistant/ask',self.ot,{'question':'Question'})[0])
    def test_cross_firm_response_does_not_expose_matters(self):
        self.matter()
        status,data,_=self.call('POST','/api/assistant/ask',self.bt,{'question':'Help me plan'})
        self.assertEqual(status,200)
        self.assertNotIn('Fictional',data['answer'])

if __name__=='__main__':unittest.main()
