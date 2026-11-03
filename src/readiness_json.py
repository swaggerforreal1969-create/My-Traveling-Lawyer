"""Authenticated, offline, minimal JSON matter-readiness view.

This is an in-process adapter only; it does not open HTTP endpoints or send data.
A human review never certifies legal authority, deadlines or filing readiness.
"""
import json
from datetime import datetime
from .matter_readiness import MatterReadiness
from .mobile_preview_gateway import PreviewRejected, PreviewResponse


class ReadinessJSON:
    """Return only bounded counts and false legal-verification assertions."""
    MAX_BYTES = 8192
    STATUSES = tuple(sorted(MatterReadiness.STATUSES))

    def __init__(self, core):
        self.readiness = MatterReadiness(core)

    def prepare(self, token, matter_id, *, now=None):
        if not isinstance(token, str) or not 32 <= len(token) <= 512:
            raise PreviewRejected('Credential required')
        if not isinstance(matter_id, str) or not 1 <= len(matter_id) <= 64:
            raise PreviewRejected('Invalid matter')
        if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
            raise PreviewRejected('Timezone-aware time required')
        source = self.readiness.summarize(token, matter_id, now=now)
        if (type(source) is not dict or source.get('schema') != 'mtl.matter.readiness.v1'
                or source.get('matter_id') != matter_id):
            raise PreviewRejected('Inconsistent matter')
        for flag in ('source_authenticated', 'legal_authority_current',
                     'court_filing_approved', 'legal_deadlines_verified', 'outbound_ai_transmission'):
            if source.get(flag) is not False:
                raise PreviewRejected('Unsafe legal or outbound claim')
        if source.get('human_review_not_legal_verification') is not True:
            raise PreviewRejected('Legal disclaimer required')
        totals = source.get('research_status_counts')
        if type(totals) is not dict or set(totals) != set(self.STATUSES):
            raise PreviewRejected('Unexpected source status')
        for key in ('open_task_count', 'past_user_entered_date_count',
                    'research_source_count', 'unresolved_research_count'):
            if type(source.get(key)) is not int or not 0 <= source[key] <= 100:
                raise PreviewRejected('Unsafe task or source count')
        if any(type(totals[k]) is not int or not 0 <= totals[k] <= 100 for k in self.STATUSES):
            raise PreviewRejected('Invalid status count')
        if (sum(totals.values()) != source['research_source_count']
                or source['unresolved_research_count'] != source['research_source_count'] - totals['two_people_reviewed_unverified']
                or source['past_user_entered_date_count'] > source['open_task_count']):
            raise PreviewRejected('Conflicting status counts')
        # Do not return matter IDs, evidence IDs, matter titles, notes, deadlines,
        # observations, URLs, timestamps or even client-supplied identifiers.
        public = {
            'schema': 'mtl.private.readiness.counts.v1',
            'open_tasks': source['open_task_count'],
            'past_user_entered_dates_not_court_deadlines': source['past_user_entered_date_count'],
            'research_sources': source['research_source_count'],
            'research_needing_procedural_work': source['unresolved_research_count'],
            'review_counts': {k: totals[k] for k in self.STATUSES},
            'legal_source_authenticated': False,
            'legal_deadlines_verified': False,
            'court_filing_approved': False,
            'outbound_ai_transmission': False,
            'human_review_is_legal_verification': False,
        }
        body = json.dumps(public, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
        if len(body) > self.MAX_BYTES:
            raise PreviewRejected('JSON response too large')
        headers = (
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, private'),
            ('Pragma', 'no-cache'), ('X-Content-Type-Options', 'nosniff'),
            ('Referrer-Policy', 'no-referrer'),
            ('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'"),
            ('X-Frame-Options', 'DENY'),
            ('Content-Length', str(len(body))),
        )
        return PreviewResponse(200, headers, body)
