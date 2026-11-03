import unittest
from test_secure_http import APIIntegrationTests

class ResearchCases(APIIntegrationTests):
    def test_research_lifecycle_permissions_and_no_fake_verification(self):
        mid=self.matter()
        route='/api/matters/'+mid+'/research'
        payload={'title':'Fictional authority','url':'https://example.org/fictional','excerpt':'This is an invented excerpt for tests.'}
        self.assertEqual(403,self.call('POST',route,self.bt,payload)[0])
        self.assertEqual(403,self.call('GET',route,self.bt)[0])
        self.assertEqual(201,self.call('POST',route,self.ot,payload)[0])
        st,d,_=self.call('GET',route,self.ot)
        self.assertEqual(200,st)
        self.assertEqual(1,len(d['sources']))
        self.assertFalse(d['sources'][0]['source_verified'])
        self.assertFalse(d['sources'][0]['legal_authority_verified'])
        self.assertEqual(payload['excerpt'],d['sources'][0]['excerpt'])
    def test_no_viewer_write(self):
        mid=self.matter();route='/api/matters/'+mid+'/research'
        self.core.grant(self.ot,mid,self.viewer,'viewer',1)
        d={'title':'Fiction','url':'https://example.org/x','excerpt':'Mock'}
        self.assertEqual(403,self.call('POST',route,self.vt,d)[0])
        self.assertEqual(200,self.call('GET',route,self.vt)[0])
    def test_reject_unsafe_urls(self):
        mid=self.matter();route='/api/matters/'+mid+'/research'
        for u in ['http://example.org','https://localhost/','https://user:pw@example.org/','file:///etc/passwd','https://example.org:8443/x']:
            with self.subTest(u=u):
                self.assertEqual(400,self.call('POST',route,self.ot,{'title':'Fake','url':u,'excerpt':'Mock'})[0])
    def test_auth_required(self):
        mid=self.matter();route='/api/matters/'+mid+'/research'
        self.assertEqual(403,self.call('GET',route)[0])
        self.assertEqual(403,self.call('POST',route,body={'title':'x','url':'https://example.org','excerpt':'x'})[0])
