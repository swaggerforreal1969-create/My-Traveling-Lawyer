"""Local-only, access-controlled attorney matter preparation snapshot.

No automatic legal deadline or authority verification. No AI/network transmission.
"""
from datetime import datetime, timezone
import hashlib
import json

from .research_evidence import EvidenceInvalid


class MatterBrief:
    MAX_NOTES = 100
    MAX_TASKS = 100
    MAX_SOURCES = 100

    def __init__(self, core):
        self.core = core

    @staticmethod
    def _digest(row):
        return hashlib.sha256(json.dumps(
            [row['title'], row['url'], row['excerpt']], separators=(',', ':')
        ).encode()).hexdigest()

    def prepare(self, token, matter_id, *, now=None):
        """Read-only briefing for a single authorized matter, with explicit open risks."""
        if not isinstance(matter_id, str) or not (1 <= len(matter_id) <= 64):
            raise EvidenceInvalid('Invalid matter identifier')
        if now is None:
            now = datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise EvidenceInvalid('Timezone-aware briefing time required')
        at = now.astimezone(timezone.utc).isoformat()
        with self.core.lock:
            actor = self.core._identity(token)
            self.core._role(actor, matter_id, ('owner', 'editor', 'viewer'))
            matter = self.core.db.execute(
                'SELECT title, version FROM matters WHERE id=? AND firm_id=?',
                (matter_id, actor['firm_id'])
            ).fetchone()
            if matter is None:
                raise EvidenceInvalid('Matter not found')
            notes = [dict(x) for x in self.core.db.execute(
                'SELECT id, text FROM notes WHERE matter_id=? ORDER BY id LIMIT ?',
                (matter_id, self.MAX_NOTES + 1)
            )]
            tasks = [dict(x) for x in self.core.db.execute(
                'SELECT id, text, due_at, completed, version FROM tasks WHERE matter_id=? ORDER BY due_at,id LIMIT ?',
                (matter_id, self.MAX_TASKS + 1)
            )]
            sources = [dict(x) for x in self.core.db.execute(
                'SELECT id,title,url,excerpt,content_digest FROM research_evidence WHERE matter_id=? ORDER BY id LIMIT ?',
                (matter_id, self.MAX_SOURCES + 1)
            )] if self._table_exists('research_evidence') else []
            if len(notes) > self.MAX_NOTES or len(tasks) > self.MAX_TASKS or len(sources) > self.MAX_SOURCES:
                raise EvidenceInvalid('Matter too large for bounded briefing; paginate before export')
            source_results = []
            for row in sources:
                if self._digest(row) != row['content_digest']:
                    raise EvidenceInvalid('Research evidence integrity mismatch')
                reviews = [dict(x) for x in self.core.db.execute(
                    'SELECT decision,reviewed_at,evidence_digest FROM authority_review_events '
                    'WHERE matter_id=? AND evidence_id=? ORDER BY reviewed_at DESC,event_id DESC',
                    (matter_id, row['id'])
                )] if self._table_exists('authority_review_events') else []
                matching = [r for r in reviews if r['evidence_digest'] == row['content_digest']]
                if len(matching) != len(reviews):
                    raise EvidenceInvalid('Review evidence digest mismatch')
                latest = matching[0] if matching else None
                source_results.append({
                    'id': row['id'], 'title': row['title'], 'url': row['url'],
                    'last_human_assessment': latest['decision'] if latest else 'not_reviewed',
                    'last_reviewed_at': latest['reviewed_at'] if latest else None,
                    'software_verified': False,
                })
            open_tasks = []
            for row in tasks:
                if row['completed']:
                    continue
                due = datetime.fromisoformat(row['due_at'])
                if due.tzinfo is None:
                    raise EvidenceInvalid('Stored task deadline lacks timezone')
                open_tasks.append({
                    'id': row['id'], 'text': row['text'], 'due_at': row['due_at'],
                    'past_user_entered_due_time': due.astimezone(timezone.utc) < now.astimezone(timezone.utc),
                    'version': row['version'],
                })
            risks = []
            if any(x['past_user_entered_due_time'] for x in open_tasks):
                risks.append('Some unfinished tasks have user-entered dates in the past; verify all court deadlines manually.')
            if any(x['last_human_assessment'] != 'checked_against_original' for x in source_results):
                risks.append('Some research sources lack a current positive human assessment; verify jurisdiction, treatment and currency.')
            risks.append('This briefing does not calculate court deadlines, verify legal authorities or provide legal advice.')
            return {
                'schema': 'mtl.matter.preparation.v1', 'matter_id': matter_id,
                'matter_title': matter['title'], 'matter_version': matter['version'],
                'as_of': at, 'notes': notes, 'open_tasks': open_tasks,
                'research_sources': source_results, 'risk_notices': risks,
                'legal_deadlines_verified': False, 'legal_authorities_verified_by_software': False,
                'outbound_ai_transmission': False,
            }

    def _table_exists(self, name):
        return self.core.db.execute(
            'SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', name)
        ).fetchone() is not None
