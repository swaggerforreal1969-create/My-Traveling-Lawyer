"""No-network tests for disabled and pinned TLS custody connector."""
import hashlib
import json
import unittest
from unittest.mock import patch
from src.pinned_https_custody_adapter import PinnedHTTPSCustodyAdapter
from src.secure_engine import Denied

CERT=b"fictional-tls-certificate"
PIN=hashlib.sha256(CERT).hexdigest()
ENDPOINT="https://custody.example.org"


class FakeResponse:
    def __init__(self,status=200,contents=None,ctype="application/json"):
        self.status=status
        self.contents=(json.dumps({"sequence":1,"head_digest":"f"*64}).encode()
                       if contents is None else contents)
        self.ctype=ctype
    def getheader(self,key,default=None):
        if key=="Content-Type":return self.ctype
        if key=="Content-Length":return str(len(self.contents))
        return default
    def read(self,size):
        return self.contents[:size]


class FakeConnection:
    def __init__(self,*args,**kwargs):
        self.called=[]
        self.sock=self
        self.certificate=CERT
        self.response=FakeResponse()
    def connect(self):
        self.called.append("connect")
    def getpeercert(self,**kwargs):
        return self.certificate
    def request(self,method,path,body=None,headers=None):
        self.called.append((method,path,body,headers))
    def getresponse(self):
        return self.response
    def close(self):
        self.called.append("close")


class RealProviderReadinessTests(unittest.TestCase):
    def setUp(self):
        self.connection=FakeConnection()
        patcher=patch("src.pinned_https_custody_adapter.http.client.HTTPSConnection",
                      side_effect=lambda *args,**kwargs:self.connection)
        self.mock_conn=patcher.start()
        self.addCleanup(patcher.stop)
        patcher2=patch("src.pinned_https_custody_adapter.ssl.create_default_context")
        self.context=patcher2.start()
        self.addCleanup(patcher2.stop)

    def active(self,**kw):
        args={"endpoint":ENDPOINT,"certificate_sha256":PIN,"enabled":True}
        args.update(kw)
        return PinnedHTTPSCustodyAdapter(**args)

    def test_disabled_default_cannot_contact_network(self):
        adapter=PinnedHTTPSCustodyAdapter()
        with self.assertRaises(Denied):
            adapter("read_head",{})
        self.mock_conn.assert_not_called()

    def test_https_certificate_and_chain_configuration_before_request(self):
        response=self.active()("read_head",{"credential":"fictional"})
        self.assertEqual(response["sequence"],1)
        self.assertEqual(self.connection.called[0],"connect")
        self.assertEqual(self.connection.called[1][0],"POST")
        self.assertEqual(self.connection.called[1][1],"/v1/custody/head")
        self.assertEqual(self.connection.called[-1],"close")
        self.assertEqual(self.context.return_value.minimum_version,
                         __import__("ssl").TLSVersion.TLSv1_2)

    def test_wrong_leaf_certificate_never_sends_request(self):
        self.connection.certificate=b"substituted"
        with self.assertRaises(Denied):self.active()("admit",{"nonce":"f"*64})
        self.assertFalse(any(isinstance(x,tuple) for x in self.connection.called))

    def test_http_redirect_and_denial_never_replay_or_follow(self):
        self.connection.response=FakeResponse(status=307)
        with self.assertRaises(Denied):self.active()("admit",{"nonce":"f"*64})
        self.assertEqual(sum(isinstance(x,tuple) for x in self.connection.called),1)

    def test_reject_unapproved_endpoints(self):
        for url in ("http://custody.example.org","https://localhost",
                    "https://127.0.0.1","https://custody.example.org/path",
                    "https://user:password@custody.example.org",
                    "https://custody.example.org:444/",
                    "https://custody.example.org?x=y"):
            with self.subTest(url=url),self.assertRaises(Denied):
                PinnedHTTPSCustodyAdapter(endpoint=url,
                                         certificate_sha256=PIN,enabled=True)
        self.mock_conn.assert_not_called()

    def test_provider_invalid_content_or_oversized_body_denied(self):
        self.connection.response=FakeResponse(ctype="text/html")
        with self.assertRaises(Denied):self.active()("read_head",{})
        self.connection.response=FakeResponse(contents=b"0"*16385)
        with self.assertRaises(Denied):self.active()("read_head",{})

    def test_reject_duplicate_json_properties_and_invalid_unicode(self):
        self.connection.response=FakeResponse(contents=b'{"a":1,"a":2}')
        with self.assertRaises(Denied):self.active()("read_head",{})
        self.connection.response=FakeResponse(contents=b"\xff")
        with self.assertRaises(Denied):self.active()("read_head",{})

    def test_transport_error_fails_closed_without_retry(self):
        self.connection.connect=lambda: (_ for _ in ()).throw(OSError("no network"))
        with self.assertRaises(Denied):self.active()("admit",{})
        self.assertEqual(self.mock_conn.call_count,1)

    def test_requires_explicit_pin_and_bounded_timeouts(self):
        for key,values in (("certificate_sha256",[None,"0",PIN.upper()]),
                           ("timeout_seconds",[0,16])):
            for value in values:
                kw={key:value}
                with self.subTest(kw=kw),self.assertRaises(Denied):
                    self.active(**kw)

    def test_adapter_cannot_activate_other_operations(self):
        with self.assertRaises(Denied):self.active()("delete_history",{})
        self.mock_conn.assert_not_called()


if __name__=="__main__":
    unittest.main()
