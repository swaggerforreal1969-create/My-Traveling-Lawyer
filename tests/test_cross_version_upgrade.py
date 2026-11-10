"""Disposable cross-version backup denial without real client data."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from tools.qualify_cross_version_upgrade import offline_test_backup, restore_test_backup
from src.offline_pilot import initialize_fictional_pilot
from src.durable_local_write_fence import LocalWriteFence


class TestFictionalOfflineBackup(unittest.TestCase):
    def test_exclusive_paired_restore_and_overwrite_denial(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            db = base / "fictional-install-test-original.sqlite3"
            initialize_fictional_pilot(db)
            backup = offline_test_backup(db, base / "private-fixture")
            self.assertTrue((backup / "checksums.json").is_file())
            with self.assertRaises(FileExistsError):
                offline_test_backup(db, backup)
            restored = restore_test_backup(
                backup, base / "fictional-install-test-restored.sqlite3")
            self.assertTrue(restored.is_file())
            self.assertFalse(LocalWriteFence(restored).is_pending())
            with self.assertRaises(FileExistsError):
                restore_test_backup(backup, db)
            with self.assertRaises(FileExistsError):
                restore_test_backup(backup, restored)

    def test_unresolved_fence_blocks_backup(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            db = base / "fictional-install-test-pending.sqlite3"
            initialize_fictional_pilot(db)
            fence = LocalWriteFence(db)
            fence.begin()
            dest = base / "must-not-exist"
            with self.assertRaises(ValueError):
                offline_test_backup(db, dest)
            self.assertFalse(dest.exists())
            self.assertTrue(LocalWriteFence(db).is_pending())

    def test_modified_backup_denied_before_creating_records(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            db = base / "fictional-install-test-original.sqlite3"
            initialize_fictional_pilot(db)
            saved = offline_test_backup(db, base / "private-fixture")
            with (saved / "fence.sqlite3").open("ab") as f:
                f.write(b"fake")
            new = base / "fictional-install-test-forbidden.sqlite3"
            with self.assertRaises(ValueError):
                restore_test_backup(saved, new)
            self.assertFalse(new.exists())


if __name__ == "__main__":
    unittest.main()
