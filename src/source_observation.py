"""Local custody of *manual* legal-source observations; never external verification.

No network access. An observation is evidence that an authenticated operator entered
particular content, not evidence of authenticity, treatment, jurisdiction or currency.
"""
import hashlib
import json
import secrets
from datetime import datetime, timezone
from .research_evidence import EvidenceInvalid


def _digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


class SourceObservation:
    MAX_BODY = 12000

    def __init__(self, core):
        self.core = core
        with core.lock, core.db:
            core.db.execute('''CREATE TABLE IF NOT EXISTS source_observation (
                observation_id TEXT PRIMARY KEY, matter_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                evidence_digest TEXT NOT NULL, captured_text TEXT NOT NULL,
                captured_digest TEXT NOT NULL, note TEXT NOT NULL,
                recorded_at TEXT NOT NULL, record_digest TEXT NOT NULL)''')
            core.db.execute('''CREATE INDEX IF NOT EXISTS source_observation_scope
                ON source_observation(matter_id,evidence_id,recorded_at)''')

    def _source(self, matter_id, evidence_id):
        row = self.core.db.execute('''SELECT title,url,excerpt,content_digest
             FROM research_evidence WHERE matter_id=? AND id=?''',
             (matter_id, evidence_id)).fetchone()
        if row is None:
            raise EvidenceInvalid('No evidence in authorized matter')
        if _digest([row['title'], row['url'], row['excerpt']]) != row['content_digest']:
            # Original research notebook uses compact JSON with list ordering, not sort_keys;
            # sort_keys has no effect on lists.
            raise EvidenceInvalid('Evidence digest mismatch')
        return row

    def capture(self, token, matter_id, evidence_id, captured_text, note):
        if not isinstance(captured_text, str) or not (1 <= len(captured_text.strip()) <= self.MAX_BODY):
            raise EvidenceInvalid('Invalid captured text')
        if not isinstance(note, str) or not (12 <= len(note.strip()) <= 1200):
            raise EvidenceInvalid('Observation must include a manual evidence note')
        if not isinstance(evidence_id, str) or len(evidence_id) != 32 or any(c not in '0123456789abcdef' for c in evidence_id):
            raise EvidenceInvalid('Invalid evidence identifier')
        with self.core.authorized_transaction():
            actor = self.core._identity(token)
            self.core._role(actor, matter_id, ('owner', 'editor'))
            source = self._source(matter_id, evidence_id)
            record = {
                'observation_id': secrets.token_hex(16), 'matter_id': matter_id,
                'evidence_id': evidence_id, 'actor_id': actor['id'],
                'evidence_digest': source['content_digest'],
                'captured_text': captured_text.strip(),
                'captured_digest': hashlib.sha256(captured_text.strip().encode('utf-8')).hexdigest(),
                'note': note.strip(), 'recorded_at': datetime.now(timezone.utc).isoformat(),
            }
            digest = _digest(record)
            self.core.db.execute('''INSERT INTO source_observation VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (record['observation_id'], record['matter_id'], record['evidence_id'],
                 record['actor_id'], record['evidence_digest'], record['captured_text'],
                 record['captured_digest'], record['note'], record['recorded_at'], digest))
            self.core._audit(actor['id'], 'research.manual_source_observation', record['observation_id'])
            return {'observation_id': record['observation_id'], 'record_digest': digest,
                    'local_record_integrity_checked': True, 'official_source_authenticated': False,
                    'current_legal_authority_verified': False, 'network_accessed': False}

    def history(self, token, matter_id, evidence_id):
        with self.core.authorized_transaction():
            actor = self.core._identity(token)
            self.core._role(actor, matter_id, ('owner', 'editor', 'viewer'))
            source = self._source(matter_id, evidence_id)
            rows = self.core.db.execute('''SELECT * FROM source_observation
                 WHERE matter_id=? AND evidence_id=? ORDER BY recorded_at,observation_id LIMIT 102''',
                 (matter_id, evidence_id)).fetchall()
            if len(rows) > 100:
                raise EvidenceInvalid('Too many source observations; paginate before export')
            results = []
            for row in rows:
                d = dict(row)
                expected = d.pop('record_digest')
                if d['evidence_digest'] != source['content_digest']:
                    raise EvidenceInvalid('Observation bound to wrong research digest')
                if hashlib.sha256(d['captured_text'].encode('utf-8')).hexdigest() != d['captured_digest']:
                    raise EvidenceInvalid('Manual observation text changed')
                if _digest(d) != expected:
                    raise EvidenceInvalid('Manual observation record altered')
                # Deliberately avoid exposing full captured text from a history metadata response.
                results.append({'observation_id': d['observation_id'],
                                'recorded_at': d['recorded_at'], 'actor_id': d['actor_id'],
                                'captured_digest': d['captured_digest'],
                                'record_digest': expected, 'note': d['note'],
                                'official_source_authenticated': False,
                                'current_legal_authority_verified': False})
            return {'observations': results, 'local_hash_integrity': True,
                    'official_source_authenticated': False,
                    'current_legal_authority_verified': False,
                    'notice': 'Manual observation only; check official website, jurisdiction, subsequent treatment and currency independently.'}
