"""Portable fictional pilot package integration and adversarial acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from tools.build_offline_pilot_preview import build, collect


class PortablePreviewAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.archive = self.folder/'preview.zip'

    def tearDown(self):
        self.tmp.cleanup()

    def extract(self):
        build(self.archive)
        with ZipFile(self.archive) as archive:
            names = archive.namelist()
            self.assertTrue(all(n.startswith('mtl-fictional-preview/') for n in names))
            self.assertTrue(all('..' not in Path(n).parts for n in names))
            archive.extractall(self.folder)
        return self.folder/'mtl-fictional-preview'

    def invoke(self, location, *args):
        return subprocess.run(
            [sys.executable,'run_pilot.py',*args],
            cwd=str(location), text=True, capture_output=True,
            timeout=35, env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})

    def test_package_integrity_and_first_run_reopen(self):
        root = self.extract()
        valid = self.invoke(root,'--verify')
        self.assertEqual(valid.returncode,0,valid.stderr)
        self.assertIn('SHA-256 check: PASS',valid.stdout)
        help_result = self.invoke(root,'--help')
        self.assertEqual(help_result.returncode,0,help_result.stderr)
        self.assertIn('init',help_result.stdout)
        # Do not log credentials: inspect only the result code and existence.
        db = root/'new-fictional.sqlite3'
        setup = self.invoke(root,'init','--database',str(db))
        self.assertEqual(setup.returncode,0,setup.stderr)
        self.assertTrue(db.is_file())
        self.assertTrue((root/'new-fictional.sqlite3.write-fence.sqlite3').is_file())
        second = self.invoke(root,'init','--database',str(db))
        self.assertNotEqual(second.returncode,0)
        self.assertTrue(db.is_file())
        from hashlib import sha256
        manifest = json.loads((root/'MANIFEST.json').read_text())
        self.assertEqual(manifest['purpose'],'FICTIONAL OFFLINE PREVIEW')
        self.assertFalse(manifest['production_use'])
        self.assertFalse(manifest['independent_security_approval'])
        self.assertEqual(set(manifest['sha256']),set(collect()))
        for name,digest in manifest['sha256'].items():
            self.assertEqual(sha256((root/name).read_bytes()).hexdigest(),digest)

    def test_mutated_source_and_extra_source_fail_before_pilot(self):
        root=self.extract()
        changed=root/'src'/'offline_pilot.py'
        changed.write_bytes(changed.read_bytes()+b'\n# synthetic change\n')
        self.assertNotEqual(self.invoke(root,'--verify').returncode,0)
        changed.write_bytes(collect()['src/offline_pilot.py'])
        extra=root/'src'/'unapproved.py'
        extra.write_text('print(999)')
        self.assertNotEqual(self.invoke(root,'--verify').returncode,0)

    def test_package_never_contains_credentials_database_or_server(self):
        root=self.extract()
        with ZipFile(self.archive) as z:
            members=z.namelist()
            self.assertFalse(any(name.endswith('.sqlite3') for name in members))
            self.assertFalse(any(name.endswith('server.py') for name in members))
            self.assertFalse(any(name.endswith('secure_server.py') for name in members))
            self.assertFalse(any(name.endswith('src/__init__.py') for name in members))
        self.assertNotIn('token',json.loads((root/'MANIFEST.json').read_text())['sha256'])
        self.assertFalse((root/'src'/'secure_server.py').exists())

    def test_deterministic_archive_and_no_overwrite(self):
        first=build(self.archive)
        with self.assertRaises(FileExistsError):
            build(self.archive)
        second=build(self.folder/'preview2.zip')
        self.assertEqual(first['archive_sha256'],second['archive_sha256'])
        self.assertGreater(first['source_count'],5)

    def test_portable_human_launcher_is_packaged_and_checks_integrity(self):
        root = self.extract()
        helper = root / 'start_pilot.py'
        self.assertTrue(helper.is_file())
        result = subprocess.run(
            [sys.executable, str(helper), '--check'],
            cwd=str(root), text=True, capture_output=True, timeout=35)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Tk module: available', result.stdout)
        before = self.invoke(root, '--verify')
        self.assertEqual(before.returncode, 0)
        # A damaged published module must block the human launcher too.
        module = root / 'src' / 'offline_pilot.py'
        module.write_bytes(module.read_bytes() + b'\n# synthetic damage\n')
        denied = subprocess.run(
            [sys.executable, str(helper), '--check'],
            cwd=str(root), text=True, capture_output=True, timeout=35)
        self.assertEqual(denied.returncode, 2)
        self.assertIn('DENIED: package verification failed', denied.stderr)

    def test_portable_human_launcher_never_overwrites_existing_database(self):
        root = self.extract()
        existing = root / 'already.sqlite3'
        existing.write_bytes(b'KEEP-SYNTHETIC-DATA')
        result = subprocess.run(
            [sys.executable, 'start_pilot.py'],
            input='1\n' + str(existing) + '\n',
            cwd=str(root), text=True, capture_output=True, timeout=35)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(existing.read_bytes(), b'KEEP-SYNTHETIC-DATA')

    def test_platform_launchers_are_packaged_with_safe_local_entrypoint(self):
        root = self.extract()
        for filename in ('launch-windows.cmd', 'launch-macos.command', 'launch-linux.sh'):
            script = (root / filename).read_text(encoding='utf-8')
            self.assertIn('start_pilot.py', script)
            self.assertNotIn('curl ', script)
            self.assertNotIn('wget ', script)
            self.assertNotIn('pip install', script)
            self.assertNotIn('http://', script)
            self.assertNotIn('https://', script)
        with ZipFile(self.archive) as z:
            for filename in ('launch-macos.command', 'launch-linux.sh'):
                info = z.getinfo('mtl-fictional-preview/' + filename)
                self.assertEqual((info.external_attr >> 16) & 0o111, 0o111)
        self.assertTrue((root/'launch-windows.cmd').read_text().startswith('@echo off'))

    @unittest.skipIf(os.name == 'nt', 'POSIX shell acceptance runs only on POSIX')
    def test_posix_launcher_executes_real_verified_pilot_and_clean_cancel(self):
        import shutil
        if not shutil.which('python3'):
            self.skipTest('python3 not present on shell PATH')
        root = self.extract()
        result = subprocess.run(
            ['sh', 'launch-linux.sh'], input='\\n\\n', cwd=str(root),
            text=True, capture_output=True, timeout=35)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('FICTIONAL OFFLINE PILOT ONLY', result.stdout)
        self.assertIn('Tk module: available', result.stdout)

    def test_extracted_symlink_is_refused(self):
        if not hasattr(os,'symlink'):
            self.skipTest('Platform does not support symlinks')
        root=self.extract()
        target=root/'src'/'offline_pilot.py'
        original=target.read_bytes()
        target.unlink()
        try:
            os.symlink(root/'src'/'local_operator_gui.py',target)
        except (OSError,PermissionError):
            target.write_bytes(original)
            self.skipTest('Symlink creation disallowed')
        self.assertNotEqual(self.invoke(root,'--verify').returncode,0)


if __name__ == '__main__':
    unittest.main()
