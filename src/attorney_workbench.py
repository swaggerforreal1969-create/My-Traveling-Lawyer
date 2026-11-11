"""Experimental authenticated matter workbench, strictly local and fictional.

Combines authorized matter listing, bounded task triage and optimistic task
completion without providing legal deadlines, source authenticity or AI output.
No HTTP listener, network access, or new authority is introduced.
"""
from datetime import datetime, timezone
from .secure_engine import Denied, Invalid, Stale


class AttorneyWorkbench:
    MAX_MATTERS = 100
    MAX_TASKS = 100

    def __init__(self, core):
        self.core = core

    def matters(self, token):
        """One authenticated overview, without matter names or notes."""
        with self.core.authorized_transaction():
            actor = self.core._identity(token)
            rows = self.core.db.execute('''SELECT m.id,m.version,g.role FROM matters m
                JOIN grants g ON g.matter_id=m.id
                WHERE m.firm_id=? AND g.user_id=? ORDER BY m.id LIMIT ?''',
                (actor['firm_id'], actor['id'], self.MAX_MATTERS + 1)).fetchall()
            if len(rows) > self.MAX_MATTERS:
                raise Invalid('Too many matters; pagination required')
            return {'schema':'mtl.private.workbench.index.v1',
                    'matters':[{'matter_id':r['id'],'version':r['version'],'role':r['role']} for r in rows],
                    'legal_deadlines_verified':False,'legal_sources_authenticated':False,
                    'court_filing_approved':False,'outbound_ai_transmission':False}

    def matter(self, token, matter_id, *, now=None):
        """Matter-scoped, permissions-checked task inbox; no private note text."""
        if not isinstance(matter_id, str) or not 1 <= len(matter_id) <= 64:
            raise Invalid('Invalid matter identifier')
        if now is None:
            now = datetime.now(timezone.utc)
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise Invalid('Timezone-aware time required')
        with self.core.authorized_transaction():
            actor = self.core._identity(token)
            grant = self.core._role(actor,matter_id,('owner','editor','viewer'))
            rows = self.core.db.execute('''SELECT id,text,due_at,version FROM tasks
                WHERE matter_id=? AND completed=0 ORDER BY due_at,id LIMIT ?''',
                (matter_id,self.MAX_TASKS+1)).fetchall()
            if len(rows) > self.MAX_TASKS:
                raise Invalid('Task pagination required')
            tasks=[]
            for r in rows:
                try:
                    due=datetime.fromisoformat(r['due_at'])
                    if due.tzinfo is None: raise ValueError('naive')
                except (TypeError,ValueError):
                    raise Invalid('Invalid stored task date')
                tasks.append({'task_id':r['id'],'text':r['text'],'version':r['version'],
                              'user_entered_due_at':r['due_at'],
                              'past_user_entered_date':due < now})
            return {'schema':'mtl.private.workbench.matter.v1',
                    'matter_id':matter_id,'matter_version':grant['version'],
                    'can_complete_tasks':grant['role'] in ('owner','editor'),
                    'open_tasks':tasks,
                    'legal_deadlines_verified':False,
                    'legal_sources_authenticated':False,
                    'court_filing_approved':False,
                    'outbound_ai_transmission':False,
                    'notice':'User-entered dates are not court deadlines. Independently verify current official law.'}

    def complete(self, token, matter_id, task_id, expected_version):
        """One verified task completion; fails closed if task is from another matter."""
        if not isinstance(matter_id,str) or not 1 <= len(matter_id) <= 64:
            raise Invalid('Invalid matter')
        if not isinstance(task_id,str) or not 1 <= len(task_id) <= 64:
            raise Invalid('Invalid task')
        if type(expected_version) is not int or expected_version < 1:
            raise Invalid('Invalid task version')
        result=self.core.complete_task(token,task_id,expected_version,
                                        expected_matter_id=matter_id)
        return {'schema':'mtl.private.workbench.complete.v1',
                'task_id':result['task_id'],'completed':True,
                'version':result['version'],
                'legal_deadlines_verified':False,
                'court_filing_approved':False}
