"""Script-free mobile presentation of a previously authenticated readiness JSON response.

This adapter never fetches, stores, or transmits anything. Its caller must supply
an authenticated one-use-ticket response. It does NOT issue credentials or verify
legal authority. Strictly refuse unknown fields rather than rendering them.
"""
import json
from html import escape
from dataclasses import dataclass

STATUSES = (
    ('needs_additional_review', 'Additional human review required'),
    ('needs_first_observation', 'First source observation required'),
    ('needs_independent_second_review', 'Second human review required'),
    ('rejected_by_second_reviewer', 'Rejected by second reviewer'),
    ('two_people_reviewed_unverified', 'Two people reviewed; law unverified'),
)
_COUNTS = frozenset(('open_tasks', 'past_user_entered_dates_not_court_deadlines',
                     'research_sources', 'research_needing_procedural_work'))
_FALSE_FLAGS = frozenset(('legal_source_authenticated', 'legal_deadlines_verified',
                          'court_filing_approved', 'outbound_ai_transmission',
                          'human_review_is_legal_verification'))
_FIELDS = {'schema', 'review_counts'} | _COUNTS | _FALSE_FLAGS

class UnsafeReadinessDocument(ValueError):
    """Fail closed on unexpected authenticated representation."""

def _unique_json_object(pairs):
    """Reject ambiguous JSON at *every* object nesting level.

    Standard json.loads silently keeps the final value on duplicate keys,
    which can make auditing a purportedly authenticated representation
    ambiguous. Reject before schema and legal safety checks.
    """
    out = {}
    for key, value in pairs:
        if key in out:
            raise UnsafeReadinessDocument('Duplicate JSON member')
        out[key] = value
    return out

@dataclass(frozen=True)
class PrivateMobileDocument:
    html: bytes
    headers: tuple


def render_authenticated_readiness(response):
    """Convert a trusted in-process JSON PreviewResponse to script-free HTML.

    The conversion does not authenticate users: callers MUST use the already
    authenticated ReadinessJSON / PreviewSessionBroker boundary beforehand.
    """
    if getattr(response, 'status', None) != 200:
        raise UnsafeReadinessDocument('Authentication response was not successful')
    headers = getattr(response, 'headers', ())
    if not isinstance(headers, (list, tuple)):
        raise UnsafeReadinessDocument('Missing response security headers')
    seen = {}
    for pair in headers:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2 or not all(isinstance(x,str) for x in pair):
            raise UnsafeReadinessDocument('Bad response headers')
        key, val = pair
        if key.lower() in seen:
            raise UnsafeReadinessDocument('Duplicate response header')
        seen[key.lower()] = val
    body = getattr(response, 'body', None)
    if not isinstance(body, bytes) or len(body) > 8192 or not body:
        raise UnsafeReadinessDocument('Invalid response bytes')
    cache_directives = [part.strip().lower() for part in seen.get('cache-control', '').split(',')]
    # Only the narrowly allowed upstream non-cacheable policy is accepted.
    # Substrings such as 'not-no-store' are not actual cache directives.
    allowed_cache = {'no-store', 'no-cache', 'must-revalidate', 'private'}
    if (not cache_directives or 'no-store' not in cache_directives or
            any(part not in allowed_cache for part in cache_directives)):
        raise UnsafeReadinessDocument('Untrusted cache directives')
    if (seen.get('content-type') != 'application/json; charset=utf-8' or
            seen.get('x-content-type-options') != 'nosniff' or
            seen.get('content-length') != str(len(body))):
        raise UnsafeReadinessDocument('Authenticated response security policy missing')
    try:
        payload = json.loads(body.decode('utf-8'),
                             object_pairs_hook=_unique_json_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
        raise UnsafeReadinessDocument('Invalid readiness JSON') from e
    if type(payload) is not dict or set(payload) != _FIELDS or payload.get('schema') != 'mtl.private.readiness.counts.v1':
        raise UnsafeReadinessDocument('Unknown readiness schema')
    if any(payload.get(k) is not False for k in _FALSE_FLAGS):
        raise UnsafeReadinessDocument('Unsafe legal or AI claims')
    if any(type(payload.get(k)) is not int or not 0 <= payload[k] <= 100 for k in _COUNTS):
        raise UnsafeReadinessDocument('Invalid integer count')
    counts = payload['review_counts']
    if type(counts) is not dict or set(counts) != {s for s, _ in STATUSES}:
        raise UnsafeReadinessDocument('Unknown procedural statuses')
    if any(type(counts[k]) is not int or not 0 <= counts[k] <= 100 for k, _ in STATUSES):
        raise UnsafeReadinessDocument('Invalid review count')
    if (sum(counts.values()) != payload['research_sources'] or
            payload['research_needing_procedural_work'] != payload['research_sources'] - counts['two_people_reviewed_unverified'] or
            payload['past_user_entered_dates_not_court_deadlines'] > payload['open_tasks']):
        raise UnsafeReadinessDocument('Inconsistent review totals')
    def row(label, count):
        return '<li><span>'+escape(label)+'</span><strong>'+str(count)+'</strong></li>'
    p = payload
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Private attorney readiness</title><style>'
            'body{font:1rem system-ui,sans-serif;max-width:40rem;margin:auto;padding:1rem;line-height:1.5}'
            'section{border:1px solid gray;border-radius:.7rem;padding:1rem;margin:1rem 0}'
            'li{display:flex;justify-content:space-between;gap:1rem;margin:.7rem 0}'
            'strong{font-variant-numeric:tabular-nums}summary{font-weight:bold;cursor:pointer}'
            '</style></head><body><h1>Private matter readiness</h1>'
            '<p>PROCEDURAL TRIAGE ONLY. Not legal advice, verified law, or filing approval.</p>'
            '<section><h2>Open work</h2><ul>'
            + row('Open tasks', p['open_tasks'])
            + row('Past user-entered dates, NOT court deadlines', p['past_user_entered_dates_not_court_deadlines'])
            + '</ul></section><section><h2>Source review</h2><ul>'
            + row('Research sources needing review', p['research_needing_procedural_work'])
            + '</ul><details><summary>Procedural review breakdown</summary><ul>'
            + ''.join(row(label, counts[key]) for key, label in STATUSES)
            + '</ul></details></section><p>Human review never verifies official origin, legal status, citation treatment or jurisdiction. No AI transmission.</p>'
            '</body></html>').encode('utf-8')
    if len(html) > 16384:
        raise UnsafeReadinessDocument('HTML too large')
    return PrivateMobileDocument(html, (
        ('Content-Type','text/html; charset=utf-8'),
        ('Cache-Control','no-store, no-cache, must-revalidate, private'),
        ('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; img-src 'none'; form-action 'none'; frame-ancestors 'none'"),
        ('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),
        ('X-Frame-Options','DENY'),('Content-Length',str(len(html))),
    ))
