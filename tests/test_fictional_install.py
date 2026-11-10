"""Staged-version installation safety tests; no real clients or distribution."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os

from tools.qualify_fictional_install import (
    assert_private_tree, stage_version,
)


class PrivateStagedInstallTests(TestCase):
    def test_existing_target_and_symlink_are_never_overwritten(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "original"
            source.mkdir()
            (source / "fake").write_text("original", encoding="utf-8")
            dest = root / "existing"
            dest.mkdir()
            sentinel = dest / "private-existing.sqlite3"
            sentinel.write_text("protected")
            with self.assertRaises(FileExistsError):
                stage_version(source, dest)
            self.assertEqual(sentinel.read_text(), "protected")
            if hasattr(os, "symlink"):
                link = root / "linked-install"
                try:
                    link.symlink_to(dest, target_is_directory=True)
                except (OSError, PermissionError):
                    pass
                else:
                    with self.assertRaises(FileExistsError):
                        stage_version(source, link)
                    self.assertEqual(sentinel.read_text(), "protected")

    def test_external_symlink_in_source_is_denied(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, outside = root / "source", root / "private"
            source.mkdir()
            outside.write_text("PRIVATE")
            link = source / "unexpected"
            try:
                link.symlink_to(outside)
            except (OSError, PermissionError):
                self.skipTest("Host has no symlink support")
            with self.assertRaises(ValueError):
                assert_private_tree(source)
            self.assertEqual(outside.read_text(), "PRIVATE")

    def test_real_process_termination_leaves_only_marked_stage_and_retry_works(self):
        """A process killed AFTER copying must never publish partial app."""
        import subprocess
        import sys
        from types import SimpleNamespace
        from tools.qualify_fictional_install import (
            executable_at, incomplete_copies, clean_incomplete_copies,
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "approved-fictional-bundle"
            source.mkdir()
            executable_at(source).write_bytes(b"FICTIONAL EXECUTABLE TEST")
            old = root / "protected-prior-app"
            old.mkdir()
            (old / "old-version.txt").write_bytes(b"KEEP PRIOR")
            practice = root / "external-fictional-practice.sqlite3"
            practice.write_bytes(b"KEEP ALL PRACTICE RECORDS")
            target = root / "new-version"
            child = """
import os, pathlib, sys
from unittest.mock import patch
import tools.qualify_fictional_install as m
original = m.shutil.copytree
def terminate_after_copy(src, dst, **kw):
    original(src, dst, **kw)
    os._exit(86)
with patch.object(m.shutil, 'copytree', side_effect=terminate_after_copy):
    m.stage_version(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
"""
            result = subprocess.run(
                [sys.executable, "-c", child, str(source), str(target)],
                cwd=str(Path(__file__).resolve().parent.parent),
                capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 86)
            self.assertFalse(target.exists())
            self.assertEqual(len(incomplete_copies(target)), 1)
            unrelated = root / ".mtl-new-version-pending-unrelated"
            unrelated.mkdir()
            (unrelated / "private.sqlite3").write_bytes(b"NOT OUR STAGE")
            self.assertEqual(clean_incomplete_copies(target), 1)
            self.assertEqual((unrelated / "private.sqlite3").read_bytes(),
                             b"NOT OUR STAGE")
            with patch("tools.qualify_fictional_install.subprocess.run",
                       return_value=SimpleNamespace(
                           returncode=0, stdout="integrity: PASS")):
                self.assertEqual(stage_version(source, target), target)
            self.assertTrue(executable_at(target).is_file())
            self.assertEqual(incomplete_copies(target), [])
            with self.assertRaises(FileExistsError):
                clean_incomplete_copies(target)
            self.assertEqual(practice.read_bytes(),
                             b"KEEP ALL PRACTICE RECORDS")
            self.assertEqual((old / "old-version.txt").read_bytes(), b"KEEP PRIOR")

    def test_failed_integrity_never_exposes_unverified_app(self):
        from types import SimpleNamespace
        from tools.qualify_fictional_install import executable_at
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fictional-source"
            source.mkdir()
            executable_at(source).write_bytes(b"TEST ONLY")
            dest = root / "new"
            with patch("tools.qualify_fictional_install.subprocess.run",
                       return_value=SimpleNamespace(returncode=2, stdout="DENIED")):
                with self.assertRaises(RuntimeError):
                    stage_version(source, dest)
            self.assertFalse(dest.exists())
            self.assertFalse(list(root.glob(".mtl-new-pending-*")))

    def test_missing_source_refuses_and_creates_no_destination(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            dst = root / "new"
            with self.assertRaises(ValueError):
                stage_version(root / "absent", dst)
            self.assertFalse(dst.exists())
