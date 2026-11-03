"""Accessible, static local attorney-operator summary with zero client text.

This document is NOT an authenticated HTTP endpoint and has no interactive
actions. The caller must obtain its OperatorScreen via PrivateAttorneyOperator
on every request; underlying review and task commands reauthorize separately.
"""
from dataclasses import dataclass
from html import escape

from .secure_engine import Invalid


class UnsafeOperatorDocument(ValueError):
    pass


@dataclass(frozen=True)
class PrivateOperatorDocument:
    html: bytes
    headers: tuple


def render_private_operator(screen):
    """Fail closed on untrusted or inconsistent local screen state."""
    if (getattr(screen, 'schema', None) != 'mtl.private.operator.screen.v1'
            or not isinstance(getattr(screen, 'matter_id', None), str)
            or not 1 <= len(screen.matter_id) <= 64
            or type(getattr(screen, 'open_task_count', None)) is not int
            or type(getattr(screen, 'pending_second_review_count', None)) is not int
            or not 0 <= screen.open_task_count <= 100
            or not 0 <= screen.pending_second_review_count <= 100
            or type(getattr(screen, 'can_complete_tasks', None)) is not bool
            or any(getattr(screen, k, None) is not False for k in (
                'legal_deadlines_verified', 'official_law_verified',
                'court_filing_approved', 'external_ai_transmission'))):
        raise UnsafeOperatorDocument('Unsafe operator summary state')
    if not screen.can_complete_tasks and screen.pending_second_review_count:
        raise UnsafeOperatorDocument('Unauthorized reviewer work shown')
    # No user-provided IDs, text, note, source URL or bearer token is emitted.
    # The existing script-free readiness document is not inlined or trusted as
    # arbitrary markup. It remains a separately authorized presentation.
    review = ('Review work awaiting a second human'
              if screen.can_complete_tasks else 'Review work unavailable to reader')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Private attorney work summary</title>'
        '<style>body{font:1.125rem system-ui,sans-serif;line-height:1.6;'
        'max-width:42rem;margin:auto;padding:1rem;color:#171717;background:#fff}'
        'main{display:block}section{border:2px solid #555;border-radius:.65rem;'
        'padding:1rem;margin:1rem 0}strong{font-variant-numeric:tabular-nums}'
        ':focus-visible{outline:3px solid #075ec4;outline-offset:3px}'
        '@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}'
        '</style></head><body><main id="content">'
        '<h1>Private attorney work summary</h1>'
        '<p role="status">Local procedural overview only. '
        'This screen does not authorize any write or validate legal authority.</p>'
        '<section aria-labelledby="task-heading"><h2 id="task-heading">Open tasks</h2>'
        '<p><strong aria-label="Open task count">'+str(screen.open_task_count)
        +'</strong> open tasks based on user-entered information.</p></section>'
        '<section aria-labelledby="review-heading"><h2 id="review-heading">Human review</h2>'
        '<p>'+escape(review)+': <strong>'+str(screen.pending_second_review_count)
        +'</strong></p></section>'
        '<section aria-labelledby="limits-heading"><h2 id="limits-heading">Security limits</h2>'
        '<p>Dates entered by users are not verified court deadlines. '
        'Two-person review does not verify official law, citation status or jurisdiction. '
        'No court filing is approved. No AI transmission occurs.</p>'
        '<p>This read-only page does not submit reviews or complete tasks. '
        'Use a separately authorized local operator action.</p></section>'
        '</main></body></html>').encode('utf-8')
    if len(html) > 8192:
        raise UnsafeOperatorDocument('Unexpected document length')
    return PrivateOperatorDocument(html, (
        ('Content-Type', 'text/html; charset=utf-8'),
        ('Cache-Control', 'no-store, no-cache, must-revalidate, private'),
        ('Content-Security-Policy',
         "default-src 'none'; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; img-src 'none'; form-action 'none'; frame-ancestors 'none'"),
        ('X-Content-Type-Options', 'nosniff'),
        ('Referrer-Policy', 'no-referrer'),
        ('X-Frame-Options', 'DENY'),
        ('Content-Length', str(len(html))),
    ))
