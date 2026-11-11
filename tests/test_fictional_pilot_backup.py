"""Fictional-only credential-free backup and clean-location recovery tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from hashlib import sha256
from contextlib import redirect_stdout
from io import StringIO
import json
import os
import unittest

from src.offline_pilot import initialize_fictional_pilot, main
from src.fictional_pilot_backup import (
    backup_fictional_pilot, restore_fictional_pilot)
from src.secure_engine import SecureCore, Denied
from src.durable_local_write_fence import LocalWriteFence
from src.local_operator_gui import LocalOperatorController


class FictionalBackupRestoreAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.path=Path(self.tmp.name)/'original.sqlite3'
        self.archive=Path(self.tmp.name)/'private-fictional.json'
        self.restored=Path(self.tmp.name)/'restored.sqlite3'
        self.tokens=initialize_fictional_pilot(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_credential_free_record_restore_new_tokens_and_audit(self):
        with SecureCoreContext(self.path) as core:
            client=LocalOperatorController(core,self.tokens['reviewer_token'],
                                            durable_fence=LocalWriteFence(self.path))
            client.list_matters()
            client.select(0)
            self.assertEqual(client.review(0,'corroborated_manually',
                'Fictional evidence independently checked by reviewer',True).status,
                'review_committed')
            self.assertEqual(client.complete(0,True).status,
                             'completed_and_refreshed')
            self.assertTrue(core.verify_audit())
            before=core.db.execute(
                'SELECT count(*) FROM audit_chain').fetchone()[0]
        result=backup_fictional_pilot(self.path,self.tokens['editor_token'],
                                     self.archive)
        raw=self.archive.read_bytes()
        for token in (self.tokens['editor_token'],self.tokens['reviewer_token']):
            self.assertNotIn(token.encode(),raw)
            self.assertNotIn(sha256(token.encode()).hexdigest().encode(),raw)
        self.assertNotIn(b'token_digest',raw)
        self.assertNotIn(b'credentials',raw)
        self.assertNotIn(b'recovery_codes',raw)
        self.assertNotIn(b'device_keys',raw)
        self.assertEqual(len(result['sha256']),64)
        out=restore_fictional_pilot(self.archive,self.restored)
        self.assertEqual(len(out['accounts']),2)
        self.assertNotEqual(out['accounts'][0]['token'],self.tokens['editor_token'])
        self.assertTrue(self.restored.is_file())
        with SecureCoreContext(self.restored) as core:
            self.assertTrue(core.verify_audit())
            self.assertEqual(core.db.execute(
                'SELECT count(*) FROM audit_chain').fetchone()[0],before)
            self.assertEqual(core.db.execute(
                'SELECT count(*) FROM tasks WHERE completed=1').fetchone()[0],1)
            self.assertEqual(core.db.execute(
                'SELECT count(*) FROM source_second_review').fetchone()[0],1)
            for original in (self.tokens['editor_token'],self.tokens['reviewer_token']):
                with self.assertRaises(Denied):
                    core._identity(original)
            fresh={a['user']:a['token'] for a in out['accounts']}
            reviewer=LocalOperatorController(
                core,fresh['Independent Fictional Reviewer'],
                durable_fence=LocalWriteFence(self.restored))
            reviewer.list_matters()
            reviewer.select(0)
            self.assertEqual(reviewer.counts(),(0,0))
            self.assertFalse(LocalWriteFence(self.restored).is_pending())
        self.assertEqual(raw,self.archive.read_bytes())

    def test_no_overwrite_of_source_archive_or_destination(self):
        backup_fictional_pilot(self.path,self.tokens['editor_token'],self.archive)
        original=self.archive.read_bytes()
        with self.assertRaises(Denied):
            backup_fictional_pilot(self.path,self.tokens['editor_token'],self.archive)
        self.assertEqual(self.archive.read_bytes(),original)
        restore_fictional_pilot(self.archive,self.restored)
        previous=self.restored.read_bytes()
        with self.assertRaises(Denied):
            restore_fictional_pilot(self.archive,self.restored)
        self.assertEqual(previous,self.restored.read_bytes())

    def test_backup_denies_viewer_revoked_token_and_unresolved_write(self):
        with SecureCoreContext(self.path) as core:
            other=core.provision_user(
                core.db.execute('SELECT id FROM firms').fetchone()['id'],
                'Viewer only')
            core.grant(self.tokens['editor_token'],
                       core.db.execute('SELECT id FROM matters').fetchone()['id'],
                       other[0],'viewer',2)
            with self.assertRaises(Denied):
                backup_fictional_pilot(self.path,other[1],self.archive)
            core.revoke_token(self.tokens['editor_token'])
        with self.assertRaises(Denied):
            backup_fictional_pilot(self.path,self.tokens['editor_token'],self.archive)
        fence=LocalWriteFence(self.path)
        fence.begin()
        with self.assertRaises(Denied):
            backup_fictional_pilot(self.path,self.tokens['reviewer_token'],self.archive)
        self.assertFalse(self.archive.exists())

    def test_archive_corruption_and_secret_tables_fail_closed(self):
        backup_fictional_pilot(self.path,self.tokens['editor_token'],self.archive)
        original=self.archive.read_bytes()
        document=json.loads(original)
        document['payload']['tables']['tasks']['rows'][0][0]='forged'
        self.archive.write_text(json.dumps(document))
        with self.assertRaises(Denied):
            restore_fictional_pilot(self.archive,self.restored)
        self.assertFalse(self.restored.exists())
        self.archive.write_bytes(original)
        with SecureCoreContext(self.path) as core:
            core.db.execute('CREATE TABLE private_secret (value TEXT)')
        with self.assertRaises(Denied):
            backup_fictional_pilot(self.path,self.tokens['editor_token'],
                                    self.archive.with_name('unsafe.json'))

    def test_symlink_and_missing_parent_denial(self):
        if hasattr(os,'symlink'):
            link=self.restored
            os.symlink(self.path,link)
            with self.assertRaises(Denied):
                restore_fictional_pilot(self.archive,link)
            link.unlink()
        with self.assertRaises(Denied):
            restore_fictional_pilot(self.archive,
                                    self.restored.parent/'absent'/'new.db')

    def test_backup_cli_does_not_print_original_token(self):
        with patch('src.offline_pilot.getpass',return_value=self.tokens['editor_token']):
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(main(['backup','--database',str(self.path),
                                       '--archive',str(self.archive)]),0)
        self.assertNotIn(self.tokens['editor_token'],output.getvalue())
        self.assertIn('Credential-free FICTIONAL backup',output.getvalue())


class SecureCoreContext:
    def __init__(self,path):
        self.core=SecureCore(path)
    def __enter__(self):
        return self.core
    def __exit__(self,*args):
        self.core.close()


if __name__=='__main__':
    unittest.main()
