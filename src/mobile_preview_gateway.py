"""Experimental authenticated mobile preview boundary; no HTTP listener or hosting.

Compose the existing matter briefing authorization with the script-free renderer.
This is deliberately a local adapter, NOT an authenticated public API endpoint.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .matter_brief import MatterBrief
from .mobile_matter_view import render_mobile_brief


class PreviewRejected(ValueError):
    """The preview request did not meet the contract."""


@dataclass(frozen=True)
class PreviewResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def __post_init__(self):
        if self.status != 200 or not self.body:
            raise PreviewRejected('Successful, nonempty render required')


_HEADERS = (
    ('Content-Type', 'text/html; charset=utf-8'),
    ('Cache-Control', 'no-store, no-cache, must-revalidate, private'),
    ('Pragma', 'no-cache'),
    ('X-Content-Type-Options', 'nosniff'),
    ('Referrer-Policy', 'no-referrer'),
    ('Content-Security-Policy',
     "default-src 'none'; script-src 'none'; connect-src 'none'; img-src 'none'; "
     "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"),
    ('X-Frame-Options', 'DENY'),
)


class MobilePreviewGateway:
    """Only allow server-side token -> authorized snapshot -> offline HTML.

    Do not persist, log, or otherwise return the bearer credential.
    Authentication and matter authorization are performed by MatterBrief.prepare.
    """

    MAX_BYTES = 300_000

    def __init__(self, core, *, briefing_factory: Callable = MatterBrief,
                 renderer: Callable = render_mobile_brief):
        self.briefing = briefing_factory(core)
        self.renderer = renderer

    def prepare(self, token, matter_id, *, now=None):
        if not isinstance(token, str) or not (16 <= len(token) <= 2048):
            raise PreviewRejected('Valid authorization credential required')
        if not isinstance(matter_id, str) or not (1 <= len(matter_id) <= 64):
            raise PreviewRejected('Invalid matter identifier')
        if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
            raise PreviewRejected('Preview timestamp must include timezone')

        # The briefing service must authenticate and authorize before rendering.
        brief = self.briefing.prepare(token, matter_id, now=now)
        if not isinstance(brief, dict) or brief.get('matter_id') != matter_id:
            raise PreviewRejected('Briefing did not match requested matter')
        html = self.renderer(brief)
        if not isinstance(html, str):
            raise PreviewRejected('Renderer returned invalid content')
        payload = html.encode('utf-8')
        if not payload or len(payload) > self.MAX_BYTES:
            raise PreviewRejected('Preview too large or empty')
        return PreviewResponse(200, _HEADERS + (('Content-Length', str(len(payload))),), payload)
