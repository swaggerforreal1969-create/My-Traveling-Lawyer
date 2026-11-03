"""Real socket-based integration tests; only fictional local SQLite data."""
import http.client
import threading
import tempfile
from pathlib import Path
import unittest
from src.secure_engine import SecureCore
from src.readiness_loopback_http import LoopbackReadinessServer

class HTTPReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.core=SecureCore(Path(self.temp.name)/'demo.sqlite3')
        firm=self.core.provision_firm('Fictional Firm')
        self.uid,self.token=self.core.provision_user(firm,'Invented Attorney')
        self.mid=self.core.create_matter(self.token,'PRIVATE TITLE')['id']
        other=self.core.provision_firm('Fictional Other Firm')
        _,self.outside=self.core.provision_user(other,'Other Fiction')
        self.server=LoopbackReadinessServer(self.core)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        self.core.close();self.temp.cleanup()
    def url(self,matter=None):
        return f'/v1/matters/{matter or self.mid}/readiness'
    def ticket(self,token=None,matter=None):
        return self.server.issue_ticket(token or self.token,matter or self.mid)['ticket']
    def send(self,path=None,method='GET',token=None,ticket=None,extra=None):
        con=http.client.HTTPConnection('127.0.0.1',self.server.server_address[1],timeout=4)
        headers={'Authorization':'Bearer '+(token or self.token),'X-Preview-Ticket':ticket or self.ticket()}
        if extra:headers.update(extra)
        con.request(method,path or self.url(),headers=headers)
        res=con.getresponse();body=res.read();code=res.status;headers=dict(res.getheaders());con.close()
        return code,headers,body
    def test_01_success_and_security_headers(self):
        code,h,body=self.send();self.assertEqual(200,code)
        self.assertIn(b'Private matter readiness',body)
        self.assertNotIn(b'PRIVATE TITLE',body)
        self.assertEqual(str(len(body)),h['Content-Length'])
        self.assertIn('no-store',h['Cache-Control'])
        self.assertIn('frame-ancestors',h['Content-Security-Policy'])
    def test_02_ticket_replay_denied(self):
        t=self.ticket();self.assertEqual(200,self.send(ticket=t)[0]);self.assertEqual(403,self.send(ticket=t)[0])
    def test_03_wrong_matter_fails_without_consuming_ticket(self):
        t=self.ticket();self.assertEqual(403,self.send(path=self.url('foreign-thing'),ticket=t)[0]);self.assertEqual(200,self.send(ticket=t)[0])
    def test_04_outsider_denied(self):
        self.assertEqual(403,self.send(token=self.outside)[0])
    def test_05_revoked_denied(self):
        t=self.ticket();self.core.revoke_token(self.token);self.assertEqual(403,self.send(ticket=t)[0])
    def test_06_ticket_missing_denied(self):
        self.assertEqual(403,self.send(ticket='x')[0])
    def test_07_header_origin_denied(self):
        self.assertEqual(403,self.send(extra={'Origin':'https://evil.example'})[0])
    def test_08_referer_denied(self):
        self.assertEqual(403,self.send(extra={'Referer':'https://evil.example'})[0])
    def test_09_cookie_denied(self):
        self.assertEqual(403,self.send(extra={'Cookie':'x=y'})[0])
    def test_10_wrong_host_denied(self):
        self.assertEqual(403,self.send(extra={'Host':'evil.example'})[0])
    def test_11_query_and_fragment_denied(self):
        self.assertEqual(404,self.send(path=self.url()+'?ticket=secret')[0])
    def test_12_no_bearer_denied(self):
        self.assertEqual(403,self.send(extra={'Authorization':'Token xxx'})[0])
    def test_13_methods_denied(self):
        for method in ('HEAD','POST','PUT','DELETE','OPTIONS'):
            with self.subTest(method=method):self.assertEqual(405,self.send(method=method)[0])
    def test_14_binds_loopback_only(self):
        self.assertEqual('127.0.0.1',self.server.server_address[0])
        with self.assertRaises(ValueError):LoopbackReadinessServer(self.core,('0.0.0.0',0))
    def test_15_no_sensitive_error_body(self):
        code,h,body=self.send(extra={'Authorization':'Bearer invalid'})
        self.assertEqual(403,code);self.assertEqual(b'',body)
        self.assertIn('no-store',h['Cache-Control'])
    def test_16_no_auth_in_url_and_csrf_checks(self):
        self.assertEqual(404,self.send(path=self.url()+'?auth='+self.token)[0])
        self.assertEqual(403,self.send(extra={'Origin':'null'})[0])

if __name__=='__main__':unittest.main()
