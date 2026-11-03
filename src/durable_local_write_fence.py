"""Durable local *write fence*, not independent custody or recovery evidence.

The only persisted application state is one anonymous global pending bit.
It is committed BEFORE any local attorney write. It survives process crashes,
applies across local windows/processes using this fence, and fails closed after
uncertainty or corruption. There is deliberately NO API for auto-clearing an
orphaned pending bit: authorized incident review is required. The guard must
never be mistaken for durable event identity or cryptographic rollback proof.
"""
from pathlib import Path
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
                           "state TEXT NOT NULL CHECK(state='pending'))")
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

    def begin(self):
        try:
            with self._connection() as db:
                db.execute('BEGIN IMMEDIATE')
                count = db.execute('SELECT count(*) FROM fence').fetchone()[0]
                if count:
                    db.execute('ROLLBACK')
                    raise Denied('A prior write is unresolved; no writes permitted')
                db.execute("INSERT INTO fence(slot,state) VALUES(1,'pending')")
                db.execute('COMMIT')
        except Denied:
            raise
        except (sqlite3.Error, OSError) as error:
            raise Denied('Cannot persist write fence; write denied') from error

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
