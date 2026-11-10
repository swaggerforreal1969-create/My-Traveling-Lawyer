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

    def test_missing_source_refuses_and_creates_no_destination(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            dst = root / "new"
            with self.assertRaises(ValueError):
                stage_version(root / "absent", dst)
            self.assertFalse(dst.exists())
