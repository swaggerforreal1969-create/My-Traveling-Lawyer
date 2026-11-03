"""Fictional-only matter research notebook. NEVER labels an external legal source verified."""
import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit

class EvidenceInvalid(ValueError):
    pass

class ResearchEvidence:
    def __init__(self, core):
        self.core=core
        with core.lock, core.db:
            core.db.execute('''CREATE TABLE IF NOT EXISTS research_evidence (
              id TEXT PRIMARY KEY, matter_id TEXT NOT NULL, author_id TEXT NOT NULL,
              title TEXT NOT NULL, url TEXT NOT NULL, excerpt TEXT NOT NULL,
              content_digest TEXT NOT NULL, created_at TEXT NOT NULL)''')

    @staticmethod
    def clean(title,url,excerpt):
        if not isinstance(title,str) or not 1<=len(title.strip())<=180:raise EvidenceInvalid('Invalid title')
        if not isinstance(excerpt,str) or not 1<=len(excerpt.strip())<=1500:raise EvidenceInvalid('Invalid excerpt')
        if not isinstance(url,str) or len(url)>1200:raise EvidenceInvalid('Invalid URL')
        p=urlsplit(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment or p.port not in (None,443):raise EvidenceInvalid('HTTPS source URL required')
        if p.hostname.lower() in ('localhost','127.0.0.1','::1') or p.hostname.lower().endswith('.local'):
            raise EvidenceInvalid('Public source URL required')
        return title.strip(),url,excerpt.strip()

    def add(self,token,matter_id,title,url,excerpt):
        title,url,excerpt=self.clean(title,url,excerpt)
        with self.core.lock,self.core.db:
            ident=self.core._identity(token)
            self.core._role(ident,matter_id,('owner','editor'))
            entry_id=secrets.token_hex(16)
            digest=hashlib.sha256(json.dumps([title,url,excerpt],separators=(',',':')).encode()).hexdigest()
            self.core.db.execute('INSERT INTO research_evidence VALUES(?,?,?,?,?,?,?,?)',
                (entry_id,matter_id,ident['id'],title,url,excerpt,digest,datetime.now(timezone.utc).isoformat()))
            self.core._audit(ident['id'],'research.evidence_add',entry_id)
            return {'id':entry_id,'content_digest':digest,'source_verified':False,'legal_authority_verified':False}

    def list(self,token,matter_id):
        with self.core.lock:
            ident=self.core._identity(token)
            self.core._role(ident,matter_id,('owner','editor','viewer'))
            rows=self.core.db.execute('SELECT id,title,url,excerpt,content_digest,created_at FROM research_evidence WHERE matter_id=? ORDER BY created_at,id',(matter_id,)).fetchall()
            return {'sources':[dict(r,source_verified=False,legal_authority_verified=False) for r in rows],
                'notice':'User-entered excerpts only. Check original official authorities and currency independently.'}
