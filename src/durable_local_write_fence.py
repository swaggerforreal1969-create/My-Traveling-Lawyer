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
        self.database = path
        self.path = path.with_name(path.name + '.write-fence.sqlite3')
        # A marker in the original local DB detects accidental sidecar removal
        # or replacement. It is NOT independently trusted or rollback-proof.
        # Unanchored legacy sidecars must not be silently adopted.
        try:
            with sqlite3.connect(str(self.database), timeout=5,
                                 isolation_level=None) as main:
                main.execute('PRAGMA busy_timeout=5000')
                main.execute('BEGIN IMMEDIATE')
                main.execute("""CREATE TABLE IF NOT EXISTS local_write_fence_anchor (
                    slot INTEGER PRIMARY KEY CHECK(slot=1),
                    marker TEXT NOT NULL)""")
                row = main.execute(
                    'SELECT marker FROM local_write_fence_anchor WHERE slot=1'
                ).fetchone()
                exists = self.path.is_file()
                if row is None:
                    if exists:
                        raise Denied('Existing unanchored write fence requires incident review')
                    marker=token_hex(32)
                    main.execute(
                        'INSERT INTO local_write_fence_anchor(slot,marker) VALUES(1,?)',
                        (marker,))
                else:
                    if not exists:
                        raise Denied('Missing write fence: all writes denied')
                    marker=row[0]
                with self._connection() as db:
                    db.execute("""CREATE TABLE IF NOT EXISTS fence (
                        slot INTEGER PRIMARY KEY CHECK(slot=1),
                        state TEXT NOT NULL CHECK(state='pending'),
                        kind TEXT NOT NULL DEFAULT 'unknown',
                        salt TEXT, fingerprint TEXT,
                        audit_before INTEGER,
                        reservation TEXT)""")
                    existing={entry[1] for entry in db.execute('PRAGMA table_info(fence)')}
                    for name, sql in (
                        ('kind', "TEXT NOT NULL DEFAULT 'unknown'"),
                        ('salt', 'TEXT'), ('fingerprint', 'TEXT'),
                        ('audit_before', 'INTEGER'),
                        ('reservation', 'TEXT')
                    ):
                        if name not in existing:
                            db.execute(f'ALTER TABLE fence ADD COLUMN {name} {sql}')
                    db.execute("""CREATE TABLE IF NOT EXISTS fence_marker (
                        slot INTEGER PRIMARY KEY CHECK(slot=1),
                        marker TEXT NOT NULL)""")
                    found=db.execute(
                        'SELECT marker FROM fence_marker WHERE slot=1').fetchone()
                    if found is None:
                        if row is not None:
                            raise Denied('Unbound existing write fence; writes denied')
                        db.execute('INSERT INTO fence_marker(slot,marker) VALUES(1,?)',
                                   (marker,))
                    elif found[0]!=marker:
                        raise Denied('Write fence binding mismatch; writes denied')
                main.execute('COMMIT')
        except Denied:
            raise
        except (sqlite3.Error, OSError) as error:
            raise Denied('Local write fence unavailable; all writes denied') from error

    def _verify_binding(self):
        try:
            if not self.path.is_file():
                raise Denied('Missing local write fence; writes denied')
            with sqlite3.connect(str(self.database), timeout=5) as main:
                anchor=main.execute(
                    'SELECT marker FROM local_write_fence_anchor WHERE slot=1'
                ).fetchone()
            with self._connection() as db:
                marker=db.execute(
                    'SELECT marker FROM fence_marker WHERE slot=1').fetchone()
            if (anchor is None or marker is None
                    or not isinstance(anchor[0],str)
                    or anchor[0]!=marker[0]):
                raise Denied('Local write fence binding invalid')
        except Denied:
            raise
        except (sqlite3.Error,OSError) as error:
            raise Denied('Cannot verify local write fence binding') from error

    def _connection(self):
        db = sqlite3.connect(str(self.path), timeout=5, isolation_level=None)
        db.execute('PRAGMA busy_timeout=5000')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def is_pending(self):
        self._verify_binding()
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
        reservation = token_hex(32)  # exact per-write CAS identity; never displayed
        salt = token_hex(24) if review_identity is not None else None
        fingerprint = (self._fingerprint(salt, review_identity)
                       if review_identity is not None else None)
        self._verify_binding()
        try:
            with self._connection() as db:
                db.execute('BEGIN IMMEDIATE')
                count = db.execute('SELECT count(*) FROM fence').fetchone()[0]
                if count:
                    db.execute('ROLLBACK')
                    raise Denied('A prior write is unresolved; no writes permitted')
                db.execute('''INSERT INTO fence
                    (slot,state,kind,salt,fingerprint,audit_before,reservation)
                    VALUES(1,'pending',?,?,?,?,?)''',
                    ('review' if review_identity is not None else 'unknown',
                     salt, fingerprint, audit_before, reservation))
                db.execute('COMMIT')
                return reservation
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
        self._verify_binding()
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

    def pending_reservation(self):
        """Return only an opaque local CAS version, not authorization evidence.

        Existing pre-version reservations deliberately require incident review;
        missing/corrupt identifiers may never be upgraded or auto-cleared.
        """
        self._verify_binding()
        try:
            with self._connection() as db:
                rows=db.execute(
                    'SELECT reservation FROM fence WHERE slot=1').fetchall()
                if len(rows)!=1 or not isinstance(rows[0][0],str):
                    raise Denied('No versioned reservation available')
                value=rows[0][0]
                if len(value)!=64 or any(ch not in '0123456789abcdef'
                                      for ch in value):
                    raise Denied('Invalid reservation version')
                return value
        except Denied:
            raise
        except (sqlite3.Error,OSError) as error:
            raise Denied('Reservation unavailable') from error

    def finish_confirmed(self, *, expected_reservation):
        """Exact-version CAS clearance after actor-authorized outcome proof.

        No wildcard, missing-version or automatic clearing is supported.
        This protects against a stale operator clearing a newer pending write,
        not against coordinated SQLite rollback or a malicious local writer.
        """
        if (not isinstance(expected_reservation,str)
                or len(expected_reservation)!=64
                or any(ch not in '0123456789abcdef'
                       for ch in expected_reservation)):
            raise Denied('Exact reservation identity required')
        self._verify_binding()
        try:
            with self._connection() as db:
                db.execute('BEGIN IMMEDIATE')
                deleted=db.execute(
                    'DELETE FROM fence WHERE slot=1 AND state=? AND reservation=?',
                    ('pending',expected_reservation))
                if deleted.rowcount!=1:
                    db.execute('ROLLBACK')
                    raise Denied('Reservation changed; clearance denied')
                db.execute('COMMIT')
        except Denied:
            raise
        except (sqlite3.Error,OSError) as error:
            raise Denied('Unable to clear exact reservation') from error
