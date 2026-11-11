"""Experimental single-use, short-lived authorization for local private preview.

Tickets never authenticate a user on their own: the original valid bearer credential
must also be presented, and current matter permission is rechecked at consumption.
No HTTP listener, network access or client data export. Not production WebAuthn.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe

from .mobile_preview_gateway import MobilePreviewGateway, PreviewRejected


class TicketRejected(PreviewRejected):
    """Reject a missing, expired, consumed, wrongly scoped or unauthorised ticket."""


class PreviewSessionBroker:
    MAX_TTL_SECONDS = 120

    def __init__(self, core, gateway=None):
        self.core = core
        self.gateway = gateway if gateway is not None else MobilePreviewGateway(core)
        with core.lock, core.db:
            core.db.execute('''CREATE TABLE IF NOT EXISTS preview_ticket (
                ticket_digest TEXT PRIMARY KEY,
                credential_digest TEXT NOT NULL,
                user_id TEXT NOT NULL,
                firm_id TEXT NOT NULL,
                matter_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                consumed INTEGER NOT NULL DEFAULT 0 CHECK(consumed IN (0,1))
            )''')
            core.db.execute('CREATE INDEX IF NOT EXISTS preview_ticket_expire ON preview_ticket(expires_at)')

    @staticmethod
    def _validate_request(token, matter_id):
        if not isinstance(token, str) or not (32 <= len(token) <= 512):
            raise TicketRejected('Valid credential required')
        if not isinstance(matter_id, str) or not (1 <= len(matter_id) <= 64):
            raise TicketRejected('Valid matter required')

    def issue(self, token, matter_id, *, ttl_seconds=60):
        """Mint a single-use ticket only for an authorized matter. Never store token."""
        self._validate_request(token, matter_id)
        if type(ttl_seconds) is not int or not (1 <= ttl_seconds <= self.MAX_TTL_SECONDS):
            raise TicketRejected('Invalid ticket lifetime')
        with self.core.authorized_transaction():
            actor = self.core._identity(token)
            self.core._role(actor, matter_id, ('owner', 'editor', 'viewer'))
            ticket = token_urlsafe(32)
            expiry = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
            self.core.db.execute('''INSERT INTO preview_ticket
                (ticket_digest, credential_digest, user_id, firm_id, matter_id, expires_at)
                VALUES (?,?,?,?,?,?)''',
                (sha256(ticket.encode()).hexdigest(), sha256(token.encode()).hexdigest(),
                 actor['id'], actor['firm_id'], matter_id, expiry))
            return {'ticket': ticket, 'expires_at': expiry, 'single_use': True,
                    'requires_existing_credential': True, 'matter_id': matter_id}

    def consume(self, token, matter_id, ticket, *, now=None):
        """Atomically burn the ticket before rendering; deny any subsequent replay.

        A failed render burns the ticket too. This deliberately favours security over
        retriable previews and avoids leaking the preview through partial retries.
        """
        self._validate_request(token, matter_id)
        if not isinstance(ticket, str) or not (32 <= len(ticket) <= 512):
            raise TicketRejected('Valid ticket required')
        if now is not None and (not isinstance(now, datetime) or now.tzinfo is None):
            raise TicketRejected('Timezone-aware time required')
        credential_digest = sha256(token.encode()).hexdigest()
        ticket_digest = sha256(ticket.encode()).hexdigest()
        with self.core.authorized_transaction():
            actor = self.core._identity(token)
            self.core._role(actor, matter_id, ('owner', 'editor', 'viewer'))
            updated = self.core.db.execute('''UPDATE preview_ticket SET consumed=1
                WHERE ticket_digest=? AND credential_digest=? AND user_id=?
                  AND firm_id=? AND matter_id=? AND consumed=0 AND expires_at>?''',
                (ticket_digest, credential_digest, actor['id'], actor['firm_id'],
                 matter_id, datetime.now(timezone.utc).isoformat()))
            if updated.rowcount != 1:
                raise TicketRejected('Preview ticket unavailable')
        # Ticket has been durably burned; this second authentication check can fail
        # if access changes between ticket consumption and gateway rendering.
        return self.gateway.prepare(token, matter_id, now=now)
