import unittest, tempfile, threading, json, http.client, os
from pathlib import Path
from src.secure_engine import SecureCore
from src.secure_server import APIServer

class APIIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.path=Path(self.t.name)/'secure.db'
        self.core=SecureCore(self.path)
        self.a=self.core.provision_firm('Firm A');self.b=self.core.provision_firm('Firm B')
        self.owner,self.ot=self.core.provision_user(self.a,'Owner');self.viewer,self.vt=self.core.provision_user(self.a,'Viewer')
        self.out,self.bt=self.core.provision_user(self.b,'Outside')
        self.server=APIServer(('127.0.0.1',0),self.core)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.port=self.server.server_port
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2);self.core.close();self.t.cleanup()
    def call(self,method,path,token=None,body=None,headers=None):
        h={'Host':f'127.0.0.1:{self.port}'}
        if token is not None:h['Authorization']='Bearer '+token
        if body is not None:
            h['Content-Type']='application/json'
            body=json.dumps(body)
        if headers:h.update(headers)
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
        c.request(method,path,body=body,headers=h);r=c.getresponse();raw=r.read();status=r.status;response_headers=dict(r.getheaders());c.close()
        try:out=json.loads(raw)
        except (ValueError,UnicodeDecodeError):out=raw
        return status,out,response_headers
    def matter(self):return self.call('POST','/api/matters',self.ot,{'title':'Fictional'})[1]['id']
    def test_unauthenticated_list_denied(self):self.assertEqual(403,self.call('GET','/api/matters')[0])
    def test_unauthenticated_create_denied(self):self.assertEqual(403,self.call('POST','/api/matters',body={'title':'Evil'})[0])
    def test_unauthenticated_notes_denied(self):self.assertEqual(403,self.call('GET','/api/matters/00000000-0000-0000-0000-000000000000/notes')[0])
    def test_old_dashboard_unavailable(self):self.assertEqual(403,self.call('GET','/api/dashboard')[0])
    def test_old_entries_unavailable(self):self.assertEqual(403,self.call('POST','/api/entries',body={})[0])
    def test_forged_token(self):self.assertEqual(403,self.call('GET','/api/matters','z'*43)[0])
    def test_bad_host(self):self.assertEqual(403,self.call('GET','/api/matters',self.ot,headers={'Host':'evil.example'})[0])
    def test_cross_origin(self):self.assertEqual(403,self.call('POST','/api/matters',self.ot,{'title':'E'},headers={'Origin':'http://evil.example'})[0])
    def test_missing_content_type(self):self.assertEqual(400,self.call('POST','/api/matters',self.ot,headers={'Content-Length':'2'})[0])
    def test_create_list(self):
        mid=self.matter();s,data,_=self.call('GET','/api/matters',self.ot)
        self.assertEqual(200,s);self.assertEqual(mid,data['matters'][0]['id'])
    def test_cross_firm_hidden(self):
        self.matter();self.assertEqual([] ,self.call('GET','/api/matters',self.bt)[1]['matters'])
    def test_cross_firm_notes_forbidden(self):self.assertEqual(403,self.call('GET',f'/api/matters/{self.matter()}/notes',self.bt)[0])
    def test_colleague_without_grant_denied(self):self.assertEqual(403,self.call('GET',f'/api/matters/{self.matter()}/notes',self.vt)[0])
    def test_viewer_read_only(self):
        mid=self.matter();self.core.grant(self.ot,mid,self.viewer,'viewer',1)
        self.assertEqual(200,self.call('GET',f'/api/matters/{mid}/notes',self.vt)[0])
        self.assertEqual(403,self.call('POST',f'/api/matters/{mid}/notes',self.vt,{'text':'Bad'})[0])
    def test_owner_note(self):
        mid=self.matter();self.assertEqual(201,self.call('POST',f'/api/matters/{mid}/notes',self.ot,{'text':'Imaginary'})[0]);self.assertEqual(1,len(self.call('GET',f'/api/matters/{mid}/notes',self.ot)[1]['notes']))
    def test_stale_grant(self):
        mid=self.matter();body={'matter_id':mid,'user_id':self.viewer,'role':'viewer','expected_version':1}
        self.assertEqual(200,self.call('POST','/api/grants',self.ot,body)[0]);self.assertEqual(409,self.call('POST','/api/grants',self.ot,body)[0])
    def test_cross_firm_grant(self):
        mid=self.matter();self.assertEqual(403,self.call('POST','/api/grants',self.ot,{'matter_id':mid,'user_id':self.out,'role':'editor','expected_version':1})[0])
    def test_logout_revokes(self):
        self.assertEqual(200,self.call('POST','/api/logout',self.ot,{})[0]);self.assertEqual(403,self.call('GET','/api/matters',self.ot)[0])
    def test_bad_json_and_type(self):self.assertEqual(400,self.call('POST','/api/matters',self.ot,{'title':123})[0])
    def test_secure_headers(self):
        _,_,h=self.call('GET','/api/me',self.ot);self.assertEqual('nosniff',h['X-Content-Type-Options']);self.assertEqual('no-store',h['Cache-Control'])
    def test_reopen_revocation(self):
        self.call('POST','/api/logout',self.ot,{})
        other=SecureCore(self.path)
        try:
            with self.assertRaises(Exception):other.list_matters(self.ot)
        finally:other.close()
    def test_loopback_enforced(self):
        with self.assertRaises(ValueError):APIServer(('0.0.0.0',0),self.core)

