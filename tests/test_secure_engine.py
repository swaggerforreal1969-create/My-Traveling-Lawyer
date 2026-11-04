import unittest
import tempfile
from pathlib import Path
from src.secure_engine import SecureCore, Denied, Stale, Invalid

class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.core=SecureCore()
        self.firm=self.core.provision_firm('Imaginary Firm')
        self.owner,self.owner_token=self.core.provision_user(self.firm,'Owner')
        self.editor,self.editor_token=self.core.provision_user(self.firm,'Editor')
        self.viewer,self.viewer_token=self.core.provision_user(self.firm,'Viewer')
        self.other_firm=self.core.provision_firm('Second Firm')
        self.outsider,self.out_token=self.core.provision_user(self.other_firm,'Outsider')
        self.m=self.core.create_matter(self.owner_token,'Fictional Matter')
    def tearDown(self):self.core.close()
    def assertDenied(self, fn, *args):
        with self.assertRaises(Denied):fn(*args)
    def test_owner_reads_own(self):self.assertEqual(1,len(self.core.list_matters(self.owner_token)))
    def test_ungranted_colleague_cannot_read(self):self.assertDenied(self.core.read_notes,self.editor_token,self.m['id'])
    def test_other_firm_cannot_read(self):self.assertDenied(self.core.read_notes,self.out_token,self.m['id'])
    def test_other_firm_cannot_grant(self):self.assertDenied(self.core.grant,self.owner_token,self.m['id'],self.outsider,'editor',1)
    def test_viewer_can_read(self):
        self.core.grant(self.owner_token,self.m['id'],self.viewer,'viewer',1)
        self.assertEqual([],self.core.read_notes(self.viewer_token,self.m['id']))
    def test_viewer_cannot_write(self):
        self.core.grant(self.owner_token,self.m['id'],self.viewer,'viewer',1)
        self.assertDenied(self.core.add_note,self.viewer_token,self.m['id'],'Secret')
    def test_editor_can_write(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        self.core.add_note(self.editor_token,self.m['id'],'Fictional')
        self.assertEqual(1,len(self.core.read_notes(self.owner_token,self.m['id'])))
    def test_editor_cannot_grant(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        self.assertDenied(self.core.grant,self.editor_token,self.m['id'],self.viewer,'viewer',2)
    def test_stale_grant_denied(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        with self.assertRaises(Stale):self.core.grant(self.owner_token,self.m['id'],self.viewer,'viewer',1)
        self.assertDenied(self.core.read_notes,self.viewer_token,self.m['id'])
    def test_passive_authorization_does_not_refresh_idle(self):
        from datetime import datetime, timezone, timedelta
        from hashlib import sha256
        digest=sha256(self.owner_token.encode()).hexdigest()
        old=(datetime.now(timezone.utc)-timedelta(seconds=240)).isoformat()
        self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',(old,digest))
        with self.core.passive_authorization():
            self.assertEqual(1,len(self.core.list_matters(self.owner_token)))
            self.assertEqual([],self.core.read_notes(self.owner_token,self.m['id']))
        self.assertEqual(self.core.db.execute(
            'SELECT last_seen_at FROM credentials WHERE token_digest=?',
            (digest,)).fetchone()['last_seen_at'],old)
        self.core.list_matters(self.owner_token)
        self.assertNotEqual(self.core.db.execute(
            'SELECT last_seen_at FROM credentials WHERE token_digest=?',
            (digest,)).fetchone()['last_seen_at'],old)

    def test_passive_auth_denies_expired_and_revoked(self):
        from datetime import datetime, timezone, timedelta
        from hashlib import sha256
        digest=sha256(self.owner_token.encode()).hexdigest()
        expired=(datetime.now(timezone.utc)-timedelta(
            seconds=self.core.IDLE_SECONDS+1)).isoformat()
        self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',(expired,digest))
        with self.core.passive_authorization():
            self.assertDenied(self.core.list_matters,self.owner_token)
        self.assertEqual(self.core.db.execute(
            'SELECT last_seen_at FROM credentials WHERE token_digest=?',
            (digest,)).fetchone()['last_seen_at'],expired)
        self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
                             (datetime.now(timezone.utc).isoformat(),digest))
        self.core.revoke_token(self.owner_token)
        with self.core.passive_authorization():
            self.assertDenied(self.core.list_matters,self.owner_token)

    def test_passive_context_restored_after_exception(self):
        from datetime import datetime, timezone, timedelta
        from hashlib import sha256
        digest=sha256(self.owner_token.encode()).hexdigest()
        old=(datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat()
        self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',(old,digest))
        with self.assertRaises(RuntimeError):
            with self.core.passive_authorization():
                raise RuntimeError('synthetic passive failure')
        self.core.list_matters(self.owner_token)
        self.assertNotEqual(self.core.db.execute(
            'SELECT last_seen_at FROM credentials WHERE token_digest=?',
            (digest,)).fetchone()['last_seen_at'],old)

    def test_passive_scope_does_not_leak_to_other_core(self):
        from datetime import datetime, timezone, timedelta
        from hashlib import sha256
        other=SecureCore()
        try:
            firm=other.provision_firm('Unrelated Test Firm')
            _,other_token=other.provision_user(firm,'Another Operator')
            other.create_matter(other_token,'Unrelated Fictional Matter')
            digest=sha256(other_token.encode()).hexdigest()
            previous=(datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat()
            other.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
                             (previous,digest))
            with self.core.passive_authorization():
                self.core.list_matters(self.owner_token)
                other.list_matters(other_token)
            actual=other.db.execute(
                'SELECT last_seen_at FROM credentials WHERE token_digest=?',
                (digest,)).fetchone()['last_seen_at']
            self.assertNotEqual(previous,actual)
        finally:
            other.close()

    def test_passive_scope_is_thread_local_on_same_core(self):
        import threading
        from datetime import datetime, timezone, timedelta
        from hashlib import sha256
        digest=sha256(self.editor_token.encode()).hexdigest()
        previous=(datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat()
        self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
                             (previous,digest))
        failures=[]
        def real_user_action():
            try:
                self.core.list_matters(self.editor_token)
            except Exception as exc:
                failures.append(str(type(exc).__name__))
        with self.core.passive_authorization():
            self.core.list_matters(self.owner_token)
            actor=threading.Thread(target=real_user_action)
            actor.start()
            actor.join(timeout=5)
            self.assertFalse(actor.is_alive())
        self.assertEqual(failures,[])
        actual=self.core.db.execute(
            'SELECT last_seen_at FROM credentials WHERE token_digest=?',
            (digest,)).fetchone()['last_seen_at']
        self.assertNotEqual(previous,actual)

    def test_nested_passive_scope_restores_previous_mode(self):
        from datetime import datetime, timezone, timedelta
        from hashlib import sha256
        digest=sha256(self.owner_token.encode()).hexdigest()
        previous=(datetime.now(timezone.utc)-timedelta(seconds=120)).isoformat()
        self.core.db.execute('UPDATE credentials SET last_seen_at=? WHERE token_digest=?',
                             (previous,digest))
        with self.core.passive_authorization():
            with self.core.passive_authorization():
                self.core.list_matters(self.owner_token)
            self.core.list_matters(self.owner_token)
            self.assertEqual(previous,self.core.db.execute(
                'SELECT last_seen_at FROM credentials WHERE token_digest=?',
                (digest,)).fetchone()['last_seen_at'])
        self.core.list_matters(self.owner_token)
        self.assertNotEqual(previous,self.core.db.execute(
            'SELECT last_seen_at FROM credentials WHERE token_digest=?',
            (digest,)).fetchone()['last_seen_at'])

    def test_task_transaction_revoked_before_admission_has_zero_write(self):
        task=self.core.create_task(self.owner_token,self.m['id'],'Fictional task',
                                   '2026-10-01T00:00:00Z')
        self.core.revoke_token(self.owner_token)
        self.assertDenied(self.core.complete_task,self.owner_token,task['id'],1)
        row=self.core.db.execute(
            'SELECT completed,version FROM tasks WHERE id=?',(task['id'],)).fetchone()
        self.assertEqual((row['completed'],row['version']),(0,1))

    def test_task_transaction_role_downgrade_denied_before_write(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        task=self.core.create_task(self.owner_token,self.m['id'],'Fictional task',
                                   '2026-10-01T00:00:00Z')
        version=self.core.db.execute(
            'SELECT version FROM matters WHERE id=?',(self.m['id'],)).fetchone()[0]
        self.core.grant(self.owner_token,self.m['id'],self.editor,'viewer',version)
        self.assertDenied(self.core.complete_task,self.editor_token,task['id'],1)
        row=self.core.db.execute(
            'SELECT completed,version FROM tasks WHERE id=?',(task['id'],)).fetchone()
        self.assertEqual((row['completed'],row['version']),(0,1))

    def test_task_transaction_rollback_on_audit_failure(self):
        from unittest.mock import patch
        task=self.core.create_task(self.owner_token,self.m['id'],'Fictional task',
                                   '2026-10-01T00:00:00Z')
        with patch.object(self.core,'_audit',side_effect=RuntimeError('synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.core.complete_task(self.owner_token,task['id'],1)
        row=self.core.db.execute(
            'SELECT completed,version FROM tasks WHERE id=?',(task['id'],)).fetchone()
        self.assertEqual((row['completed'],row['version']),(0,1))
        self.assertTrue(self.core.verify_audit())

    def test_task_transaction_separate_connection_writer_order(self):
        import threading
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'shared_fictional.db'
            a=SecureCore(path)
            try:
                firm=a.provision_firm('Fictional Shared Firm')
                _,owner=a.provision_user(firm,'Test Owner')
                matter=a.create_matter(owner,'Fictional Matter')
                task=a.create_task(owner,matter['id'],'Fictional task',
                                   '2026-10-01T00:00:00Z')
                b=SecureCore(path)
                try:
                    entered=threading.Event()
                    release=threading.Event()
                    results=[]
                    original=a._identity
                    def paused_identity(token):
                        entered.set()
                        if not release.wait(5):raise RuntimeError('Test barrier timeout')
                        return original(token)
                    def completion():
                        try:results.append(('complete',a.complete_task(owner,task['id'],1)))
                        except Exception as exc:results.append(('complete_error',type(exc).__name__))
                    def revocation():
                        try:b.revoke_token(owner);results.append(('revoked',True))
                        except Exception as exc:results.append(('revoke_error',type(exc).__name__))
                    with patch.object(a,'_identity',side_effect=paused_identity):
                        writer=threading.Thread(target=completion)
                        writer.start()
                        self.assertTrue(entered.wait(5))
                        rival=threading.Thread(target=revocation)
                        rival.start()
                        release.set()
                        writer.join(timeout=8)
                        rival.join(timeout=8)
                    self.assertFalse(writer.is_alive())
                    self.assertFalse(rival.is_alive())
                    self.assertEqual([x[0] for x in results].count('complete'),1)
                    self.assertEqual([x[0] for x in results].count('revoked'),1)
                    self.assertEqual(a.db.execute(
                        'SELECT completed,version FROM tasks WHERE id=?',
                        (task['id'],)).fetchone()['completed'],1)
                    self.assertDenied(a.complete_task,owner,task['id'],1)
                    self.assertTrue(a.verify_audit())
                finally:b.close()
            finally:a.close()

    def test_revocation(self):
        self.core.revoke_token(self.owner_token)
        self.assertDenied(self.core.list_matters,self.owner_token)
    def test_fake_token(self):self.assertDenied(self.core.list_matters,'not_a_valid_token')
    def test_wrong_firm_not_listed(self):self.assertEqual([],self.core.list_matters(self.out_token))
    def test_no_permission_leak_on_unknown_matter(self):self.assertDenied(self.core.read_notes,self.owner_token,'bogus')
    def test_persistent_authorization(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'test.db'
            a=SecureCore(path); fid=a.provision_firm('Test'); uid,token=a.provision_user(fid,'Tester'); a.create_matter(token,'Test'); a.close()
            b=SecureCore(path); self.assertEqual(1,len(b.list_matters(token)));b.close()
    def test_invalid_role(self):
        with self.assertRaises(Invalid):self.core.grant(self.owner_token,self.m['id'],self.editor,'owner',1)
    def test_missing_token(self):self.assertDenied(self.core.list_matters,None)
    def test_viewer_cannot_see_another_matter(self):
        self.core.grant(self.owner_token,self.m['id'],self.viewer,'viewer',1)
        new=self.core.create_matter(self.owner_token,'Other case')
        self.assertDenied(self.core.read_notes,self.viewer_token,new['id'])
    def test_stale_cannot_escalate(self):
        self.core.grant(self.owner_token,self.m['id'],self.editor,'viewer',1)
        with self.assertRaises(Stale):self.core.grant(self.owner_token,self.m['id'],self.editor,'editor',1)
        self.assertDenied(self.core.add_note,self.editor_token,self.m['id'],'Nope')

if __name__=='__main__':unittest.main()
