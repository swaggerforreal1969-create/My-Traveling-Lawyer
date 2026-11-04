"""Offline v2 signed nonce-bound custody prototype and read-only recovery.

Distinct schema/table from v1, which remains unchanged and NEVER acquires
nonce-authentication by reinterpretation. SQLite/test signer cannot establish
independent custody, rollback resistance, provider identity or release approval.
"""
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .independent_checkpoint_boundary import PinnedCheckpoint, _digest, _hex
from .secure_engine import Denied

SCHEMA='mtl.custody.nonce-bound.v2'
FIELDS=('schema','sequence','previous','nonce_digest','reservation_digest',
        'event_digest','signer_id')
EXACT=set(FIELDS)|{'signature'}


@dataclass(frozen=True)
class NonceBoundObservation:
    status: str
    sequence: int
    latest_sequence: int
    nonce_authenticated: bool = True
    independently_custodied: bool = False
    permits_write_replay: bool = False
    permits_fence_clearance: bool = False


def _message(head):
    return json.dumps({k:head[k] for k in FIELDS},
                      sort_keys=True,separators=(',',':'),
                      ensure_ascii=True).encode('ascii')


class OfflineNonceBoundCustody:
    """Test-only transactional v2 admission; no network or provider provisioning."""

    def __init__(self,path,*,genesis,authenticate,sign,verify_signature):
        if (not isinstance(genesis,PinnedCheckpoint)
                or type(genesis.sequence) is not int or genesis.sequence!=0
                or not _hex(genesis.digest) or not callable(authenticate)
                or not callable(sign) or not callable(verify_signature)):
            raise Denied('Version-two genesis or trust callbacks unavailable')
        self.path=str(Path(path))
        self.genesis=genesis
        self.authenticate=authenticate
        self.sign=sign
        self.verify_signature=verify_signature
        try:
            with self._db() as conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS custody_v2_origin(
                    slot INTEGER PRIMARY KEY CHECK(slot=1),
                    digest TEXT NOT NULL,signer_id TEXT NOT NULL)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS custody_v2_events(
                    sequence INTEGER PRIMARY KEY,
                    nonce_digest TEXT NOT NULL UNIQUE,
                    reservation_digest TEXT NOT NULL UNIQUE,
                    event_digest TEXT NOT NULL,
                    previous TEXT NOT NULL,
                    head_digest TEXT NOT NULL UNIQUE,
                    signer_id TEXT NOT NULL,
                    signature TEXT NOT NULL)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS custody_v2_policy(
                    slot INTEGER PRIMARY KEY CHECK(slot=1),
                    revoked INTEGER NOT NULL)""")
                conn.execute('INSERT OR IGNORE INTO custody_v2_policy VALUES(1,0)')
                origin=conn.execute(
                    'SELECT digest,signer_id FROM custody_v2_origin WHERE slot=1'
                ).fetchone()
                if origin is None:
                    conn.execute('INSERT INTO custody_v2_origin VALUES(1,?,?)',
                                 (genesis.digest,genesis.signer_id))
                elif origin!=(genesis.digest,genesis.signer_id):
                    raise Denied('Version-two genesis mismatch')
        except Denied:raise
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Offline v2 custody unavailable') from exc

    def _db(self):
        conn=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        conn.execute('PRAGMA busy_timeout=5000')
        conn.execute('PRAGMA synchronous=FULL')
        return conn

    def revoke(self):
        try:
            with self._db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute('UPDATE custody_v2_policy SET revoked=1 WHERE slot=1')
                conn.execute('COMMIT')
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Signer revocation unavailable') from exc

    def admit_once(self,*,credential,nonce,reservation,event_digest,expected,
                   explicitly_authorized):
        if (explicitly_authorized is not True
                or not all(_hex(x) for x in (nonce,reservation,event_digest))
                or not isinstance(expected,PinnedCheckpoint)
                or type(expected.sequence) is not int
                or expected.sequence<0 or not _hex(expected.digest)
                or expected.signer_id!=self.genesis.signer_id):
            raise Denied('Version-two exact authorized intent absent')
        try:
            with self._db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if conn.execute(
                    'SELECT revoked FROM custody_v2_policy WHERE slot=1'
                ).fetchone()!=(0,):
                    raise Denied('Version-two signer revoked')
                try:
                    allowed=self.authenticate(credential)
                except Exception as exc:
                    raise Denied('Version-two credentials rejected') from exc
                if allowed is not True:
                    raise Denied('Version-two credentials rejected')
                last=conn.execute('SELECT sequence,head_digest FROM custody_v2_events '
                                  'ORDER BY sequence DESC LIMIT 1').fetchone()
                tip=last if last is not None else (
                    self.genesis.sequence,self.genesis.digest)
                if tip!=(expected.sequence,expected.digest):
                    raise Denied('Stale version-two predecessor')
                head={'schema':SCHEMA,'sequence':tip[0]+1,'previous':tip[1],
                      'nonce_digest':_digest({'nonce':nonce}),
                      'reservation_digest':_digest({'reservation':reservation}),
                      'event_digest':event_digest,'signer_id':self.genesis.signer_id}
                payload=_message(head)
                try:
                    signature=self.sign(head['signer_id'],payload)
                except Exception as exc:
                    raise Denied('Version-two signer unavailable') from exc
                if not isinstance(signature,str) or not 1<=len(signature)<=512:
                    raise Denied('Version-two signature malformed')
                conn.execute('INSERT INTO custody_v2_events VALUES(?,?,?,?,?,?,?,?)',
                             (head['sequence'],head['nonce_digest'],
                              head['reservation_digest'],event_digest,
                              tip[1],_digest(head),head['signer_id'],signature))
                conn.execute('COMMIT')
                return {'sequence':head['sequence'],'head_digest':_digest(head)}
        except Denied:raise
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Atomic version-two admission unavailable') from exc

    def _head_at(self,sequence):
        with self._db() as conn:
            row=conn.execute(
                'SELECT sequence,nonce_digest,reservation_digest,event_digest,'
                'previous,signer_id,signature FROM custody_v2_events '
                'WHERE sequence=?',(sequence,)).fetchone()
            if row is None:raise Denied('Historical version-two event absent')
            return dict(zip(('sequence','nonce_digest','reservation_digest',
                             'event_digest','previous','signer_id','signature'),row),
                        schema=SCHEMA)

    def read_historical(self,*,nonce,reservation,event_digest,
                        predecessor,retained_latest,max_events=16):
        """Verify exact signed nonce/event within bounded continuous history.

        Both trust pins MUST be independently supplied by caller; no pin
        learning, persistence, automatic replay, or fence clearance.
        """
        if (not all(_hex(x) for x in (nonce,reservation,event_digest))
                or not isinstance(predecessor,PinnedCheckpoint)
                or not isinstance(retained_latest,PinnedCheckpoint)
                or predecessor.signer_id!=self.genesis.signer_id
                or retained_latest.signer_id!=self.genesis.signer_id
                or type(predecessor.sequence) is not int
                or type(retained_latest.sequence) is not int
                or type(max_events) is not int or not 1<=max_events<=16
                or not 0<=predecessor.sequence<retained_latest.sequence
                or retained_latest.sequence-predecessor.sequence>max_events
                or not _hex(predecessor.digest)
                or not _hex(retained_latest.digest)):
            raise Denied('V2 trusted history boundary invalid')
        nonce_hash=_digest({'nonce':nonce})
        res_hash=_digest({'reservation':reservation})
        matches=[]
        previous=predecessor.digest
        try:
            with self._db() as conn:
                start=conn.execute('SELECT sequence,head_digest FROM custody_v2_events '
                                   'ORDER BY sequence DESC LIMIT 1').fetchone()
            if start is None or start[0]!=retained_latest.sequence:
                raise Denied('V2 latest sequence diverges from held anchor')
            for sequence in range(predecessor.sequence+1,retained_latest.sequence+1):
                head=self._head_at(sequence)
                if (set(head)!=EXACT or type(head['sequence']) is not int
                        or head['sequence']!=sequence
                        or head['schema']!=SCHEMA or head['previous']!=previous
                        or head['signer_id']!=self.genesis.signer_id
                        or not all(_hex(head[k]) for k in
                                   ('nonce_digest','reservation_digest','event_digest'))
                        or not isinstance(head['signature'],str)
                        or not 1<=len(head['signature'])<=512):
                    raise Denied('Malformed or forked v2 signed checkpoint')
                payload=_message(head)
                try:
                    valid=self.verify_signature(
                        head['signer_id'],payload,head['signature'])
                except Exception as exc:
                    raise Denied('V2 verifier unavailable') from exc
                if valid is not True:raise Denied('Invalid v2 signature')
                previous=_digest({k:head[k] for k in FIELDS})
                if (head['nonce_digest']==nonce_hash
                        and head['reservation_digest']==res_hash
                        and head['event_digest']==event_digest):
                    matches.append(sequence)
            with self._db() as conn:
                end=conn.execute('SELECT sequence,head_digest FROM custody_v2_events '
                                 'ORDER BY sequence DESC LIMIT 1').fetchone()
            if (previous!=retained_latest.digest
                    or end!=start or end!=(retained_latest.sequence,
                                            retained_latest.digest)):
                raise Denied('Historical v2 finality or live head changed')
        except Denied:raise
        except (sqlite3.Error,OSError) as exc:
            raise Denied('Historical v2 readback unavailable') from exc
        if len(matches)!=1:
            raise Denied('Exact nonce-bound operation missing or ambiguous')
        return NonceBoundObservation(
            'exact_signed_nonce_bound_operation_observed',
            matches[0],retained_latest.sequence)
