"""Offline, matter-scoped intake of supplied legal-source bytes.

Configured HTTPS host names are a *routing allowlist*, NOT proof of a court source.
No website is fetched; no legal authority's validity or currency is asserted.
"""
import hashlib
import ipaddress
import json
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .research_evidence import EvidenceInvalid


def _safe_host(host):
    if not isinstance(host, str) or not 4 <= len(host) <= 253 or host != host.lower():
        raise EvidenceInvalid('Invalid configured host')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise EvidenceInvalid('IP literals are not approved hosts')
    labels = host.split('.')
    if len(labels) < 2 or any(not label or len(label) > 63 or label[0] == '-' or label[-1] == '-' or
                              any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in label)
                              for label in labels):
        raise EvidenceInvalid('Invalid configured DNS host')
    return host


def _url_host(url):
    if not isinstance(url, str) or len(url) > 1500 or any(ord(c) < 33 or ord(c) > 126 for c in url):
        raise EvidenceInvalid('Invalid source URL')
    try:
        p = urlsplit(url)
        if p.scheme != 'https' or not p.netloc or p.username is not None or p.password is not None:
            raise EvidenceInvalid('HTTPS URL with no userinfo required')
        if p.port not in (None, 443) or p.fragment or '\\' in url:
            raise EvidenceInvalid('Unsafe source URL')
        if p.hostname is None or p.hostname != p.hostname.lower() or p.hostname != p.netloc.split(':')[0].lower():
            raise EvidenceInvalid('Invalid source host')
        return _safe_host(p.hostname)
    except (ValueError, AttributeError) as e:
        raise EvidenceInvalid('Malformed source URL') from e


class OfficialSourceIntake:
    """Capture offline supplied document bytes, never verify source authenticity."""
    MAX_BYTES = 128 * 1024

    def __init__(self, core, approved_hosts):
        self.core = core
        if not isinstance(approved_hosts, (list, tuple, frozenset)) or not (1 <= len(approved_hosts) <= 50):
            raise EvidenceInvalid('Explicit approved host list required')
        self.approved_hosts = frozenset(_safe_host(h) for h in approved_hosts)
        with core.lock, core.db:
            core.db.execute('''CREATE TABLE IF NOT EXISTS official_source_intake (
              id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
              actor_id TEXT NOT NULL, source_url TEXT NOT NULL, host TEXT NOT NULL,
              document_digest TEXT NOT NULL, document_size INTEGER NOT NULL,
              evidence_digest TEXT NOT NULL, reviewed_note TEXT NOT NULL,
              captured_at TEXT NOT NULL, record_digest TEXT NOT NULL)''')
            core.db.execute('CREATE INDEX IF NOT EXISTS osi_scope ON official_source_intake(matter_id,evidence_id)')

    @staticmethod
    def _hash(item):
        return hashlib.sha256(json.dumps(item, sort_keys=True, separators=(',', ':'),
                                         ensure_ascii=False).encode('utf-8')).hexdigest()

    def record(self, token, matter_id, evidence_id, url, document, note):
        host = _url_host(url)
        if host not in self.approved_hosts:
            raise EvidenceInvalid('Source host not explicitly allowed')
        if not isinstance(document, bytes) or not 1 <= len(document) <= self.MAX_BYTES:
            raise EvidenceInvalid('Document bytes must be nonempty and bounded')
        if not isinstance(note, str) or not 15 <= len(note.strip()) <= 1200:
            raise EvidenceInvalid('Human source review note required')
        with self.core.lock, self.core.db:
            user = self.core._identity(token)
            self.core._role(user, matter_id, ('owner', 'editor'))
            row = self.core.db.execute('''SELECT title,url,excerpt,content_digest FROM research_evidence
                WHERE id=? AND matter_id=?''',(evidence_id,matter_id)).fetchone()
            if row is None:
                raise EvidenceInvalid('Source not found in permitted matter')
            source_digest = hashlib.sha256(json.dumps([row['title'], row['url'], row['excerpt']],
                                                separators=(',', ':')).encode()).hexdigest()
            if source_digest != row['content_digest']:
                raise EvidenceInvalid('Original evidence integrity mismatch')
            data = {'id': secrets.token_hex(16), 'matter_id': matter_id, 'evidence_id': evidence_id,
                    'actor_id': user['id'], 'source_url': url, 'host': host,
                    'document_digest': hashlib.sha256(document).hexdigest(),
                    'document_size': len(document), 'evidence_digest': source_digest,
                    'reviewed_note': note.strip(), 'captured_at': datetime.now(timezone.utc).isoformat()}
            fingerprint = self._hash(data)
            self.core.db.execute('''INSERT INTO official_source_intake VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                                 (*data.values(), fingerprint))
            self.core._audit(user['id'], 'research.offline_official_source_intake', data['id'])
            return {'record_id': data['id'], 'document_sha256': data['document_digest'],
                    'configured_host_matched': True, 'official_source_authenticated': False,
                    'legal_authority_current': False, 'network_accessed': False}

    def list_records(self, token, matter_id, evidence_id):
        with self.core.lock:
            user = self.core._identity(token)
            self.core._role(user, matter_id, ('owner','editor','viewer'))
            row = self.core.db.execute('SELECT content_digest FROM research_evidence WHERE id=? AND matter_id=?',
                                       (evidence_id,matter_id)).fetchone()
            if row is None: raise EvidenceInvalid('Evidence not found')
            rows = self.core.db.execute('SELECT * FROM official_source_intake WHERE matter_id=? AND evidence_id=? ORDER BY captured_at,id LIMIT 102',
                                        (matter_id,evidence_id)).fetchall()
            if len(rows) > 100: raise EvidenceInvalid('Too many observations')
            results = []
            for row_data in rows:
                data = dict(row_data)
                expected = data.pop('record_digest')
                if data['evidence_digest'] != row['content_digest'] or self._hash(data) != expected:
                    raise EvidenceInvalid('Source intake record integrity mismatch')
                results.append({'record_id': data['id'], 'document_sha256': data['document_digest'],
                                'source_url': data['source_url'], 'actor_id': data['actor_id'],
                                'reviewed_note': data['reviewed_note'], 'captured_at': data['captured_at'],
                                'official_source_authenticated': False, 'legal_authority_current': False})
            return {'records':results, 'official_source_authenticated':False,
                    'legal_authority_current':False,
                    'notice':'Offline supplied bytes only; configured host match is not verification of original origin, citation treatment or currency.'}
