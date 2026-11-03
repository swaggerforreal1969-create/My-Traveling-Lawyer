"""Fictional fixtures and fail-closed checks for isolated preview adapter."""
from datetime import datetime, timezone
from unittest import TestCase
from src.mobile_preview_gateway import MobilePreviewGateway, PreviewRejected

TOKEN = 'fictional-test-token-token-token'
MATTER = 'fictional-matter-123'

class FakeBriefing:
    def __init__(self, core):
        self.core = core
    def prepare(self, token, matter_id, *, now=None):
        self.core.calls.append((token, matter_id, now))
        if token != TOKEN or matter_id != MATTER:
            raise PermissionError('denied')
        return {'matter_id': matter_id, 'schema': 'mtl.matter.preparation.v1'}

class FakeCore:
    def __init__(self): self.calls=[]

def render(brief):
    return '<!doctype html><title>private</title><p>Fictional</p>'

class TestMobilePreview(TestCase):
    def setUp(self):
        self.core=FakeCore()
        self.gateway=MobilePreviewGateway(self.core, briefing_factory=FakeBriefing, renderer=render)
    def test_happy_path(self):
        response=self.gateway.prepare(TOKEN, MATTER)
        self.assertEqual(response.status, 200)
        self.assertIn(b'Fictional', response.body)
        self.assertEqual(self.core.calls[0][1], MATTER)
    def test_sensitive_headers(self):
        headers=dict(self.gateway.prepare(TOKEN, MATTER).headers)
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertIn('private',headers['Cache-Control'])
        self.assertEqual('DENY',headers['X-Frame-Options'])
        self.assertEqual('no-referrer', headers['Referrer-Policy'])
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        self.assertIn("script-src 'none'",headers['Content-Security-Policy'])
    def test_no_token_in_response(self):
        obj=self.gateway.prepare(TOKEN, MATTER)
        self.assertNotIn(TOKEN,repr(obj))
    def test_bad_token_denied_before_briefing(self):
        for token in (None, 4, '', 'short'):
            with self.assertRaises(PreviewRejected):self.gateway.prepare(token,MATTER)
        self.assertEqual([], self.core.calls)
    def test_invalid_matter_denied_before_briefing(self):
        for matter in (None, '', 'x'*65):
            with self.assertRaises(PreviewRejected):self.gateway.prepare(TOKEN,matter)
        self.assertEqual([],self.core.calls)
    def test_credential_denial_propagates(self):
        with self.assertRaises(PermissionError):self.gateway.prepare('wrong-but-long-token', MATTER)
    def test_cross_matter_denied(self):
        with self.assertRaises(PermissionError):self.gateway.prepare(TOKEN, 'another-matter')
    def test_no_renderer_called_before_authorization(self):
        seen=[]
        gateway=MobilePreviewGateway(self.core, briefing_factory=FakeBriefing,
                                     renderer=lambda x:seen.append(x))
        with self.assertRaises(PermissionError):gateway.prepare('wrong-but-long-token', MATTER)
        self.assertEqual([],seen)
    def test_mismatched_briefing_rejected(self):
        class BadBrief(FakeBriefing):
            def prepare(self,*a,**kw):return {'matter_id':'other'}
        gateway=MobilePreviewGateway(self.core,briefing_factory=BadBrief,renderer=render)
        with self.assertRaises(PreviewRejected):gateway.prepare(TOKEN,MATTER)
    def test_renderer_invalid_output_fails(self):
        gateway=MobilePreviewGateway(self.core,briefing_factory=FakeBriefing,renderer=lambda x:None)
        with self.assertRaises(PreviewRejected):gateway.prepare(TOKEN,MATTER)
    def test_excess_output_fails(self):
        gateway=MobilePreviewGateway(self.core,briefing_factory=FakeBriefing,renderer=lambda x:'X'*300001)
        with self.assertRaises(PreviewRejected):gateway.prepare(TOKEN,MATTER)
    def test_empty_output_fails(self):
        gateway=MobilePreviewGateway(self.core,briefing_factory=FakeBriefing,renderer=lambda x:'')
        with self.assertRaises(PreviewRejected):gateway.prepare(TOKEN,MATTER)
    def test_timestamp_validation(self):
        with self.assertRaises(PreviewRejected):self.gateway.prepare(TOKEN,MATTER,now=datetime(2026,11,3))
        self.assertEqual([],self.core.calls)
    def test_aware_timestamp_passed(self):
        instant=datetime(2026,11,3,tzinfo=timezone.utc)
        self.gateway.prepare(TOKEN,MATTER,now=instant)
        self.assertEqual(instant,self.core.calls[0][2])
    def test_header_length_exact(self):
        resp=self.gateway.prepare(TOKEN,MATTER)
        self.assertEqual(str(len(resp.body)),dict(resp.headers)['Content-Length'])
    def test_no_network_imports(self):
        import ast,inspect,src.mobile_preview_gateway as module
        imports={name.name for node in ast.walk(ast.parse(inspect.getsource(module))) if isinstance(node,ast.Import) for name in node.names}
        self.assertFalse(imports.intersection({'requests','http','socket','urllib'}))
