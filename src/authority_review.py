"""Append-only, access-controlled human review of fictional research evidence.

This module DOES NOT fetch, authenticate, or validate current legal authority.
It records an attorney's manual assessment, scoped to an existing matter.
"""
import hashlib
import json
import secrets
from datetime import datetime, timezone

from .research_evidence import EvidenceInvalid


class AuthorityReview:
    DECISIONS = frozenset(('checked_against_original', 'needs_recheck', 'rejected'))

    def __init__(self, core):
        self.core = core
        with core.lock, core.db:
            core.db.execute('''CREATE TABLE IF NOT EXISTS authority_review_events (
                event_id TEXT PRIMARY KEY, matter_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL, reviewer_id TEXT NOT NULL,
                decision TEXT NOT NULL, review_note TEXT NOT NULL,
                evidence_digest TEXT NOT NULL, reviewed_at TEXT NOT NULL)''')
            core.db.execute('''CREATE INDEX IF NOT EXISTS idx_authority_review_scope
                ON authority_review_events(matter_id, evidence_id, reviewed_at)''')

    @staticmethod
    def _expected_digest(row):
        content = [row['title'], row['url'], row['excerpt']]
        return hashlib.sha256(json.dumps(content, separators=(',', ':')).encode()).hexdigest()

    def record(self, token, matter_id, evidence_id, decision, review_note):
        if decision not in self.DECISIONS:
            raise EvidenceInvalid('Unknown review decision')
        if not isinstance(review_note, str) or not 10 <= len(review_note.strip()) <= 1500:
            raise EvidenceInvalid('Review note must contain 10-1500 characters')
        if not isinstance(evidence_id, str) or len(evidence_id) != 32 or any(c not in '0123456789abcdef' for c in evidence_id):
            raise EvidenceInvalid('Invalid evidence id')
        with self.core.lock, self.core.db:
            user = self.core._identity(token)
            self.core._role(user, matter_id, ('owner', 'editor'))
            row = self.core.db.execute('''SELECT title, url, excerpt, content_digest
                    FROM research_evidence WHERE id=? AND matter_id=?''',
                    (evidence_id, matter_id)).fetchone()
            if row is None:
                raise EvidenceInvalid('Evidence not found in permitted matter')
            if self._expected_digest(row) != row['content_digest']:
                raise EvidenceInvalid('Evidence integrity mismatch')
            event_id = secrets.token_hex(16)
            at = datetime.now(timezone.utc).isoformat()
            self.core.db.execute('''INSERT INTO authority_review_events
                (event_id, matter_id, evidence_id, reviewer_id, decision, review_note, evidence_digest, reviewed_at)
                VALUES (?,?,?,?,?,?,?,?)''',
                (event_id, matter_id, evidence_id, user['id'], decision, review_note.strip(), row['content_digest'], at))
            self.core._audit(user['id'], 'research.human_review', event_id)
            return {'event_id': event_id, 'evidence_id': evidence_id, 'decision': decision,
                    'reviewed_at': at, 'human_attestation_recorded': True,
                    'source_authenticated_by_software': False,
                    'legal_authority_verified_by_software': False}

    def history(self, token, matter_id, evidence_id):
        with self.core.lock:
            user = self.core._identity(token)
            self.core._role(user, matter_id, ('owner', 'editor', 'viewer'))
            row = self.core.db.execute('''SELECT id FROM research_evidence WHERE id=? AND matter_id=?''',
                                       (evidence_id, matter_id)).fetchone()
            if row is None:
                raise EvidenceInvalid('Evidence not found in permitted matter')
            records = [dict(r) for r in self.core.db.execute('''SELECT event_id, reviewer_id, decision,
                 review_note, evidence_digest, reviewed_at FROM authority_review_events
                 WHERE matter_id=? AND evidence_id=? ORDER BY reviewed_at, event_id''',
                 (matter_id, evidence_id))]
            return {'evidence_id': evidence_id, 'reviews': records,
                    'source_authenticated_by_software': False,
                    'legal_authority_verified_by_software': False,
                    'notice': 'Manual reviewer statements only. Independently check the original authority, jurisdiction, validity and currency.'}
