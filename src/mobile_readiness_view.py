"""No-network, authenticated single-matter readiness HTML preview.

The caller supplies an existing SecureCore credential, never a ready-made status
object. The underlying MatterReadiness service rechecks firm, matter and record
integrity. This is an in-process prototype, not a public HTTP service.
"""
from datetime import datetime
from html import escape
from .matter_readiness import MatterReadiness
from .mobile_preview_gateway import PreviewRejected, PreviewResponse, _HEADERS

_STATUSES = (
    ('needs_first_observation', 'Initial research observation required'),
    ('needs_independent_second_review', 'Independent human review required'),
    ('needs_additional_review', 'Additional human review required'),
    ('rejected_by_second_reviewer', 'Rejected by second reviewer'),
    ('two_people_reviewed_unverified', 'Two people reviewed — law remains unverified'),
)


class MobileReadinessView:
    MAX_BYTES = 32_768

    def __init__(self, core):
        self.service = MatterReadiness(core)

    def prepare(self, token, matter_id, *, now=None):
        if not isinstance(token, str) or not (32 <= len(token) <= 512):
            raise PreviewRejected('Valid authorization credential required')
        if not isinstance(matter_id, str) or not (1 <= len(matter_id) <= 64):
            raise PreviewRejected('Invalid matter identifier')
        if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
            raise PreviewRejected('Timezone-aware timestamp required')
        summary = self.service.summarize(token, matter_id, now=now)
        if not isinstance(summary, dict) or summary.get('schema') != 'mtl.matter.readiness.v1' or summary.get('matter_id') != matter_id:
            raise PreviewRejected('Unrecognized readiness summary')
        for field in ('court_filing_approved', 'source_authenticated',
                      'legal_authority_current', 'legal_deadlines_verified',
                      'outbound_ai_transmission'):
            if summary.get(field) is not False:
                raise PreviewRejected('Cannot claim legal verification or external AI transmission')
        if summary.get('human_review_not_legal_verification') is not True:
            raise PreviewRejected('Human review disclaimer required')
        counts = summary.get('research_status_counts')
        if not isinstance(counts, dict) or set(counts) != {s for s, _ in _STATUSES}:
            raise PreviewRejected('Invalid research status counts')
        for name in ('open_task_count', 'past_user_entered_date_count',
                     'research_source_count', 'unresolved_research_count'):
            n = summary.get(name)
            if type(n) is not int or not 0 <= n <= 100:
                raise PreviewRejected('Invalid readiness count')
        if summary['past_user_entered_date_count'] > summary['open_task_count'] or summary['unresolved_research_count'] > summary['research_source_count']:
            raise PreviewRejected('Inconsistent readiness counts')
        if any(type(counts[s]) is not int or not 0 <= counts[s] <= 100 for s, _ in _STATUSES):
            raise PreviewRejected('Invalid review count')
        if sum(counts.values()) != summary['research_source_count'] or (summary['research_source_count'] - counts['two_people_reviewed_unverified']) != summary['unresolved_research_count']:
            raise PreviewRejected('Inconsistent source totals')
        when = summary.get('as_of')
        if not isinstance(when, str) or not 1 <= len(when) <= 70:
            raise PreviewRejected('Invalid summary timestamp')
        # Counts only; never render matter title, task text, note, URL or excerpt.
        def li(label, number):
            return f'<li><span>{escape(label)}</span><strong>{number}</strong></li>'
        rows = ''.join(li(label, counts[key]) for key, label in _STATUSES)
        html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; connect-src &#39;none&#39;; script-src &#39;none&#39;; img-src &#39;none&#39;; form-action &#39;none&#39;; base-uri &#39;none&#39;">'
                '<title>Private Attorney Readiness</title>'
                '<style>body{font:1rem system-ui,sans-serif;max-width:38rem;margin:auto;padding:1rem;line-height:1.5}'
                'section{border:1px solid gray;border-radius:.7rem;padding:1rem;margin:1rem 0}'
                'li{display:flex;justify-content:space-between;gap:1rem;margin:.6rem 0}strong{font-variant-numeric:tabular-nums}'
                'summary{font-weight:700;cursor:pointer}small{display:block}</style></head><body>'
                '<h1>Private matter readiness</h1><p><strong>PROCEDURAL TRIAGE ONLY.</strong> Not legal advice, source verification, or court-filing approval.</p>'
                '<section><h2>Open work</h2><ul>'
                + li('Open tasks', summary['open_task_count'])
                + li('Past user-entered dates — NOT court deadlines', summary['past_user_entered_date_count'])
                + '</ul></section><section><h2>Research review</h2><ul>'
                + li('Sources needing further procedural work', summary['unresolved_research_count'])
                + '</ul><details><summary>Expand procedural breakdown</summary><ul>' + rows + '</ul></details></section>'
                '<small>Human review does not establish official origin, legal currency, citation treatment, or jurisdiction. No AI transmission. Generated: '
                + escape(when, quote=True) + '</small></body></html>')
        body = html.encode('utf-8')
        if len(body) > self.MAX_BYTES:
            raise PreviewRejected('Readiness view oversized')
        return PreviewResponse(200, _HEADERS + (('Content-Length', str(len(body))),), body)
