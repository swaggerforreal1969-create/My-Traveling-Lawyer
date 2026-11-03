"""Experimental loopback-only HTTP adapter for fictional mobile readiness previews.

Never expose outside localhost or treat this server as production deployment.
A valid bearer AND previously issued single-use ticket are required per GET.
"""
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .research_evidence import ResearchEvidence
from .source_observation import SourceObservation
from .second_source_review import SecondSourceReview
from .mobile_readiness_view import MobileReadinessView
from .preview_session import PreviewSessionBroker

_PATH = re.compile(r'/v1/matters/([a-zA-Z0-9_-]{1,64})/readiness\Z', re.ASCII)
_DENIAL_HEADERS = (
    ('Cache-Control', 'no-store, no-cache, must-revalidate, private'),
    ('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'"),
    ('X-Content-Type-Options', 'nosniff'),
    ('X-Frame-Options', 'DENY'),
    ('Referrer-Policy', 'no-referrer'),
)


class LoopbackReadinessServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, core, address=('127.0.0.1', 0)):
        if not isinstance(address, tuple) or len(address) != 2 or address[0] != '127.0.0.1':
            raise ValueError('Only literal 127.0.0.1 loopback binding supported')
        if type(address[1]) is not int or not 0 <= address[1] <= 65535:
            raise ValueError('Invalid loopback port')
        # Initialize optional experimental tables in dependency order.
        ResearchEvidence(core)
        SourceObservation(core)
        SecondSourceReview(core)
        self.broker = PreviewSessionBroker(core, gateway=MobileReadinessView(core))
        super().__init__(address, LoopbackReadinessHandler, bind_and_activate=True)

    def issue_ticket(self, credential, matter_id):
        """In-process only: never provide an unauthenticated HTTP ticket endpoint."""
        return self.broker.issue(credential, matter_id)


class LoopbackReadinessHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        # No request-target or header logging; secrets must not enter access logs.
        return

    def _deny(self, status=403):
        self.send_response(status)
        for key, value in _DENIAL_HEADERS:
            self.send_header(key, value)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _host_allowed(self):
        host = self.headers.get('Host')
        if host is None:
            return False
        expected = '127.0.0.1:' + str(self.server.server_address[1])
        # Exact header match; no alternate name, DNS rebinding, or port ambiguity.
        return host == expected

    def do_GET(self):
        if (not self._host_allowed() or self.headers.get('Origin') is not None or
                self.headers.get('Referer') is not None or self.headers.get('Cookie') is not None or
                self.headers.get('Transfer-Encoding') is not None or self.headers.get('Content-Length') is not None):
            return self._deny()
        match = _PATH.fullmatch(self.path)
        if match is None:
            return self._deny(404)
        auth = self.headers.get('Authorization')
        ticket = self.headers.get('X-Preview-Ticket')
        if not isinstance(auth, str) or not auth.startswith('Bearer ') or auth.count(' ') != 1:
            return self._deny()
        token = auth[7:]
        if not isinstance(ticket, str) or not (32 <= len(ticket) <= 512):
            return self._deny()
        try:
            preview = self.server.broker.consume(token, match.group(1), ticket)
        except Exception:
            # Fail closed; never leak exception class, matter existence or source data.
            return self._deny()
        self.send_response(200)
        for key, value in preview.headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(preview.body)

    def do_HEAD(self):
        self._deny(405)

    def do_POST(self):
        self._deny(405)

    def do_PUT(self):
        self._deny(405)

    def do_DELETE(self):
        self._deny(405)

    def do_OPTIONS(self):
        self._deny(405)
