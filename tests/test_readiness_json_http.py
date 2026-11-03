"""Real local HTTP acceptance for fictional confidential JSON preview."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from src.secure_engine import SecureCore
from src.research_evidence import ResearchEvidence
from src.readiness_json_http import LoopbackJSONReadinessServer


class JSONOverHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.core = SecureCore(Path(self.temp.name)/'fictional.db')
        firm = self.core.provision_firm('Fictional Law Lab')
        _, self.credential = self.core.provision_user(firm, 'Fictional Attorney')
        self.matter = self.core.create_matter(self.credential, 'VERY PRIVATE TITLE')['id']
        self.core.add_note(self.credential, self.matter, 'VERY PRIVATE NOTE')
        other = self.core.provision_firm('Separate Fictional Organization')
        _, self.outside = self.core.provision_user(other, 'Outside Attorney')
        self.server = LoopbackJSONReadinessServer(self.core)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=3)
        self.core.close()
        self.temp.cleanup()

    def ticket(self):
        return self.server.issue_ticket(self.credential, self.matter)['ticket']

    def request(self, *, ticket=None, credential=None, matter=None, extra=None, method='GET'):
        port = self.server.server_address[1]
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=4)
        head = {'Authorization': 'Bearer ' + (credential or self.credential),
                'X-Preview-Ticket': ticket if ticket is not None else self.ticket()}
        head.update(extra or {})
        conn.request(method, '/v1/matters/' + (matter or self.matter) + '/readiness', headers=head)
        resp = conn.getresponse()
        result = (resp.status, dict(resp.getheaders()), resp.read())
        conn.close()
        return result

    def test_01_real_http_json_and_no_private_text(self):
        code, headers, body = self.request()
        self.assertEqual(200, code)
        obj = json.loads(body)
        self.assertEqual('mtl.private.readiness.counts.v1', obj['schema'])
        self.assertEqual('application/json; charset=utf-8', headers['Content-Type'])
        self.assertEqual(str(len(body)), headers['Content-Length'])
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual('close', headers['Connection'])
        for private in (self.matter, self.credential, 'VERY PRIVATE TITLE', 'VERY PRIVATE NOTE', 'matter_id', 'evidence_id'):
            self.assertNotIn(private, body.decode())

    def test_02_single_ticket_replay_denied(self):
        t = self.ticket()
        self.assertEqual(200, self.request(ticket=t)[0])
        code, _, body = self.request(ticket=t)
        self.assertEqual((403, b''), (code, body))

    def test_03_wrong_matter_preserves_ticket(self):
        t = self.ticket()
        self.assertEqual(403, self.request(ticket=t, matter='foreign-matter')[0])
        self.assertEqual(200, self.request(ticket=t)[0])

    def test_04_cross_firm_denied(self):
        code, _, body = self.request(credential=self.outside)
        self.assertEqual((403, b''), (code, body))

    def test_05_revoked_credentials_denied(self):
        t = self.ticket()
        self.core.revoke_token(self.credential)
        self.assertEqual(403, self.request(ticket=t)[0])

    def test_06_unsafe_origin_does_not_consume_ticket(self):
        t = self.ticket()
        self.assertEqual(403, self.request(ticket=t, extra={'Origin': 'https://evil.example'})[0])
        self.assertEqual(200, self.request(ticket=t)[0])

    def test_07_tampered_source_fails_closed(self):
        sources = ResearchEvidence(self.core)
        sid = sources.add(self.credential, self.matter, 'PRIVATE SOURCE', 'https://example.org/law', 'PRIVATE EXCERPT')['id']
        t = self.ticket()
        self.core.db.execute('UPDATE research_evidence SET excerpt=? WHERE id=?', ('altered', sid))
        code, _, body = self.request(ticket=t)
        self.assertEqual((403, b''), (code, body))
        self.assertEqual(403, self.request(ticket=t)[0])

    def test_08_wrong_host_does_not_consume_ticket(self):
        t = self.ticket()
        self.assertEqual(403, self.request(ticket=t, extra={'Host': 'evil.example'})[0])
        self.assertEqual(200, self.request(ticket=t)[0])

    def test_09_unsafe_method_denied(self):
        t = self.ticket()
        self.assertEqual(405, self.request(ticket=t, method='POST')[0])
        self.assertEqual(200, self.request(ticket=t)[0])

    def test_10_loopback_only_and_no_ticket_http_endpoint(self):
        self.assertEqual('127.0.0.1', self.server.server_address[0])
        with self.assertRaises(ValueError):
            LoopbackJSONReadinessServer(self.core, address=('0.0.0.0', 0))
        self.assertEqual(404, self.request(matter='invalid?ticket=secret')[0])

if __name__ == '__main__':
    unittest.main()
