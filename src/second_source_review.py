"""Two distinct human accounts must review one offline source observation.

This is procedural review only. It does not authenticate websites, citations,
legal status, jurisdiction or independent custody, and never uses the network.
"""
import hashlib
import json
import secrets
from datetime import datetime, timezone
from .research_evidence import EvidenceInvalid
from .source_observation import SourceObservation, _digest


class SecondSourceReview:
    DECISIONS = frozenset(('corroborated_manually', 'needs_further_review', 'rejected'))

    def __init__(self, core):
        self.core = core
        self.observations = SourceObservation(core)
        with core.lock, core.db:
            core.db.execute('''CREATE TABLE IF NOT EXISTS source_second_review (
                id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
                observation_id TEXT NOT NULL UNIQUE, original_actor_id TEXT NOT NULL,
                reviewer_id TEXT NOT NULL, observation_digest TEXT NOT NULL,
                decision TEXT NOT NULL, note TEXT NOT NULL,
                recorded_at TEXT NOT NULL, record_digest TEXT NOT NULL)''')

    def record(self, token, matter_id, evidence_id, observation_id, decision, note):
        if decision not in self.DECISIONS:
            raise EvidenceInvalid('Unrecognized second-review decision')
        if not isinstance(note, str) or not (15 <= len(note.strip()) <= 1200):
            raise EvidenceInvalid('Second reviewer note required')
        if not isinstance(observation_id, str) or len(observation_id) != 32 or any(
                c not in '0123456789abcdef' for c in observation_id):
            raise EvidenceInvalid('Invalid observation identifier')
        with self.core.lock, self.core.db:
            reviewer = self.core._identity(token)
            self.core._role(reviewer, matter_id, ('owner', 'editor'))
            # Verify the original source and every observation before relying on it.
            self.observations.history(token, matter_id, evidence_id)
            row = self.core.db.execute('''SELECT * FROM source_observation
                WHERE observation_id=? AND matter_id=? AND evidence_id=?''',
                (observation_id, matter_id, evidence_id)).fetchone()
            if row is None:
                raise EvidenceInvalid('Observation not found in matter')
            prior = dict(row)
            digest = prior.pop('record_digest')
            if _digest(prior) != digest:
                raise EvidenceInvalid('Original observation corrupted')
            if prior['actor_id'] == reviewer['id']:
                raise EvidenceInvalid('Independent second user required')
            if self.core.db.execute('SELECT 1 FROM source_second_review WHERE observation_id=?',
                                    (observation_id,)).fetchone() is not None:
                raise EvidenceInvalid('Observation already countersigned')
            entry = {'id': secrets.token_hex(16), 'matter_id': matter_id,
                     'evidence_id': evidence_id, 'observation_id': observation_id,
                     'original_actor_id': prior['actor_id'], 'reviewer_id': reviewer['id'],
                     'observation_digest': digest, 'decision': decision,
                     'note': note.strip(), 'recorded_at': datetime.now(timezone.utc).isoformat()}
            fingerprint = _digest(entry)
            self.core.db.execute('''INSERT INTO source_second_review VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                                 (*entry.values(), fingerprint))
            self.core._audit(reviewer['id'], 'research.second_source_review', entry['id'])
            return {'review_id': entry['id'], 'second_human_account': True,
                    'decision': decision, 'official_source_authenticated': False,
                    'legal_authority_current': False}

    def history(self, token, matter_id, evidence_id):
        with self.core.lock:
            actor = self.core._identity(token)
            self.core._role(actor, matter_id, ('owner', 'editor', 'viewer'))
            # Read-only integrity validation; viewer cannot add a countersignature.
            observed = self.observations.history(token, matter_id, evidence_id)
            originals = {r['observation_id']: r for r in observed['observations']}
            rows = self.core.db.execute('''SELECT * FROM source_second_review
                WHERE matter_id=? AND evidence_id=? ORDER BY recorded_at,id LIMIT 102''',
                (matter_id, evidence_id)).fetchall()
            if len(rows) > 100:
                raise EvidenceInvalid('Too many second reviews')
            results = []
            for row in rows:
                d = dict(row)
                expected = d.pop('record_digest')
                original = originals.get(d['observation_id'])
                if (original is None or d['observation_digest'] != original['record_digest']
                        or d['original_actor_id'] != original['actor_id']
                        or d['reviewer_id'] == d['original_actor_id']
                        or d['decision'] not in self.DECISIONS or _digest(d) != expected):
                    raise EvidenceInvalid('Second-review history integrity mismatch')
                results.append({'review_id': d['id'], 'observation_id': d['observation_id'],
                                'decision': d['decision'], 'reviewer_id': d['reviewer_id'],
                                'original_actor_id': d['original_actor_id'],
                                'recorded_at': d['recorded_at'],
                                'official_source_authenticated': False,
                                'legal_authority_current': False})
            return {'second_reviews': results, 'official_source_authenticated': False,
                    'legal_authority_current': False,
                    'notice': 'Two local human-account statements do not verify external authenticity or the current status of a law.'}
