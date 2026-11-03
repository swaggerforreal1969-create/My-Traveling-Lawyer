"""Experimental loopback-only HTTP adapter for fictional mobile readiness previews.

Never expose outside localhost or treat this server as production deployment.
A valid bearer AND previously issued single-use ticket are required per GET.
"""
import re
import threading
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

    def __init__(self, core, address=('127.0.0.1', 0), *, max_connections=8, idle_seconds=2.0):
        if not isinstance(address, tuple) or len(address) != 2 or address[0] != '127.0.0.1':
            raise ValueError('Only literal 127.0.0.1 loopback binding supported')
        if type(address[1]) is not int or not 0 <= address[1] <= 65535:
            raise ValueError('Invalid loopback port')
        if type(max_connections) is not int or not 1 <= max_connections <= 16:
            raise ValueError('Bounded connection capacity required')
        if type(idle_seconds) not in (int, float) or not 0.5 <= idle_seconds <= 5.0:
            raise ValueError('Bounded idle timeout required')
        self._slots = threading.BoundedSemaphore(max_connections)
        self._idle_seconds = float(idle_seconds)
        # Initialize optional experimental tables in dependency order.
        ResearchEvidence(core)
        SourceObservation(core)
        SecondSourceReview(core)
        self.broker = PreviewSessionBroker(core, gateway=MobileReadinessView(core))
        super().__init__(address, LoopbackReadinessHandler, bind_and_activate=True)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(self._idle_seconds)
        return request, address

    def process_request(self, request, client_address):
        # Never allocate unlimited idle worker threads. Close excess sockets
        # before their headers or credentials are parsed.
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def issue_ticket(self, credential, matter_id):
        """In-process only: never provide an unauthenticated HTTP ticket endpoint."""
        return self.broker.issue(credential, matter_id)


class LoopbackReadinessHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        # No request-target or header logging; secrets must not enter access logs.
        return

    def send_error(self, code, message=None, explain=None):
        """Parser-level failures get the same private, empty response as ACL denial.

        The stdlib default produces a descriptive HTML error page before
        do_GET can evaluate authentication. No parser-generated body or
        request details are returned to an untrusted local client.
        """
        # BaseHTTPRequestHandler uses HTTP/0.9 on malformed request lines,
        # otherwise suppressing the entire error response. Send a bounded
        # HTTP/1.1 denial independent of the untrusted request version.
        self.request_version = 'HTTP/1.1'
        self._deny(code)

    def _deny(self, status=403):
        # Never parse bytes following a rejected request as a new authorized
        # request. The request might contain an unread body or pipelined data.
        self.close_connection = True
        self.send_response(status)
        self.send_header('Connection', 'close')
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

    def _headers_unambiguous(self):
        """Deny HTTP parser disagreement before validating or burning a ticket.

        Duplicate Host, authorization or ticket fields can be interpreted
        differently by upstream parsers. This prototype rejects *all* duplicate
        field names rather than choosing a winning value. It also refuses
        proxy/routing headers and excessive fields. No header values are logged.
        """
        items = list(self.headers.items())
        if len(items) > 32:
            return False
        names = [name.casefold() for name, _ in items]
        if len(names) != len(set(names)):
            return False
        if any(name in names for name in (
                'proxy-authorization', 'proxy-connection', 'forwarded',
                'x-forwarded-host', 'x-forwarded-for', 'x-forwarded-proto',
                'x-original-url', 'x-rewrite-url', 'expect')):
            return False
        return all(len(name) <= 64 and len(value) <= 2048 and
                   all(32 <= ord(ch) <= 126 or ch == '\t' for ch in value)
                   for name, value in items)

    def do_GET(self):
        if (self.request_version != 'HTTP/1.1' or
                not self._headers_unambiguous() or not self._host_allowed() or
                self.headers.get('Origin') is not None or
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
        # One authorized preview per connection; no ambient keep-alive state.
        self.close_connection = True
        self.send_response(200)
        self.send_header('Connection', 'close')
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

    def do_PATCH(self):
        self._deny(405)

    def do_TRACE(self):
        self._deny(405)

    def do_CONNECT(self):
        self._deny(405)
