"""Offline transactional checkpoint admission *prototype*, NOT a custody provider.

Caller injects a REAL authentication verifier and separately controlled signer.
This implementation uses local SQLite for executable acceptance only. It is NOT
independent, rollback-resistant, remote, provisioned or production authorized.

Critical invariant: authenticate and reserve nonce/reservation inside a single
BEGIN IMMEDIATE transaction; persist signed head/event atomically, then return
an UNTRUSTED acknowledgment. Independent pinned readback is separately required.
"""
import json
import sqlite3
from pathlib import Path
from .secure_engine import Denied
from .independent_checkpoint_boundary import (
    PinnedCheckpoint, _digest, _hex, _identity)


class LocalCheckpointAdmissionPrototype:
    def __init__(self, path, *, genesis, authenticate, sign, signer_id):
        if (not isinstance(genesis,PinnedCheckpoint)
                or type(genesis.sequence) is not int or genesis.sequence != 0
                or not _hex(genesis.digest) or not _identity(genesis.signer_id)
                or not callable(authenticate) or not callable(sign)
                or signer_id != genesis.signer_id):
            raise Denied('Checkpoint trust configuration invalid')
        self.path = str(Path(path))
        self.genesis = genesis
        self.authenticate = authenticate
        self.sign = sign
        self.signer_id = signer_id
        # SQLite path belongs ONLY to explicitly authorized synthetic tests.
        try:
            with self._db() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_origin (
                    slot INTEGER PRIMARY KEY CHECK(slot=1),
                    genesis_digest TEXT NOT NULL, signer TEXT NOT NULL)""")
                db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_events (
                    sequence INTEGER PRIMARY KEY,
                    nonce TEXT NOT NULL UNIQUE,
                    reservation_digest TEXT NOT NULL UNIQUE,
                    event_digest TEXT NOT NULL,
                    previous TEXT NOT NULL,
                    head_digest TEXT NOT NULL UNIQUE,
                    signer_id TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    commit_state TEXT NOT NULL CHECK(commit_state='committed'))""")
                db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_policy (
                    slot INTEGER PRIMARY KEY CHECK(slot=1), revoked INTEGER NOT NULL)""")
                db.execute('INSERT OR IGNORE INTO checkpoint_policy VALUES(1,0)')
                row = db.execute(
                    'SELECT genesis_digest, signer FROM checkpoint_origin WHERE slot=1'
                ).fetchone()
                if row is None:
                    db.execute('INSERT INTO checkpoint_origin VALUES(1,?,?)',
                               (genesis.digest, genesis.signer_id))
                elif row != (genesis.digest, genesis.signer_id):
                    raise Denied('Checkpoint genesis mismatch')
        except Denied:
            raise
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Checkpoint storage unavailable') from exc

    def _db(self):
        conn=sqlite3.connect(self.path, timeout=5, isolation_level=None)
        conn.execute('PRAGMA busy_timeout=5000')
        conn.execute('PRAGMA synchronous=FULL')
        return conn

    def revoke_signer(self):
        """Test-only local operation; never implies operational key revocation."""
        try:
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('UPDATE checkpoint_policy SET revoked=1 WHERE slot=1')
                db.execute('COMMIT')
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Signer revocation state unavailable') from exc

    def admit(self, *, credential, reservation, nonce, event_digest, expected):
        """Atomic nonce+reservation+history admission; no retry on lost ACK.

        The credential-verification callback is invoked under the transaction.
        Do not infer successful commitment from this method's response.
        """
        if (not isinstance(expected,PinnedCheckpoint)
                or type(expected.sequence) is not int
                or expected.sequence < 0 or not _hex(expected.digest)
                or expected.signer_id != self.signer_id
                or not _hex(reservation) or not _hex(nonce)
                or not _hex(event_digest)):
            raise Denied('Checkpoint admission intent invalid')
        try:
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute(
                    'SELECT revoked FROM checkpoint_policy WHERE slot=1'
                ).fetchone() != (0,):
                    raise Denied('Checkpoint signer revoked')
                try:
                    authorized=self.authenticate(credential)
                except Exception as exc:
                    raise Denied('Checkpoint credential denied') from exc
                if authorized is not True:
                    raise Denied('Checkpoint credential denied')
                current = db.execute(
                    '''SELECT sequence,head_digest FROM checkpoint_events
                       ORDER BY sequence DESC LIMIT 1''').fetchone()
                tip = (current[0],current[1]) if current else (
                    self.genesis.sequence,self.genesis.digest)
                if (expected.sequence,expected.digest) != tip:
                    raise Denied('Stale or rollback checkpoint predecessor')
                if db.execute('SELECT 1 FROM checkpoint_events WHERE nonce=?',
                              (nonce,)).fetchone():
                    raise Denied('Nonce already admitted')
                reservation_digest=_digest({'reservation':reservation})
                if db.execute(
                    'SELECT 1 FROM checkpoint_events WHERE reservation_digest=?',
                    (reservation_digest,)).fetchone():
                    raise Denied('Reservation already admitted')
                seq=tip[0]+1
                head={'sequence':seq,'previous':tip[1],
                      'event_digest':event_digest,
                      'reservation_digest':reservation_digest,
                      'signer_id':self.signer_id}
                message=json.dumps(head,sort_keys=True,separators=(',',':'),
                                   ensure_ascii=True).encode('ascii')
                try:
                    signature=self.sign(self.signer_id,message)
                except Exception as exc:
                    raise Denied('Checkpoint signer unavailable') from exc
                if not isinstance(signature,str) or not 1 <= len(signature) <= 512:
                    raise Denied('Checkpoint signer returned invalid signature')
                digest=_digest(head)
                db.execute(
                    '''INSERT INTO checkpoint_events VALUES (?,?,?,?,?,?,?,?,?)''',
                    (seq,nonce,reservation_digest,event_digest,tip[1],
                     digest,self.signer_id,signature,'committed'))
                db.execute('COMMIT')
                # Returned acknowledgment is NOT independently committed proof.
                return {'sequence':seq,'head_digest':digest}
        except Denied:
            raise
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Checkpoint admission unavailable or conflicting') from exc

    def read_event(self, seq):
        if type(seq) is not int or seq <= 0:
            raise Denied('Invalid event sequence')
        try:
            with self._db() as db:
                row=db.execute(
                    '''SELECT sequence,reservation_digest,event_digest,commit_state
                       FROM checkpoint_events WHERE sequence=?''',(seq,)
                ).fetchone()
                if row is None:
                    raise Denied('Committed event absent')
                return dict(zip(('sequence','reservation_digest',
                                 'event_digest','commit_state'),row))
        except Denied:
            raise
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Checkpoint readback unavailable') from exc

    def read_head(self):
        try:
            with self._db() as db:
                row=db.execute(
                    '''SELECT sequence,reservation_digest,event_digest,previous,
                              signer_id,signature FROM checkpoint_events
                       ORDER BY sequence DESC LIMIT 1''').fetchone()
                if row is None:
                    raise Denied('No committed checkpoint available')
                return dict(zip(('sequence','reservation_digest',
                                 'event_digest','previous','signer_id','signature'),row))
        except Denied:
            raise
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Checkpoint readback unavailable') from exc
