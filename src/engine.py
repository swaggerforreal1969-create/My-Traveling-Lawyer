"""My Traveling Lawyer experimental engine; fictional data only."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import RLock
import json
import sqlite3
import uuid

LOCK = RLock()

def utcnow():
    return datetime.now(timezone.utc).isoformat()

class ConflictError(Exception): pass
class NotFoundError(Exception): pass
class ValidationError(Exception): pass

@dataclass(frozen=True)
class Entry:
    id: str
    matter_id: str
    kind: str
    text: str
    occurred_at: str
    minutes: int = 0

class Engine:
    def __init__(self, path: str | Path = ':memory:'):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA busy_timeout=5000')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS matters (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS entries (
            id TEXT PRIMARY KEY, matter_id TEXT NOT NULL REFERENCES matters(id),
            kind TEXT NOT NULL CHECK(kind IN ('note','time','task','deadline')),
            text TEXT NOT NULL, occurred_at TEXT NOT NULL, minutes INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)),
            version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS audit (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, action TEXT NOT NULL,
            object_id TEXT NOT NULL, detail TEXT NOT NULL, prev_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS requests (
            request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response_json TEXT NOT NULL);
        ''')
        self.db.commit()

    def _audit(self, action, object_id, detail):
        previous = self.db.execute('SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
        prev_hash = previous['event_hash'] if previous else 'GENESIS'
        at = utcnow()
        payload = json.dumps([at, action, object_id, detail, prev_hash], separators=(',', ':'))
        event_hash = sha256(payload.encode()).hexdigest()
        self.db.execute('INSERT INTO audit (at,action,object_id,detail,prev_hash,event_hash) VALUES (?,?,?,?,?,?)',
                        (at,action,object_id,detail,prev_hash,event_hash))

    def _run(self, request_id, payload, perform):
        if not isinstance(request_id,str) or not request_id.strip() or len(request_id)>128:
            raise ValidationError('Request identifier required (max 128 characters)')
        fingerprint = sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        with LOCK:
            with self.db:
                existing = self.db.execute('SELECT * FROM requests WHERE request_id=?',(request_id,)).fetchone()
                if existing:
                    if existing['fingerprint'] != fingerprint:
                        raise ConflictError('Idempotency key reused with different input')
                    return json.loads(existing['response_json'])
                result = perform()
                self.db.execute('INSERT INTO requests VALUES (?,?,?)',
                                (request_id, fingerprint, json.dumps(result,sort_keys=True)))
                return result

    def create_matter(self, title, request_id):
        if not isinstance(title,str) or not (1 <= len(title.strip()) <= 160):
            raise ValidationError('Matter title must contain 1-160 characters')
        title = title.strip()
        def action():
            m = {'id':str(uuid.uuid4()), 'title':title, 'status':'open','created_at':utcnow(),'version':1}
            self.db.execute('INSERT INTO matters VALUES (?,?,?,?,?)',tuple(m.values()))
            self._audit('matter.created',m['id'],title)
            return m
        return self._run(request_id,['matter',title],action)

    def add_entry(self,matter_id,kind,text,occurred_at,minutes,request_id):
        if kind not in ('note','time','task','deadline'): raise ValidationError('Unsupported entry kind')
        if not isinstance(text,str) or not (1 <= len(text.strip()) <= 2000):
            raise ValidationError('Text must contain 1-2000 characters')
        if not isinstance(minutes,int) or isinstance(minutes,bool) or minutes<0 or minutes>1440 or (kind!='time' and minutes!=0):
            raise ValidationError('Minutes must be 0-1440 for time entries and zero otherwise')
        try:
            parsed = datetime.fromisoformat(occurred_at.replace('Z','+00:00'))
            if parsed.tzinfo is None: raise ValueError()
        except (ValueError,AttributeError): raise ValidationError('An offset-aware ISO date/time is required')
        normalized = parsed.astimezone(timezone.utc).isoformat()
        text = text.strip()
        def action():
            if not self.db.execute('SELECT id FROM matters WHERE id=?',(matter_id,)).fetchone():
                raise NotFoundError('Matter not found')
            e = asdict(Entry(str(uuid.uuid4()),matter_id,kind,text,normalized,minutes))
            self.db.execute('INSERT INTO entries (id,matter_id,kind,text,occurred_at,minutes) VALUES (?,?,?,?,?,?)',tuple(e.values()))
            self._audit('entry.created',e['id'],json.dumps({'matter_id':matter_id,'kind':kind}))
            return e
        return self._run(request_id,['entry',matter_id,kind,text,normalized,minutes],action)

    def complete_task(self, entry_id, expected_version, request_id):
        if type(expected_version) is not int or expected_version<1: raise ValidationError('Invalid version')
        def action():
            task = self.db.execute('SELECT * FROM entries WHERE id=?',(entry_id,)).fetchone()
            if not task or task['kind'] != 'task': raise NotFoundError('Task not found')
            if task['version'] != expected_version: raise ConflictError('Version conflict: refresh before retry')
            if task['completed']: raise ConflictError('Already completed')
            self.db.execute('UPDATE entries SET completed=1, version=version+1 WHERE id=? AND version=?',(entry_id,expected_version))
            self._audit('task.completed',entry_id,str(expected_version+1))
            return {'id':entry_id,'completed':True,'version':expected_version+1}
        return self._run(request_id,['complete',entry_id,expected_version],action)

    def dashboard(self):
        matters=[dict(x) for x in self.db.execute('SELECT * FROM matters ORDER BY created_at DESC,id DESC')]
        entries=[dict(x) for x in self.db.execute('SELECT * FROM entries ORDER BY occurred_at ASC,id ASC')]
        return {'matters':matters,'entries':entries,'billable_minutes':sum(x['minutes'] for x in entries if x['kind']=='time'),
                'open_tasks':sum(x['kind']=='task' and not x['completed'] for x in entries),
                'deadlines':[x for x in entries if x['kind']=='deadline']}

    def verify_audit(self):
        prev='GENESIS'
        for x in self.db.execute('SELECT * FROM audit ORDER BY seq'):
            if x['prev_hash']!=prev: return False
            raw=json.dumps([x['at'],x['action'],x['object_id'],x['detail'],prev],separators=(',',':'))
            if sha256(raw.encode()).hexdigest()!=x['event_hash']: return False
            prev=x['event_hash']
        return True
