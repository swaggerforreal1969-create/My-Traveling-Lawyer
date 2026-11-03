"""Real socket-based integration tests; only fictional local SQLite data."""
import http.client
import socket
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

    def raw_request(self, header_lines, *, path=None):
        """Send exact duplicate fields over the actual socket, without proxy emulation."""
        con=http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=4)
        con.putrequest('GET', path or self.url(), skip_host=True, skip_accept_encoding=True)
        for name, value in header_lines:
            con.putheader(name, value)
        con.endheaders()
        res=con.getresponse(); code=res.status; body=res.read();con.close()
        return code,body

    def base_fields(self, ticket=None):
        return [('Host','127.0.0.1:'+str(self.server.server_address[1])),
                ('Authorization','Bearer '+self.token),
                ('X-Preview-Ticket',ticket or self.ticket())]

    def test_17_duplicate_authorization_rejected_without_burning_ticket(self):
        ticket=self.ticket();h=self.base_fields(ticket)
        self.assertEqual((403,b''),self.raw_request(h+[('authorization','Bearer '+self.outside)]))
        self.assertEqual(200,self.send(ticket=ticket)[0])

    def test_18_duplicate_preview_ticket_rejected_without_burning(self):
        ticket=self.ticket();h=self.base_fields(ticket)
        self.assertEqual((403,b''),self.raw_request(h+[('x-preview-ticket',self.ticket())]))
        self.assertEqual(200,self.send(ticket=ticket)[0])

    def test_19_duplicate_host_rejected_without_burning(self):
        ticket=self.ticket();h=self.base_fields(ticket)
        self.assertEqual((403,b''),self.raw_request(h+[('HOST','evil.example')]))
        self.assertEqual(200,self.send(ticket=ticket)[0])

    def test_20_proxy_forwarding_headers_rejected(self):
        for name in ('Proxy-Authorization','Forwarded','X-Forwarded-Host','X-Original-URL','Expect'):
            with self.subTest(name=name):
                self.assertEqual(403,self.send(extra={name:'other'})[0])

    def test_21_duplicate_arbitrary_field_rejected(self):
        ticket=self.ticket();h=self.base_fields(ticket)
        self.assertEqual(403,self.raw_request(h+[('X-Other','1'),('x-other','2')])[0])
        self.assertEqual(200,self.send(ticket=ticket)[0])

    def test_22_too_many_headers_rejected(self):
        ticket=self.ticket();h=self.base_fields(ticket)
        h.extend(('X-Extra-%02d'%i,'v') for i in range(35))
        self.assertEqual(403,self.raw_request(h)[0])
        self.assertEqual(200,self.send(ticket=ticket)[0])

    def _pipelined_reply(self, first, second):
        # Raw on-wire test: an invalid request may include unread bytes that
        # resemble a second authenticated HTTP message. Connection must close.
        with socket.create_connection(('127.0.0.1', self.server.server_address[1]), timeout=4) as sock:
            sock.settimeout(4)
            sock.sendall(first + second)
            parts = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                parts.append(chunk)
        return b''.join(parts)

    def _wire_get(self, ticket, path=None):
        path = path or self.url()
        port = self.server.server_address[1]
        return (f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n'
                f'Authorization: Bearer {self.token}\r\n'
                f'X-Preview-Ticket: {ticket}\r\n\r\n').encode()

    def test_23_duplicate_header_pipeline_closes_without_consuming(self):
        ticket = self.ticket()
        first = self._wire_get(ticket).replace(b'\r\n\r\n', b'\r\nauthorization: Bearer invalid\r\n\r\n')
        reply = self._pipelined_reply(first, self._wire_get(ticket))
        self.assertEqual(1, reply.count(b'HTTP/1.1 '))
        self.assertIn(b'HTTP/1.1 403', reply)
        self.assertIn(b'Connection: close', reply)
        self.assertNotIn(b'Private matter readiness', reply)
        self.assertEqual(200, self.send(ticket=ticket)[0])

    def test_24_post_body_pipeline_closes_without_consuming(self):
        ticket = self.ticket()
        first = (f'POST {self.url()} HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_address[1]}\r\n'
                 'Content-Length: 16\r\n\r\n1234567890123456').encode()
        reply = self._pipelined_reply(first, self._wire_get(ticket))
        self.assertEqual(1, reply.count(b'HTTP/1.1 '))
        self.assertIn(b'HTTP/1.1 405', reply)
        self.assertIn(b'Connection: close', reply)
        self.assertEqual(200, self.send(ticket=ticket)[0])

    def test_25_success_connection_closes_after_one_preview(self):
        first_ticket, second_ticket = self.ticket(), self.ticket()
        reply = self._pipelined_reply(self._wire_get(first_ticket), self._wire_get(second_ticket))
        self.assertEqual(1, reply.count(b'HTTP/1.1 '))
        self.assertIn(b'HTTP/1.1 200', reply)
        self.assertIn(b'Connection: close', reply)
        self.assertIn(b'Private matter readiness', reply)
        self.assertEqual(403, self.send(ticket=first_ticket)[0])
        self.assertEqual(200, self.send(ticket=second_ticket)[0])

    def test_26_unimplemented_methods_reject_without_consuming_ticket(self):
        t=self.ticket()
        for method in ('PATCH','TRACE','CONNECT'):
            with self.subTest(method=method):
                code,headers,body=self.send(method=method,ticket=t)
                self.assertEqual(405, code)
                self.assertEqual(b'', body)
                self.assertEqual('close',headers.get('Connection'))
        self.assertEqual(200,self.send(ticket=t)[0])

    def test_27_http_10_rejected_without_consuming_ticket(self):
        t=self.ticket()
        request=self._wire_get(t).replace(b'HTTP/1.1',b'HTTP/1.0',1)
        reply=self._pipelined_reply(request,b'')
        self.assertIn(b' 403 ',reply)
        self.assertIn(b'Connection: close',reply)
        self.assertEqual(200,self.send(ticket=t)[0])

    def test_28_simultaneous_http_requests_consume_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        t=self.ticket()
        barrier=Barrier(6)
        def request(_):
            barrier.wait(timeout=5)
            return self.send(ticket=t)[0]
        with ThreadPoolExecutor(max_workers=6) as pool:
            codes=list(pool.map(request,range(6)))
        self.assertEqual(1,codes.count(200))
        self.assertEqual(5,codes.count(403))
        self.assertEqual(403,self.send(ticket=t)[0])

    def test_29_capacity_saturation_fails_closed_without_using_ticket(self):
        import time
        # Replace the normal fixture server with a one-slot private server.
        small=LoopbackReadinessServer(self.core, max_connections=1, idle_seconds=2)
        thread=threading.Thread(target=small.serve_forever,daemon=True)
        thread.start()
        held=socket.create_connection(('127.0.0.1',small.server_address[1]),timeout=4)
        held.sendall(b'GET /v1/matters/unfinished HTTP/1.1\r\nHost: ')
        try:
            # Wait for the worker to claim its only slot, without racing accept().
            deadline=time.monotonic()+2
            while small._slots._value and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertEqual(0,small._slots._value)
            t=small.issue_ticket(self.token,self.mid)['ticket']
            with socket.create_connection(('127.0.0.1',small.server_address[1]),timeout=3) as sock:
                sock.settimeout(3)
                sock.sendall(self._wire_get(t))
                self.assertEqual(b'',sock.recv(4096))
            held.close()
            deadline=time.monotonic()+3
            while small._slots._value==0 and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertEqual(1,small._slots._value)
            con=http.client.HTTPConnection('127.0.0.1',small.server_address[1],timeout=3)
            con.request('GET',self.url(),headers={'Authorization':'Bearer '+self.token,
                         'X-Preview-Ticket':t})
            response=con.getresponse()
            self.assertEqual(200,response.status)
            response.read();con.close()
        finally:
            held.close();small.shutdown();small.server_close();thread.join(timeout=3)

    def test_30_idle_connection_times_out_releasing_capacity(self):
        import time
        small=LoopbackReadinessServer(self.core, max_connections=1, idle_seconds=0.5)
        thread=threading.Thread(target=small.serve_forever,daemon=True);thread.start()
        sock=socket.create_connection(('127.0.0.1',small.server_address[1]),timeout=3)
        sock.settimeout(3)
        sock.sendall(b'GET /v1/matters/incomplete HTTP/1.1\r\n')
        try:
            deadline=time.monotonic()+2
            while small._slots._value and time.monotonic()<deadline:time.sleep(0.01)
            self.assertEqual(0,small._slots._value)
            deadline=time.monotonic()+3
            while small._slots._value==0 and time.monotonic()<deadline:time.sleep(0.02)
            self.assertEqual(1,small._slots._value)
            self.assertEqual(b'',sock.recv(2048))
        finally:
            sock.close();small.shutdown();small.server_close();thread.join(timeout=3)

    def test_31_unsafe_resource_limits_cannot_be_configured(self):
        for n in (0,17,True,-1):
            with self.subTest(capacity=n):
                with self.assertRaises(ValueError):
                    LoopbackReadinessServer(self.core,max_connections=n)
        for seconds in (0,0.2,6,True):
            with self.subTest(timeout=seconds):
                with self.assertRaises(ValueError):
                    LoopbackReadinessServer(self.core,idle_seconds=seconds)

if __name__=='__main__':unittest.main()
