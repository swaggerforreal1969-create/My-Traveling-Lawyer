"""Isolated experimental authorization core. Fictional test data only.

This layer intentionally has NO integration with the v0.2 HTTP server or demo UI.
It is not production authentication, encrypted storage, or independent custody.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from contextlib import contextmanager
from contextvars import ContextVar
from hmac import compare_digest
from secrets import token_urlsafe
import json
import sqlite3
import threading
import uuid

class Denied(Exception): pass
class Stale(Exception): pass
class Invalid(Exception): pass

class SecureCore:
    IDLE_SECONDS = 300

    @contextmanager
    def passive_authorization(self):
        """Verify session/ACL without recording user activity.

        Context-local and exception-safe; never use around write operations.
        Calls still check credential expiry, revocation and idle age.
        """
        flag = self._passive_auth.set(True)
        try:
            yield
        finally:
            self._passive_auth.reset(flag)
    def __init__(self, path=':memory:'):
        # The scope belongs to THIS core, never every SecureCore in the same
        # context. A passive watch on one database must not suppress genuine
        # user-activity tracking in another independent operator/session.
        self._passive_auth = ContextVar('mtl_passive_auth_instance', default=False)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS firms(id TEXT PRIMARY KEY, name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, firm_id TEXT NOT NULL REFERENCES firms(id), name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS credentials(token_digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), revoked INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS matters(id TEXT PRIMARY KEY, firm_id TEXT NOT NULL REFERENCES firms(id), title TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS grants(matter_id TEXT NOT NULL REFERENCES matters(id), user_id TEXT NOT NULL REFERENCES users(id), role TEXT NOT NULL CHECK(role IN ('owner','editor','viewer')), PRIMARY KEY(matter_id,user_id));
        CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY, matter_id TEXT NOT NULL REFERENCES matters(id), user_id TEXT NOT NULL REFERENCES users(id), text TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL, action TEXT NOT NULL, target TEXT NOT NULL, at TEXT NOT NULL);
        ''')
        # Migration: legacy demo credentials get a finite, conservative lifetime.
        columns={r['name'] for r in self.db.execute('PRAGMA table_info(credentials)')}
        if 'expires_at' not in columns:
            self.db.execute('ALTER TABLE credentials ADD COLUMN expires_at TEXT')
        expiry=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()
        self.db.execute('UPDATE credentials SET expires_at=? WHERE expires_at IS NULL',(expiry,))
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS audit_chain(seq INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL,
          action TEXT NOT NULL, target TEXT NOT NULL, at TEXT NOT NULL, previous_hash TEXT NOT NULL, row_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, matter_id TEXT NOT NULL REFERENCES matters(id),
          text TEXT NOT NULL, due_at TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0);
        ''')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS recovery_codes(user_id TEXT NOT NULL REFERENCES users(id),
          code_digest TEXT PRIMARY KEY, used INTEGER NOT NULL DEFAULT 0,
          expires_at TEXT NOT NULL);
        ''')
        credential_cols={r['name'] for r in self.db.execute('PRAGMA table_info(credentials)')}
        if 'last_seen_at' not in credential_cols:
            self.db.execute('ALTER TABLE credentials ADD COLUMN last_seen_at TEXT')
        self.db.execute('UPDATE credentials SET last_seen_at=? WHERE last_seen_at IS NULL', (datetime.now(timezone.utc).isoformat(),))
        task_cols={r['name'] for r in self.db.execute('PRAGMA table_info(tasks)')}
        if 'version' not in task_cols:self.db.execute('ALTER TABLE tasks ADD COLUMN version INTEGER NOT NULL DEFAULT 1')

    def _audit(self, actor, action, target):
        at=datetime.now(timezone.utc).isoformat()
        previous=self.db.execute('SELECT row_hash FROM audit_chain ORDER BY seq DESC LIMIT 1').fetchone()
        prev=previous['row_hash'] if previous else 'GENESIS'
        entry={'actor':actor,'action':action,'target':target,'at':at,'prev':prev}
        digest=sha256(json.dumps(entry,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.db.execute('INSERT INTO audit_chain(actor_id,action,target,at,previous_hash,row_hash) VALUES(?,?,?,?,?,?)',
                        (actor,action,target,at,prev,digest))
        self.db.execute('INSERT INTO audit(actor_id,action,target,at) VALUES(?,?,?,?)',(actor,action,target,at))

    def provision_firm(self, name):
        """Administrative test fixture ONLY; never expose over HTTP."""
        if not isinstance(name, str) or not name.strip(): raise Invalid('Firm name required')
        with self.lock, self.db:
            fid=str(uuid.uuid4())
            self.db.execute('INSERT INTO firms VALUES (?,?)',(fid,name.strip()))
            return fid

    def provision_user(self, firm_id, name):
        """Administrative test fixture ONLY. Returns bearer token once."""
        if not isinstance(name,str) or not name.strip(): raise Invalid('User name required')
        with self.lock, self.db:
            if not self.db.execute('SELECT 1 FROM firms WHERE id=?',(firm_id,)).fetchone(): raise Invalid('Unknown firm')
            uid=str(uuid.uuid4()); token=token_urlsafe(32)
            self.db.execute('INSERT INTO users(id,firm_id,name) VALUES(?,?,?)',(uid,firm_id,name.strip()))
            self.db.execute('INSERT INTO credentials(token_digest,user_id,expires_at) VALUES (?,?,?)',(sha256(token.encode()).hexdigest(),uid,(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()))
            self.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?', (datetime.now(timezone.utc).isoformat(),sha256(token.encode()).hexdigest()))
            return uid,token

    def _identity(self, token):
        # Server-enforced idle expiration; UTC demo wall clock only.
        if not isinstance(token,str) or len(token)>512 or len(token)<32: raise Denied('Access denied')
        digest=sha256(token.encode()).hexdigest()
        now=datetime.now(timezone.utc)
        row=self.db.execute('''SELECT u.id,u.firm_id,c.last_seen_at FROM credentials c JOIN users u ON c.user_id=u.id
            WHERE c.token_digest=? AND c.revoked=0 AND u.active=1 AND c.expires_at>?''',(digest,now.isoformat())).fetchone()
        if row is None: raise Denied('Access denied')
        try:
            last=datetime.fromisoformat(row['last_seen_at'])
            if last.tzinfo is None or (now-last).total_seconds() >= self.IDLE_SECONDS or (last-now).total_seconds()>30:
                raise Denied('Access denied')
        except (TypeError,ValueError):
            raise Denied('Access denied')
        if not self._passive_auth.get():
            self.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',(now.isoformat(),digest))
        return row

    def _role(self, identity, matter_id, allowed):
        row=self.db.execute('''SELECT m.version,g.role FROM matters m JOIN grants g ON m.id=g.matter_id
            WHERE m.id=? AND m.firm_id=? AND g.user_id=?''',
            (matter_id,identity['firm_id'],identity['id'])).fetchone()
        if row is None or row['role'] not in allowed: raise Denied('Access denied')
        return row

    def create_matter(self, token, title):
        if not isinstance(title,str) or not (1<=len(title.strip())<=160):raise Invalid('Invalid title')
        with self.lock, self.db:
            u=self._identity(token); mid=str(uuid.uuid4())
            self.db.execute('INSERT INTO matters(id,firm_id,title) VALUES(?,?,?)',(mid,u['firm_id'],title.strip()))
            self.db.execute('INSERT INTO grants VALUES(?,?,?)',(mid,u['id'],'owner'))
            self._audit(u['id'],'matter.create',mid)
            return {'id':mid,'title':title.strip(),'version':1}

    def grant(self, token, matter_id, target_user, role, expected_version):
        if role not in ('editor','viewer'): raise Invalid('Invalid role')
        if type(expected_version)!=int or expected_version<1: raise Invalid('Invalid version')
        with self.lock, self.db:
            u=self._identity(token)
            row=self._role(u,matter_id,('owner',))
            if row['version']!=expected_version: raise Stale('Version changed')
            target=self.db.execute('SELECT firm_id,active FROM users WHERE id=?',(target_user,)).fetchone()
            if target is None or target['firm_id']!=u['firm_id'] or not target['active']: raise Denied('Access denied')
            if target_user==u['id']:raise Denied('Access denied')
            self.db.execute('''INSERT INTO grants VALUES(?,?,?) ON CONFLICT(matter_id,user_id)
                DO UPDATE SET role=excluded.role''',(matter_id,target_user,role))
            changed=self.db.execute('UPDATE matters SET version=version+1 WHERE id=? AND version=?',(matter_id,expected_version))
            if changed.rowcount!=1: raise Stale('Version changed')
            self._audit(u['id'],'grant.set',matter_id)
            return {'matter_id':matter_id,'version':expected_version+1}

    def list_matters(self, token):
        with self.lock:
            u=self._identity(token)
            return [dict(x) for x in self.db.execute('''SELECT m.id,m.title,m.version,g.role
                FROM matters m JOIN grants g ON m.id=g.matter_id
                WHERE m.firm_id=? AND g.user_id=? ORDER BY m.id''',(u['firm_id'],u['id']))]

    def add_note(self, token, matter_id, text):
        if not isinstance(text,str) or not (1<=len(text.strip())<=2000):raise Invalid('Invalid note')
        with self.lock, self.db:
            u=self._identity(token); self._role(u,matter_id,('owner','editor'))
            nid=str(uuid.uuid4())
            self.db.execute('INSERT INTO notes VALUES (?,?,?,?)',(nid,matter_id,u['id'],text.strip()))
            self._audit(u['id'],'note.create',matter_id)
            return {'id':nid,'matter_id':matter_id}

    def read_notes(self, token, matter_id):
        with self.lock:
            u=self._identity(token); self._role(u,matter_id,('owner','editor','viewer'))
            return [dict(x) for x in self.db.execute('SELECT id,text FROM notes WHERE matter_id=? ORDER BY id',(matter_id,))]

    def revoke_token(self, token):
        with self.lock, self.db:
            u=self._identity(token)
            self.db.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',(sha256(token.encode()).hexdigest(),))
            self._audit(u['id'],'credential.revoke',u['id'])

    def rotate_token(self, token):
        """Authenticated demo rotation; never a password-recovery substitute."""
        with self.lock, self.db:
            u=self._identity(token)
            replacement=token_urlsafe(32)
            expiry=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()
            self.db.execute('INSERT INTO credentials(token_digest,user_id,expires_at) VALUES(?,?,?)',
                            (sha256(replacement.encode()).hexdigest(),u['id'],expiry))
            self.db.execute('UPDATE credentials SET revoked=1 WHERE token_digest=?',(sha256(token.encode()).hexdigest(),))
            self.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',(datetime.now(timezone.utc).isoformat(),sha256(replacement.encode()).hexdigest()))
            self._audit(u['id'],'credential.rotate',u['id'])
            return {'token':replacement,'expires_at':expiry}

    def verify_audit(self):
        """Verify local hash chain AND its separately stored audit mirror.

        A truncated/deleted chain is not an authentic empty history when the
        mirror still contains events. Neither local table is independent
        rollback-resistant custody; both may be changed by a database owner.
        """
        with self.lock:
            previous='GENESIS'
            expected_seq=1
            mirror=self.db.execute(
                'SELECT seq,actor_id,action,target,at FROM audit ORDER BY seq'
            ).fetchall()
            chain=self.db.execute('SELECT * FROM audit_chain ORDER BY seq').fetchall()
            if len(mirror)!=len(chain):
                return False
            for row, legacy in zip(chain,mirror):
                if row['seq']!=expected_seq or legacy['seq']!=expected_seq:
                    return False
                if any(row[key]!=legacy[key] for key in (
                        'actor_id','action','target','at')):
                    return False
                expected_seq+=1
                entry={'actor':row['actor_id'],'action':row['action'],
                       'target':row['target'],'at':row['at'],'prev':previous}
                digest=sha256(json.dumps(entry,sort_keys=True,
                    separators=(',',':')).encode()).hexdigest()
                if row['previous_hash']!=previous or not compare_digest(
                        digest,row['row_hash']):
                    return False
                previous=digest
            return True

    def create_task(self,token,matter_id,text,due_at):
        if not isinstance(text,str) or not 1<=len(text.strip())<=200:raise Invalid('Invalid task')
        try:
            due=datetime.fromisoformat(due_at.replace('Z','+00:00'))
            if due.tzinfo is None:raise ValueError()
            due=due.astimezone(timezone.utc).isoformat()
        except (ValueError,AttributeError,TypeError):raise Invalid('Timezone-aware ISO deadline required')
        with self.lock,self.db:
            u=self._identity(token);self._role(u,matter_id,('owner','editor'))
            tid=str(uuid.uuid4())
            self.db.execute('INSERT INTO tasks(id,matter_id,text,due_at) VALUES(?,?,?,?)',(tid,matter_id,text.strip(),due))
            self._audit(u['id'],'task.create',tid)
            return {'id':tid,'matter_id':matter_id,'due_at':due}

    def dashboard(self,token):
        with self.lock:
            u=self._identity(token)
            matters=self.list_matters(token)
            tasks=[dict(r) for r in self.db.execute("""SELECT t.id,t.text,t.due_at,t.version,m.title AS matter_title
                FROM tasks t JOIN matters m ON t.matter_id=m.id JOIN grants g ON m.id=g.matter_id
                WHERE m.firm_id=? AND g.user_id=? AND t.completed=0 ORDER BY t.due_at,t.id LIMIT 30""",
                (u['firm_id'],u['id']))]
            return {'matter_count':len(matters),'upcoming_tasks':tasks,'as_of':datetime.now(timezone.utc).isoformat(),
                    'note':'Dates are user-entered; no court-rule calculation or automatic legal deadline assurance.'}


    def issue_recovery_code(self, token):
        """Issue one local recovery code while authenticated; print once, store digest only.

        CLI/secure local workflow only. No recovery endpoint in HTTP.
        """
        with self.lock, self.db:
            u=self._identity(token)
            code=token_urlsafe(40)
            digest=sha256(code.encode()).hexdigest()
            self.db.execute('INSERT INTO recovery_codes(user_id,code_digest,expires_at) VALUES(?,?,?)',
                            (u['id'],digest,(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()))
            self._audit(u['id'],'recovery.issue',u['id'])
            return code

    def recover_offline(self, user_id, code):
        """Local-only recovery: consume previously generated code, revoke all prior sessions.

        This is NOT identity proofing or production MFA. Never expose over HTTP.
        """
        if not isinstance(user_id,str) or not isinstance(code,str) or not (40<=len(code)<=256):
            raise Denied('Access denied')
        digest=sha256(code.encode()).hexdigest()
        with self.lock,self.db:
            row=self.db.execute("""SELECT r.user_id FROM recovery_codes r JOIN users u ON r.user_id=u.id
                WHERE r.code_digest=? AND r.user_id=? AND r.used=0 AND r.expires_at>?
                AND u.active=1""",(digest,user_id,datetime.now(timezone.utc).isoformat())).fetchone()
            if row is None:raise Denied('Access denied')
            updated=self.db.execute('UPDATE recovery_codes SET used=1 WHERE code_digest=? AND used=0',(digest,))
            if updated.rowcount!=1:raise Denied('Access denied')
            self.db.execute('UPDATE credentials SET revoked=1 WHERE user_id=?',(user_id,))
            self.db.execute('UPDATE recovery_codes SET used=1 WHERE user_id=?',(user_id,))
            token=token_urlsafe(32)
            expiry=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()
            self.db.execute('INSERT INTO credentials(token_digest,user_id,expires_at) VALUES(?,?,?)',
                            (sha256(token.encode()).hexdigest(),user_id,expiry))
            self.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',(datetime.now(timezone.utc).isoformat(),sha256(token.encode()).hexdigest()))
            self._audit(user_id,'recovery.consume',user_id)
            return {'token':token,'expires_at':expiry}

    def complete_task(self,token,task_id,expected_version):
        """Serialize credential, ACL, version and task mutation with writers.

        BEGIN IMMEDIATE acquires the SQLite writer reservation BEFORE reading
        session and ACL state. A second independent connection may revoke or
        downgrade before this admission or after it commits, but cannot change
        authority midway through the protected operation. No retry is made.
        """
        if not isinstance(task_id,str) or not (1<=len(task_id)<=64) or type(expected_version)!=int or expected_version<1:
            raise Invalid('Invalid task completion request')
        with self.lock:
            if self.db.in_transaction:
                raise Invalid('Task admission requires an independent transaction')
            self.db.execute('BEGIN IMMEDIATE')
            try:
                u=self._identity(token)
                row=self.db.execute('SELECT matter_id,version,completed FROM tasks WHERE id=?',(task_id,)).fetchone()
                if row is None:raise Denied('Access denied')
                self._role(u,row['matter_id'],('owner','editor'))
                if row['version']!=expected_version:raise Stale('Version changed')
                if row['completed']:raise Stale('Task already completed')
                changed=self.db.execute('UPDATE tasks SET completed=1,version=version+1 WHERE id=? AND completed=0 AND version=?',
                                        (task_id,expected_version))
                if changed.rowcount!=1:raise Stale('Version changed')
                self._audit(u['id'],'task.complete',task_id)
                result={'task_id':task_id,'version':expected_version+1,'completed':True}
                self.db.commit()
                return result
            except BaseException:
                self.db.rollback()
                raise

    def audit_head(self):
        # Local audit head; not independently durable by itself.
        with self.lock:
            if not self.verify_audit(): raise Invalid('Audit verification failed')
            row=self.db.execute('SELECT seq,row_hash FROM audit_chain ORDER BY seq DESC LIMIT 1').fetchone()
            return {'schema':'mtl.audit.head.v1','seq':row['seq'] if row else 0,
                    'row_hash':row['row_hash'] if row else 'GENESIS'}

    def close(self):self.db.close()
