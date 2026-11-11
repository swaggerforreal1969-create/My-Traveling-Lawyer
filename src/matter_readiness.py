"""Confidential single-matter attorney work queue: no verification or outbound calls.

Only derived counts and procedural statuses are returned. MatterBrief and
SourceReleaseProjection perform real, independent ACL and record checks.
"""
from collections import Counter
from datetime import datetime, timezone

from .matter_brief import MatterBrief
from .research_evidence import EvidenceInvalid
from .source_release_projection import SourceReleaseProjection

class MatterReadiness:
    STATUSES = frozenset({
        'needs_first_observation', 'needs_independent_second_review',
        'needs_additional_review', 'rejected_by_second_reviewer',
        'two_people_reviewed_unverified',
    })

    def __init__(self, core):
        self.core = core
        self.briefing = MatterBrief(core)
        self.sources = SourceReleaseProjection(core)

    def summarize(self, token, matter_id, *, now=None):
        """Fail closed: never present stale or incomplete projections as court-ready."""
        if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
            raise EvidenceInvalid('Timezone-aware reference time required')
        with self.core.authorized_transaction():
            brief = self.briefing.prepare(token, matter_id, now=now)
            disposition = self.sources.project(token, matter_id)
            if (brief.get('matter_id') != disposition.get('matter_id') or
                brief.get('legal_authorities_verified_by_software') is not False or
                brief.get('legal_deadlines_verified') is not False or
                disposition.get('court_filing_approved') is not False or
                disposition.get('outbound_ai_transmission') is not False):
                raise EvidenceInvalid('Inconsistent confidentiality or verification flags')
            source_ids = [x['id'] for x in brief['research_sources']]
            disposition_ids = [x['evidence_id'] for x in disposition['sources']]
            if len(source_ids) != len(set(source_ids)) or set(source_ids) != set(disposition_ids) or len(disposition_ids) != len(set(disposition_ids)):
                raise EvidenceInvalid('Research projections do not match')
            statuses = []
            for entry in disposition['sources']:
                s = entry.get('procedural_status')
                if (s not in self.STATUSES or entry.get('source_authenticated') is not False or
                    entry.get('legal_authority_current') is not False or
                    entry.get('usable_without_attorney_validation') is not False):
                    raise EvidenceInvalid('Unsafe research disposition')
                statuses.append({'evidence_id':entry['evidence_id'], 'procedural_status':s})
            if len(brief['open_tasks']) > 100 or len(statuses) > 100:
                raise EvidenceInvalid('Exceeded bounded work queue')
            tasks_past = sum(x['past_user_entered_due_time'] is True for x in brief['open_tasks'])
            if any(type(x.get('past_user_entered_due_time')) is not bool for x in brief['open_tasks']):
                raise EvidenceInvalid('Invalid task urgency')
            counts = Counter(s['procedural_status'] for s in statuses)
            return {
                'schema':'mtl.matter.readiness.v1', 'matter_id':matter_id,
                'matter_version':brief['matter_version'], 'as_of':brief['as_of'],
                'open_task_count':len(brief['open_tasks']),
                'past_user_entered_date_count':tasks_past,
                'research_source_count':len(statuses),
                'research_status_counts':{s:counts[s] for s in sorted(self.STATUSES)},
                'research_statuses':statuses,
                'unresolved_research_count':len(statuses) - counts['two_people_reviewed_unverified'],
                'human_review_not_legal_verification':True,
                'source_authenticated':False, 'legal_authority_current':False,
                'court_filing_approved':False, 'legal_deadlines_verified':False,
                'outbound_ai_transmission':False,
                'notice':'Procedural triage only; attorney must independently verify the source, legal treatment, jurisdiction and all deadlines.'
            }
