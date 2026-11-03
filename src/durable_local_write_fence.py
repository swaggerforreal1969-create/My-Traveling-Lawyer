"""Durable local *write fence*, not independent custody or recovery evidence.

The only persisted application state is one anonymous global pending bit.
It is committed BEFORE any local attorney write. It survives process crashes,
applies across local windows/processes using this fence, and fails closed after
uncertainty or corruption. There is deliberately NO API for auto-clearing an
orphaned pending bit: authorized incident review is required. The guard must
never be mistaken for durable event identity or cryptographic rollback proof.
"""
from pathlib import Path
from hashlib import sha256
from secrets import token_hex
import json
import sqlite3

from .secure_engine import Denied


class LocalWriteFence:
    def __init__(self, database):
        path = Path(database)
        if not path.is_file():
            raise Denied('Existing local database required for durable fence')
        self.path = path.with_name(path.name + '.write-fence.sqlite3')
        try:
            with self._connection() as db:
                db.execute("CREATE TABLE IF NOT EXISTS fence ("
                           "slot INTEGER PRIMARY KEY CHECK(slot=1),"
                           "state TEXT NOT NULL CHECK(state='pending'),"
                           "kind TEXT NOT NULL DEFAULT 'unknown',"
                           "salt TEXT, fingerprint TEXT,"
                           "audit_before INTEGER)")
                existing={row[1] for row in db.execute('PRAGMA table_info(fence)')}
                for name, sql in (
                    ('kind', "TEXT NOT NULL DEFAULT 'unknown'"),
                    ('salt', 'TEXT'), ('fingerprint', 'TEXT'),
                    ('audit_before', 'INTEGER')
                ):
                    if name not in existing:
                        db.execute(f'ALTER TABLE fence ADD COLUMN {name} {sql}')
        except (sqlite3.Error, OSError) as error:
            raise Denied('Local write fence unavailable; all writes denied') from error

    def _connection(self):
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.execute('PRAGMA busy_timeout=5000')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def is_pending(self):
        try:
            with self._connection() as db:
                row = db.execute('SELECT state FROM fence WHERE slot=1').fetchone()
                return row is not None
        except (sqlite3.Error, OSError) as error:
            raise Denied('Local write fence unreadable; writes denied') from error

    @staticmethod
    def _fingerprint(salt, identity):
        return sha256(json.dumps([salt, *identity],
                      separators=(',', ':'), ensure_ascii=True).encode('utf-8')).hexdigest()

    def begin(self, *, review_identity=None, audit_before=None):
        """Reserve one write. For a review store ONLY a salted fingerprint.

        Identity order: (actor_id, matter_id, evidence_id, observation_id).
        This is a local matching hint, not a cryptographic custody witness.
        """
        if review_identity is not None:
            if (not isinstance(review_identity, tuple)
                    or len(review_identity) != 4
                    or not all(isinstance(i,str) and i for i in review_identity)
                    or type(audit_before) is not int or audit_before < 0):
                raise Denied('Invalid review reservation; no write permitted')
        salt = token_hex(24) if review_identity is not None else None
        fingerprint = (self._fingerprint(salt, review_identity)
                       if review_identity is not None else None)
        try:
            with self._connection() as db:
                db.execute('BEGIN IMMEDIATE')
                count = db.execute('SELECT count(*) FROM fence').fetchone()[0]
                if count:
                    db.execute('ROLLBACK')
                    raise Denied('A prior write is unresolved; no writes permitted')
                db.execute('''INSERT INTO fence
                    (slot,state,kind,salt,fingerprint,audit_before)
                    VALUES(1,'pending',?,?,?,?)''',
                    ('review' if review_identity is not None else 'unknown',
                     salt, fingerprint, audit_before))
                db.execute('COMMIT')
        except Denied:
            raise
        except (sqlite3.Error, OSError) as error:
            raise Denied('Cannot persist write fence; write denied') from error

    def pending_review_matches(self, identity, audit_seq):
        """Match a candidate without disclosing stored IDs or the fingerprint.

        Calling code MUST first authorize the actor and matter and verify the
        actual local record and audit event. This comparison alone is not proof.
        """
        if (not isinstance(identity,tuple) or len(identity)!=4
                or type(audit_seq) is not int):
            raise Denied('Invalid recovery candidate')
        try:
            with self._connection() as db:
                rows=db.execute('''SELECT kind,salt,fingerprint,audit_before
                                   FROM fence WHERE slot=1''').fetchall()
                if len(rows)!=1 or rows[0][0]!='review':
                    raise Denied('No recoverable review reservation')
                _, salt, fingerprint, floor=rows[0]
                if (not isinstance(salt,str) or len(salt)!=48
                        or not isinstance(fingerprint,str)
                        or len(fingerprint)!=64 or type(floor)!=int):
                    raise Denied('Invalid pending review reservation')
                return (audit_seq > floor and
                        self._fingerprint(salt,identity)==fingerprint)
        except Denied:
            raise
        except (sqlite3.Error,OSError) as error:
            raise Denied('Recovery reservation unreadable') from error

    def finish_confirmed(self):
        """Only call when the operation outcome is DEFINITIVELY known.

        A crash between commit and clearance intentionally leaves a pending
        fence. No auto-clear on reboot, timeout, startup, or uncertain result.
        """
        try:
            with self._connection() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT count(*) FROM fence').fetchone()[0] != 1:
                    db.execute('ROLLBACK')
                    raise Denied('Write fence missing or corrupted')
                db.execute('DELETE FROM fence WHERE slot=1')
                db.execute('COMMIT')
        except Denied:
            raise
        except (sqlite3.Error, OSError) as error:
            raise Denied('Unable to clear write fence; further writes denied') from error
