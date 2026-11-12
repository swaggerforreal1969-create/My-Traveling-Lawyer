"""Append-only correction of a fictional research observation; no external authority."""
from datetime import datetime, timezone
import secrets
from .research_evidence import EvidenceInvalid
from .source_observation import SourceObservation, _digest

class ResearchCorrection:
    def __init__(self, core):
        self.core = core
        self.observations = SourceObservation(core)
        with core.authorized_transaction():
            core.db.execute("""CREATE TABLE IF NOT EXISTS research_correction (
                id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
                prior_observation_id TEXT NOT NULL UNIQUE,
                new_observation_id TEXT NOT NULL UNIQUE,
                prior_digest TEXT NOT NULL, new_digest TEXT NOT NULL,
                actor_id TEXT NOT NULL, reason TEXT NOT NULL,
                recorded_at TEXT NOT NULL, record_digest TEXT NOT NULL)""")

    def history(self, token, matter_id, evidence_id):
        with self.core.authorized_transaction():
            records = self.observations.history(token, matter_id, evidence_id)['observations']
            by_id = {r['observation_id']: r for r in records}
            rows = self.core.db.execute(
                'SELECT * FROM research_correction WHERE matter_id=? AND evidence_id=? '
                'ORDER BY recorded_at,id LIMIT 102', (matter_id,evidence_id)).fetchall()
            if len(rows) > 100:
                raise EvidenceInvalid('Too many corrections; paginate first')
            old_seen, new_seen, result = set(), set(), []
            for row in rows:
                d = dict(row)
                fingerprint = d.pop('record_digest')
                old_id, new_id = d['prior_observation_id'], d['new_observation_id']
                old, new = by_id.get(old_id), by_id.get(new_id)
                if (old is None or new is None or old_id == new_id
                        or old_id in old_seen or new_id in new_seen
                        or old['record_digest'] != d['prior_digest']
                        or new['record_digest'] != d['new_digest']
                        or new['actor_id'] != d['actor_id']
                        or (new['recorded_at'],new_id) <= (old['recorded_at'],old_id)
                        or not 15 <= len(d['reason'].strip()) <= 1200
                        or _digest(d) != fingerprint):
                    raise EvidenceInvalid('Research correction integrity mismatch')
                old_seen.add(old_id)
                new_seen.add(new_id)
                result.append({'old_id':old_id,'new_id':new_id,'reason':d['reason'],
                               'record_digest':fingerprint})
            return {'corrections':result,'local_integrity_checked':True,
                    'official_source_authenticated':False}

    def record(self, token, matter_id, evidence_id, prior_id, captured, note, reason):
        if not isinstance(reason,str) or not 15 <= len(reason.strip()) <= 1200:
            raise EvidenceInvalid('Correction reason must be 15–1200 characters')
        if not isinstance(prior_id,str) or len(prior_id)!=32 or any(
                c not in '0123456789abcdef' for c in prior_id):
            raise EvidenceInvalid('Invalid original observation')
        if not isinstance(captured,str) or not 1 <= len(captured.strip()) <= 12000:
            raise EvidenceInvalid('Corrected source text required')
        if not isinstance(note,str) or not 12 <= len(note.strip()) <= 1200:
            raise EvidenceInvalid('Corrected source note required')
        with self.core.authorized_transaction():
            actor = self.core._identity(token)
            self.core._role(actor,matter_id,('owner','editor'))
            if not self.core.verify_audit():
                raise EvidenceInvalid('Local audit integrity failed')
            self.history(token,matter_id,evidence_id)
            records=self.observations.history(token,matter_id,evidence_id)['observations']
            latest=max(records,key=lambda x:(x['recorded_at'],x['observation_id']),
                       default=None)
            if latest is None or latest['observation_id']!=prior_id:
                raise EvidenceInvalid('Observation no longer current')
            if self.core.db.execute(
                'SELECT 1 FROM research_correction WHERE prior_observation_id=?',
                (prior_id,)).fetchone():
                raise EvidenceInvalid('Observation already corrected')
            fresh=self.observations.capture(token,matter_id,evidence_id,captured,note)
            rec={'id':secrets.token_hex(16),'matter_id':matter_id,
                 'evidence_id':evidence_id,'prior_observation_id':prior_id,
                 'new_observation_id':fresh['observation_id'],
                 'prior_digest':latest['record_digest'],
                 'new_digest':fresh['record_digest'],
                 'actor_id':actor['id'],'reason':reason.strip(),
                 'recorded_at':datetime.now(timezone.utc).isoformat()}
            self.core.db.execute('INSERT INTO research_correction VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                                 (*rec.values(),_digest(rec)))
            self.core._audit(actor['id'],'research.observation_correction',rec['id'])
            if not self.core.verify_audit():
                raise EvidenceInvalid('Correction audit failed')
            return {'correction_id':rec['id'],'observation_id':fresh['observation_id'],
                    'prior_id':prior_id,'new_independent_review_required':True,
                    'official_source_authenticated':False}