if __name__=='__main__':unittest.main()

class CutoverTests(unittest.TestCase):
    def test_default_server_is_authenticated(self):
        import src.server as main
        import src.secure_server as secure
        self.assertIs(main.run,secure.run)
    def test_browser_app_does_not_call_legacy_api(self):
        text=(Path(__file__).resolve().parents[1]/'src'/'secure_app.js').read_text()
        for endpoint in ['/api/entries','/api/audit']:
            self.assertNotIn(endpoint,text)

class NewMilestoneTests(APIIntegrationTests):
    def test_dashboard_requires_token_and_isolated(self):
        self.assertEqual(403,self.call('GET','/api/dashboard')[0])
        mid=self.matter(); self.call('POST','/api/tasks',self.ot,{'matter_id':mid,'text':'Fictional hearing','due_at':'2030-01-05T10:00:00Z'})
        self.assertEqual(1,len(self.call('GET','/api/dashboard',self.ot)[1]['upcoming_tasks']))
        self.assertEqual(0,len(self.call('GET','/api/dashboard',self.bt)[1]['upcoming_tasks']))
        self.assertEqual(0,len(self.call('GET','/api/dashboard',self.vt)[1]['upcoming_tasks']))
    def test_rotate_revokes_old_token(self):
        status,data,_=self.call('POST','/api/rotate',self.ot,{})
        self.assertEqual(200,status)
        self.assertEqual(403,self.call('GET','/api/me',self.ot)[0])
        self.assertEqual(200,self.call('GET','/api/me',data['token'])[0])
    def test_expired_token_denied(self):
        from hashlib import sha256
        with self.core.lock,self.core.db:
            self.core.db.execute('UPDATE credentials SET expires_at=? WHERE token_digest=?',('2020-01-01T00:00:00+00:00',sha256(self.ot.encode()).hexdigest()))
        self.assertEqual(403,self.call('GET','/api/me',self.ot)[0])
        self.assertEqual(403,self.call('POST','/api/rotate',self.ot,{})[0])
    def test_task_permissions_and_bad_date(self):
        mid=self.matter(); self.core.grant(self.ot,mid,self.viewer,'viewer',1)
        payload={'matter_id':mid,'text':'Test','due_at':'2030-01-05T10:00:00Z'}
        self.assertEqual(403,self.call('POST','/api/tasks',self.vt,payload)[0])
        self.assertEqual(403,self.call('POST','/api/tasks',self.bt,payload)[0])
        self.assertEqual(400,self.call('POST','/api/tasks',self.ot,{**payload,'due_at':'2030-01-05'})[0])
    def test_audit_tampering_detected(self):
        self.matter();self.assertTrue(self.core.verify_audit())
        with self.core.lock,self.core.db:self.core.db.execute("UPDATE audit_chain SET action='forged' WHERE seq=1")
        self.assertFalse(self.core.verify_audit())
    def test_audit_survives_reopen(self):
        self.matter();new=SecureCore(self.path)
        try:self.assertTrue(new.verify_audit())
        finally:new.close()
