"""Fail-closed, read-only procedural research status; NEVER legal verification.

This module only projects statements made by local fictional human accounts.
It does not retrieve, authenticate, or validate legal authorities.
"""
from .research_evidence import EvidenceInvalid
from .source_observation import SourceObservation
from .second_source_review import SecondSourceReview


class SourceReleaseProjection:
    """Safely derive a single-matter research disposition from integrity-checked records."""

    MAX_SOURCES = 100

    def __init__(self, core):
        self.core = core
        self.observations = SourceObservation(core)
        self.reviews = SecondSourceReview(core)

    def project(self, token, matter_id):
        """No writes except demo SecureCore session last-seen bookkeeping.

        Never exposes actual excerpt, observation body, legal research note, or
        source URL. No decision here authorizes use in a court filing.
        """
        if not isinstance(matter_id, str) or not 1 <= len(matter_id) <= 64:
            raise EvidenceInvalid('Invalid matter identifier')
        with self.core.lock:
            actor = self.core._identity(token)
            self.core._role(actor, matter_id, ('owner', 'editor', 'viewer'))
            evidence_ids = [r['id'] for r in self.core.db.execute(
                'SELECT id FROM research_evidence WHERE matter_id=? ORDER BY created_at,id LIMIT ?',
                (matter_id, self.MAX_SOURCES + 1))]
            if len(evidence_ids) > self.MAX_SOURCES:
                raise EvidenceInvalid('Too many research sources; pagination required')
            results = []
            for eid in evidence_ids:
                # These independent read APIs recheck the source and every stored
                # observation/review fingerprint, raising if anything is inconsistent.
                observations = self.observations.history(token, matter_id, eid)['observations']
                reviews = self.reviews.history(token, matter_id, eid)['second_reviews']
                if not observations:
                    status, latest = 'needs_first_observation', None
                else:
                    latest = max(observations, key=lambda x: (x['recorded_at'], x['observation_id']))
                    matches = [r for r in reviews if r['observation_id'] == latest['observation_id']]
                    if not matches:
                        status = 'needs_independent_second_review'
                    elif len(matches) != 1:
                        raise EvidenceInvalid('Conflicting review records')
                    else:
                        decision = matches[0]['decision']
                        status = {
                            'corroborated_manually': 'two_people_reviewed_unverified',
                            'needs_further_review': 'needs_additional_review',
                            'rejected': 'rejected_by_second_reviewer',
                        }.get(decision)
                        if status is None:
                            raise EvidenceInvalid('Unknown review decision')
                results.append({
                    'evidence_id': eid,
                    'latest_observation_id': latest['observation_id'] if latest else None,
                    'procedural_status': status,
                    'source_authenticated': False,
                    'legal_authority_current': False,
                    'usable_without_attorney_validation': False,
                })
            return {
                'schema': 'mtl.source.review_projection.v1',
                'matter_id': matter_id,
                'sources': results,
                'court_filing_approved': False,
                'legal_authorities_verified_by_software': False,
                'outbound_ai_transmission': False,
                'notice': 'Human-account assertions only; independently authenticate official sources, jurisdiction, citation treatment and current law before reliance.',
            }
