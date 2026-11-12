"""Credential-free backup and fresh-location restore for FICTIONAL OFFLINE PILOTS.

No real client data, encryption, production identity proof or independent custody.
The archive contains fictional matter contents in plaintext. Treat it as private.
Never overwrite a source, destination, or existing archive.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from secrets import token_urlsafe
import json
import os
import sqlite3

from .secure_engine import SecureCore, Denied, Invalid
from .durable_local_write_fence import LocalWriteFence

SCHEMA = 'mtl.fictional.credential_free.backup.v1'
MAX_ARCHIVE_BYTES = 10_000_000
TABLES = (
    'firms', 'users', 'matters', 'grants', 'notes', 'audit',
    'audit_chain', 'tasks', 'research_evidence',
    'source_observation', 'source_second_review'
)
SENSITIVE = frozenset((
    'credentials', 'recovery_codes', 'device_keys', 'device_challenges'
))
METADATA = frozenset(('local_write_fence_anchor', 'sqlite_sequence'))


def _canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def _valid_regular(path):
    return path.is_file() and not path.is_symlink()


def _integrity(snapshot):
    """Independently check the saved local audit hash-chain after snapshot."""
    previous = 'GENESIS'
    for seq, row in enumerate(snapshot['audit_chain'], 1):
        if row['seq'] != seq or row['previous_hash'] != previous:
            raise Denied('Fictional audit snapshot invalid')
        data = {'actor': row['actor_id'], 'action': row['action'],
                'target': row['target'], 'at': row['at'], 'prev': previous}
        digest = sha256(_canonical(data)).hexdigest()
        if not compare_digest(digest, row['row_hash']):
            raise Denied('Fictional audit snapshot invalid')
        previous = digest


def _schema_and_rows(db):
    present = {r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    unknown = present - set(TABLES) - SENSITIVE - METADATA
    if unknown:
        raise Denied('Unsupported local data schema; backup not permitted')
    if not {'firms', 'users', 'matters', 'grants', 'audit_chain', 'tasks'} <= present:
        raise Denied('Incomplete fictional pilot schema')
    # Never silently export a device secret or other live admission data.
    for name in SENSITIVE & present:
        if name in ('credentials', 'recovery_codes'):
            continue
        if db.execute('SELECT 1 FROM '+name+' LIMIT 1').fetchone():
            raise Denied('Device authority must be separately resolved')
    result = {}
    for name in TABLES:
        if name not in present:
            result[name] = {'columns': [], 'rows': []}
            continue
        cols = [r[1] for r in db.execute('PRAGMA table_info('+name+')')]
        rows = db.execute('SELECT * FROM '+name+' ORDER BY rowid').fetchall()
        result[name] = {'columns': cols, 'rows': [list(row) for row in rows]}
    return result


def backup_fictional_pilot(database: Path, token: str, archive: Path):
    """Backup a sole-firm fictional pilot after authenticated owner admission.

    A SQLite snapshot is held in memory only; credential/recovery/device
    material is NEVER written to the archive. No active write fence allowed.
    """
    database = Path(database).expanduser()
    archive = Path(archive).expanduser()
    if not _valid_regular(database) or archive.exists() or archive.is_symlink():
        raise Denied('Backup requires an existing pilot and unused archive')
    if not archive.parent.is_dir() or archive.parent.is_symlink():
        raise Denied('Backup parent directory invalid')
    if not isinstance(token, str):
        raise Denied('Fictional pilot token required')
    if LocalWriteFence(database).is_pending():
        raise Denied('Unresolved local write: backup denied')
    core = SecureCore(database)
    snapshot = sqlite3.connect(':memory:')
    try:
        with core.passive_authorization():
            with core.authorized_transaction():
                actor = core._identity(token)
                if not core.verify_audit():
                    raise Denied('Local audit invalid')
                firm_count = core.db.execute('SELECT count(*) FROM firms').fetchone()[0]
                if firm_count != 1:
                    raise Denied('Multi-firm backup not supported')
                matters = core.db.execute('SELECT id FROM matters').fetchall()
                if not matters:
                    raise Denied('No fictional matters to backup')
                for matter in matters:
                    core._role(actor, matter['id'], ('owner',))
            # SQLite backup produces one coherent committed snapshot.
            # Do not hold an SQLite writer transaction while calling backup.
            with core.lock:
                core.db.backup(snapshot)
        source = _schema_and_rows(snapshot)
        data = {name: [dict(zip(part['columns'], row)) for row in part['rows']]
                for name, part in source.items()}
        _integrity(data)
        # Reject an authorization or unresolved-write change during capture.
        # This is conservative; never export a snapshot after an observed
        # revocation or newly pending incident fence.
        with core.passive_authorization():
            with core.authorized_transaction():
                current=core._identity(token)
                if current['id']!=actor['id'] or not core.verify_audit():
                    raise Denied('Backup authorization changed')
                for matter in core.db.execute('SELECT id FROM matters').fetchall():
                    core._role(current,matter['id'],('owner',))
        if LocalWriteFence(database).is_pending():
            raise Denied('Unresolved local write; backup denied')
        # Verify the snapshot has not crossed into another firm or role.
        firms = {r['id'] for r in data['firms']}
        if len(firms) != 1 or any(r['firm_id'] not in firms for r in data['users']):
            raise Denied('Cross-firm backup denied')
        owners = {(g['matter_id'], g['user_id']) for g in data['grants']
                  if g['role'] == 'owner'}
        if any((m['id'], actor['id']) not in owners for m in data['matters']):
            raise Denied('Backup requires current ownership of every matter')
        payload = {'schema': SCHEMA, 'tables': source}
        digest = sha256(_canonical(payload)).hexdigest()
        encoded = _canonical({'payload': payload, 'sha256': digest})
        if len(encoded) > MAX_ARCHIVE_BYTES:
            raise Denied('Backup exceeds fictional pilot limit')
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, 'O_NOFOLLOW'):
            flags |= os.O_NOFOLLOW
        old_umask = os.umask(0o077)
        try:
            fd = os.open(str(archive), flags, 0o600)
            with os.fdopen(fd, 'wb') as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
        finally:
            os.umask(old_umask)
        return {'archive': archive, 'sha256': digest,
                'records': {name: len(rows['rows']) for name, rows in source.items()}}
    finally:
        snapshot.close()
        core.close()


def restore_fictional_pilot(archive: Path, destination: Path):
    """Create a fresh fictional database with NEW one-time tokens.

    Does not import old token digests, recovery codes, device secrets or a
    prior pending-write fence. Existing files are never overwritten.
    """
    archive = Path(archive).expanduser()
    destination = Path(destination).expanduser()
    if not _valid_regular(archive) or destination.exists() or destination.is_symlink():
        raise Denied('Restore requires existing archive and unused destination')
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise Denied('Restore parent directory invalid')
    with archive.open('rb') as handle:
        raw = handle.read(MAX_ARCHIVE_BYTES+1)
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise Denied('Archive exceeds fictional pilot limit')
    try:
        document = json.loads(raw)
        payload = document['payload']
        if (payload['schema'] != SCHEMA or
                set(payload['tables']) != set(TABLES) or
                not compare_digest(document['sha256'],
                                   sha256(_canonical(payload)).hexdigest())):
            raise ValueError('Archive identity mismatch')
        tables = payload['tables']
        for name in TABLES:
            entry = tables[name]
            cols = entry['columns']
            if (not isinstance(cols, list) or len(cols) != len(set(cols))
                    or any(type(x) is not str for x in cols)
                    or not isinstance(entry['rows'], list)):
                raise ValueError('Invalid table shape')
            if any(type(row) is not list or len(row) != len(cols)
                   for row in entry['rows']):
                raise ValueError('Invalid stored record')
        data = {name: [dict(zip(tables[name]['columns'], row))
                       for row in tables[name]['rows']] for name in TABLES}
        _integrity(data)
        if (len(data['firms']) != 1 or not data['matters'] or
                any(r['firm_id'] != data['firms'][0]['id'] for r in data['users'])):
            raise ValueError('Nonfictional pilot topology')
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise Denied('Backup record integrity invalid') from error
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    old_umask = os.umask(0o077)
    core = None
    reserved = False
    try:
        fd = os.open(str(destination), flags, 0o600)
        os.close(fd)
        reserved = True
        core = SecureCore(destination)
        from .research_evidence import ResearchEvidence
        from .source_observation import SourceObservation
        from .second_source_review import SecondSourceReview
        ResearchEvidence(core)
        SourceObservation(core)
        SecondSourceReview(core)
        # Verify identical columns before inserting anything, rejecting an
        # unsupported schema, partial migration or injected field.
        for name in TABLES:
            expected = [r[1] for r in core.db.execute('PRAGMA table_info('+name+')')]
            actual = tables[name]['columns']
            if actual and actual != expected:
                raise Denied('Backup schema not accepted')
            if not actual and tables[name]['rows']:
                raise Denied('Incomplete backup')
        with core.authorized_transaction():
            for name in TABLES:
                entry = tables[name]
                if not entry['columns']:
                    continue
                placeholders = ','.join('?' for _ in entry['columns'])
                cols = ','.join(entry['columns'])
                for record in entry['rows']:
                    core.db.execute('INSERT INTO '+name+' ('+cols+') VALUES ('+
                                    placeholders+')', record)
            if not core.verify_audit():
                raise Denied('Restored audit integrity invalid')
            # New credentials are for the new fictional local database ONLY.
            # Never import an original credential digest or recovery secret.
            users = core.db.execute('SELECT id,name FROM users WHERE active=1').fetchall()
            if not users:
                raise Denied('No active fictional operator to restore')
            issued = []
            for user in users:
                token = token_urlsafe(32)
                now = datetime.now(timezone.utc)
                core.db.execute(
                    'INSERT INTO credentials(token_digest,user_id,expires_at,last_seen_at) '
                    'VALUES(?,?,?,?)',
                    (sha256(token.encode()).hexdigest(), user['id'],
                     (now+timedelta(hours=12)).isoformat(), now.isoformat()))
                issued.append({'user': user['name'], 'token': token})
        fence = LocalWriteFence(destination)
        if fence.is_pending():
            raise Denied('Restored local write fence unexpectedly pending')
        # Final, independent readback: count and value agreement for every
        # customer/audit table; token and recovery material never in archive.
        readback = _schema_and_rows(core.db)
        for name in TABLES:
            if readback[name] != tables[name]:
                # The source may lack optional research tables; constructors
                # create empty ones in the restored copy.
                if not (not tables[name]['columns'] and not readback[name]['rows']):
                    raise Denied('Restored fictional records mismatch')
        return {'database': destination, 'accounts': issued,
                'sha256': document['sha256']}
    except BaseException:
        if core is not None:
            core.close()
            core = None
        if reserved:
            for path in (str(destination),str(destination)+'.write-fence.sqlite3',
                         str(destination)+'-wal',str(destination)+'-shm',
                         str(destination)+'-journal'):
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
        raise
    finally:
        if core is not None:
            core.close()
        os.umask(old_umask)
