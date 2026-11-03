"""Bounded, read-only local research-write reconciliation, fictional/offline only.

Not independent custody, not proof of official-law authenticity. Does not replay,
authorize, or perform any research write. A missing or corrupt record fails closed.
"""
from dataclasses import dataclass
import hashlib
import json
from .secure_engine import Denied, Invalid
from .research_evidence import EvidenceInvalid
from .source_observation import _digest


@dataclass(frozen=True)
class ResearchWriteObservation:
    status: str = 'observed_local_commit'
    operation: str = ''
    official_source_authenticated: bool = False
    legal_authority_current: bool = False
    court_filing_approved: bool = False
    independent_audit_verified: bool = False


_TARGETS = {
    'source.add': ('research_evidence', 'id', 'research.evidence_add'),
    'source.observe': ('source_observation', 'observation_id', 'research.manual_source_observation'),
    'source.second_review': ('source_second_review', 'id', 'research.second_source_review'),
}


def reconcile_research_write(core, token, matter_id, operation, record_id):
    """Require an actor-owned matching local record and exact local audit event.

    Reject absent records identically to out-of-scope records. Local DB records
    and its audit history may roll back together: this cannot rule out rollback.
    """
    if (not isinstance(matter_id, str) or not 1 <= len(matter_id) <= 64
            or operation not in _TARGETS
            or not isinstance(record_id, str) or len(record_id) != 32
            or any(c not in '0123456789abcdef' for c in record_id)):
        raise Invalid('Invalid research reconciliation request')
    table, key, action = _TARGETS[operation]
    with core.lock:
        actor = core._identity(token)
        core._role(actor, matter_id, ('owner', 'editor'))
        row = core.db.execute(
            f'SELECT * FROM {table} WHERE matter_id=? AND {key}=?',
            (matter_id, record_id)).fetchone()
        if row is None:
            raise Denied('Access denied')
        data = dict(row)
        owner_field = 'author_id' if operation == 'source.add' else (
            'actor_id' if operation == 'source.observe' else 'reviewer_id')
        if data[owner_field] != actor['id']:
            raise Denied('Access denied')
        if not core.verify_audit():
            raise Invalid('Local audit verification failed')
        events = core.db.execute(
            "SELECT actor_id FROM audit_chain WHERE action=? AND target=?",
            (action, record_id)).fetchall()
        if len(events) != 1 or events[0]['actor_id'] != actor['id']:
            raise Invalid('Missing or conflicting local research audit event')

        if operation == 'source.add':
            canonical = json.dumps(
                [data['title'], data['url'], data['excerpt']],
                separators=(',', ':')).encode()
            digest = hashlib.sha256(canonical).hexdigest()
            if digest != data['content_digest']:
                raise Invalid('Research evidence integrity mismatch')
        else:
            digest = data.pop('record_digest')
            if _digest(data) != digest:
                raise Invalid('Manual research record integrity mismatch')
            if operation == 'source.observe':
                if hashlib.sha256(data['captured_text'].encode()).hexdigest() != data['captured_digest']:
                    raise Invalid('Observation content mismatch')
                source = core.db.execute(
                    'SELECT title,url,excerpt,content_digest FROM research_evidence WHERE matter_id=? AND id=?',
                    (matter_id, data['evidence_id'])).fetchone()
                if source is None:
                    raise Invalid('Missing parent evidence')
                src_digest = hashlib.sha256(json.dumps(
                    [source['title'], source['url'], source['excerpt']],
                    separators=(',', ':')).encode()).hexdigest()
                if src_digest != source['content_digest'] or data['evidence_digest'] != src_digest:
                    raise Invalid('Observation source binding mismatch')
            else:
                obs = core.db.execute(
                    'SELECT * FROM source_observation WHERE matter_id=? AND observation_id=? AND evidence_id=?',
                    (matter_id, data['observation_id'], data['evidence_id'])).fetchone()
                if obs is None:
                    raise Invalid('Missing review observation')
                original = dict(obs)
                original_hash = original.pop('record_digest')
                if (_digest(original) != original_hash
                        or data['observation_digest'] != original_hash
                        or data['original_actor_id'] != original['actor_id']
                        or data['reviewer_id'] == data['original_actor_id']
                        or data['decision'] not in ('corroborated_manually', 'needs_further_review', 'rejected')):
                    raise Invalid('Review source integrity mismatch')
        return ResearchWriteObservation(operation=operation)
