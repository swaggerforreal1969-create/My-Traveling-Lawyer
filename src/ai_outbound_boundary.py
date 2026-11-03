"""Fail-closed fictional-template AI request preparation; no network implementation.

An explicit local opt-in grants a short-lived, matter-scoped, one-use release of an
immutable public fictional prompt. No note, research, matter title, or client data
is read or passed into the resulting payload. Not a deployed AI integration.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
import json


class OutboundDenied(ValueError):
    pass


class ConfidentialAIRequest:
    TEMPLATES = {
        'fictional_agenda': 'Create a three-point agenda for an invented legal office meeting with no real people, facts, cases or clients.',
        'fictional_intake': 'List five generic, fictional intake workflow questions. Do not assume real legal facts or provide legal advice.',
    }
    MAX_TTL = 120
    SCHEMA = 'mtl.fictional.ai.preflight.v1'

    def __init__(self, core):
        self.core = core
        with core.lock, core.db:
            core.db.execute('''CREATE TABLE IF NOT EXISTS fictional_ai_authorizations (
                grant_hash TEXT PRIMARY KEY, credential_hash TEXT NOT NULL,
                actor_id TEXT NOT NULL, firm_id TEXT NOT NULL,
                matter_id TEXT NOT NULL, template_id TEXT NOT NULL,
                expires_at TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0 CHECK(consumed IN (0,1))
            )''')

    def _authorize_matter(self, token, matter_id):
        if not isinstance(token, str) or not 32 <= len(token) <= 512:
            raise OutboundDenied('Valid credential required')
        if not isinstance(matter_id, str) or not 1 <= len(matter_id) <= 64:
            raise OutboundDenied('Valid matter required')
        user = self.core._identity(token)
        self.core._role(user, matter_id, ('owner', 'editor'))
        return user

    def authorize(self, token, matter_id, template_id, *, explicit_opt_in=False, ttl_seconds=60):
        """Issue one-use local consent; the caller must actively set opt-in true."""
        if explicit_opt_in is not True:
            raise OutboundDenied('Explicit template opt-in required')
        if not isinstance(template_id, str) or template_id not in self.TEMPLATES:
            raise OutboundDenied('Only approved fictional templates may be released')
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= self.MAX_TTL:
            raise OutboundDenied('Invalid lifetime')
        with self.core.lock, self.core.db:
            actor = self._authorize_matter(token, matter_id)
            grant = token_urlsafe(32)
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
            self.core.db.execute('''INSERT INTO fictional_ai_authorizations
                (grant_hash,credential_hash,actor_id,firm_id,matter_id,template_id,expires_at)
                VALUES (?,?,?,?,?,?,?)''',
                (sha256(grant.encode()).hexdigest(), sha256(token.encode()).hexdigest(),
                 actor['id'], actor['firm_id'], matter_id, template_id, expiry))
            return {'grant': grant, 'expires_at': expiry, 'single_use': True,
                    'template_id': template_id, 'network_sent': False}

    def prepare(self, token, matter_id, template_id, grant):
        """Consume grant atomically and return *only* immutable fictional text.

        The returned object is a local candidate for a later, separately reviewed
        provider client; this module has no transport or provider credentials.
        """
        if not isinstance(template_id, str) or template_id not in self.TEMPLATES:
            raise OutboundDenied('Template not authorized')
        if not isinstance(grant, str) or not 32 <= len(grant) <= 512:
            raise OutboundDenied('Valid one-use authorization required')
        with self.core.lock, self.core.db:
            actor = self._authorize_matter(token, matter_id)
            updated = self.core.db.execute('''UPDATE fictional_ai_authorizations
                SET consumed=1 WHERE grant_hash=? AND credential_hash=?
                AND actor_id=? AND firm_id=? AND matter_id=? AND template_id=?
                AND consumed=0 AND expires_at>?''',
                (sha256(grant.encode()).hexdigest(), sha256(token.encode()).hexdigest(),
                 actor['id'], actor['firm_id'], matter_id, template_id,
                 datetime.now(timezone.utc).isoformat()))
            if updated.rowcount != 1:
                raise OutboundDenied('Authorization missing, expired, revoked or already consumed')
        prompt = self.TEMPLATES[template_id]
        return {'schema': self.SCHEMA, 'template_id': template_id, 'prompt': prompt,
                'prompt_sha256': sha256(prompt.encode('utf-8')).hexdigest(),
                'fictional_only': True, 'contains_matter_data': False,
                'contains_user_supplied_text': False, 'network_sent': False,
                'provider_configured': False, 'legal_advice': False}
