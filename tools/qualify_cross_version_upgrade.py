"""Exact-code-version frozen upgrade with PRIVATE FICTIONAL TEST-ONLY backup.

Build A is checked out from protected PR #105. Build B is the current exact
source. No real client files, no public installer, no product backup feature.
No claim of encrypted backup, transactionally atomic hot snapshot, or signing.
"""
from __future__ import annotations
import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
from tempfile import TemporaryDirectory

from tools.qualify_fictional_install import (
    stage_version, executable_at, database_snapshot, read_state,
    reject_wrong_code,
)
from src.offline_pilot import initialize_fictional_pilot
from src.durable_local_write_fence import LocalWriteFence
from src.secure_engine import SecureCore


def _run_private(app: Path, command: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(executable_at(app)), command], cwd=str(app),
                          capture_output=True, text=True, timeout=90)


def _backup_file(source: Path, dest: Path) -> None:
    with closing(sqlite3.connect(str(source), timeout=10)) as inp:
        with closing(sqlite3.connect(str(dest), timeout=10)) as out:
            inp.backup(out)


def offline_test_backup(db: Path, folder: Path) -> Path:
    """Exclusive disposable backup when all fictional operators are CLOSED.

    Checking before and after is not an atomic cross-database snapshot;
    never use on live databases or as a consumer backup feature.
    """
    if folder.exists() or folder.is_symlink():
        raise FileExistsError("Existing backup never overwritten")
    if not db.is_file() or db.is_symlink():
        raise ValueError("Fictional database required")
    fence = LocalWriteFence(db)
    if fence.is_pending():
        raise ValueError("Pending write prohibits new backup")
    sidecar = db.with_name(db.name + ".write-fence.sqlite3")
    if sidecar.is_symlink() or not sidecar.is_file():
        raise ValueError("Bound sidecar required")
    before = database_snapshot(db)
    folder.mkdir(mode=0o700)
    try:
        for name, original in (("database.sqlite3", db),
                               ("fence.sqlite3", sidecar)):
            _backup_file(original, folder / name)
        if fence.is_pending() or database_snapshot(db) != before:
            raise ValueError("Fictional database changed during backup")
        with closing(sqlite3.connect(str(folder / "database.sqlite3"))) as main:
            anchor = main.execute(
                "SELECT marker FROM local_write_fence_anchor WHERE slot=1"
            ).fetchone()
        with closing(sqlite3.connect(str(folder / "fence.sqlite3"))) as paired:
            marker = paired.execute(
                "SELECT marker FROM fence_marker WHERE slot=1"
            ).fetchone()
            pending = paired.execute("SELECT count(*) FROM fence").fetchone()[0]
        if anchor is None or marker is None or anchor[0] != marker[0] or pending:
            raise ValueError("Fictional backup mismatch or unresolved fence")
        digest = {name: sha256((folder / name).read_bytes()).hexdigest()
                  for name in ("database.sqlite3", "fence.sqlite3")}
        (folder / "checksums.json").write_text(
            json.dumps(digest, sort_keys=True) + "\n", encoding="utf-8")
        return folder
    except BaseException:
        shutil.rmtree(folder)
        raise


def restore_test_backup(folder: Path, dest: Path) -> Path:
    """Reject tampering and overwrite; clean only newly reserved test files."""
    folder, dest = Path(folder), Path(dest)
    sidecar = dest.with_name(dest.name + ".write-fence.sqlite3")
    if dest.exists() or dest.is_symlink() or sidecar.exists() or sidecar.is_symlink():
        raise FileExistsError("Existing fictional records never overwritten")
    if folder.is_symlink() or not folder.is_dir() or not dest.parent.is_dir():
        raise ValueError("Private fictional backup/restore path denied")
    created_main = created_sidecar = False
    try:
        digest = json.loads((folder / "checksums.json").read_text())
        if set(digest) != {"database.sqlite3", "fence.sqlite3"}:
            raise ValueError("Incomplete fictional backup")
        for name, value in digest.items():
            item = folder / name
            if item.is_symlink() or not item.is_file() or (
                    sha256(item.read_bytes()).hexdigest() != value):
                raise ValueError("Tampered fictional backup")
        with dest.open("xb") as target:
            created_main = True
            target.write((folder / "database.sqlite3").read_bytes())
        with sidecar.open("xb") as target:
            created_sidecar = True
            target.write((folder / "fence.sqlite3").read_bytes())
        if LocalWriteFence(dest).is_pending():
            raise ValueError("Pending backup not restorable")
        with closing(SecureCore(dest)) as core:
            if not core.verify_audit():
                raise ValueError("Fictional audit invalid after restore")
        return dest
    except BaseException:
        if created_sidecar and sidecar.exists():
            sidecar.unlink()
        if created_main and dest.exists():
            dest.unlink()
        raise


def qualify_upgrade(old_source: Path, new_source: Path) -> None:
    with TemporaryDirectory(prefix="mtl-fictional-cross-version-") as tmp:
        base = Path(tmp)
        old = stage_version(old_source, base / "fictional-prior")
        new = stage_version(new_source, base / "fictional-new")
        if sha256(executable_at(old).read_bytes()).digest() == (
                sha256(executable_at(new).read_bytes()).digest()):
            raise RuntimeError("Different code versions required")
        info_new = _run_private(new, "--self-test-build-info")
        info_old = _run_private(old, "--self-test-build-info")
        if (info_new.returncode != 0 or
                "Fictional upgrade build: cross-version-v2" not in info_new.stdout or
                info_old.returncode == 0):
            raise RuntimeError("Executable functional versions not distinct")
        db = base / "fictional-install-test-cross-version.sqlite3"
        token = initialize_fictional_pilot(db)["editor_token"]
        original = database_snapshot(db)
        read_state(old, db, token, expect_pending=False)
        reject_wrong_code(old, db)
        backup = offline_test_backup(db, base / "fictional-private-backup")
        restored = restore_test_backup(
            backup, base / "fictional-install-test-restored.sqlite3")
        if database_snapshot(restored) != original:
            raise RuntimeError("Backup changed fictional records")
        for app in (old, new):
            for database in (db, restored):
                read_state(app, database, token, expect_pending=False)
                reject_wrong_code(app, database)
        if database_snapshot(db) != original or database_snapshot(restored) != original:
            raise RuntimeError("Upgrade changed private fictional records")
        fence = LocalWriteFence(db)
        fence.begin()
        for app in (old, new):
            read_state(app, db, token, expect_pending=True)
        if not fence.is_pending() or database_snapshot(db) != original:
            raise RuntimeError("Upgrade replayed or cleared unresolved write")
        try:
            offline_test_backup(db, base / "must-not-backup-pending")
        except ValueError:
            pass
        else:
            raise RuntimeError("Backup permitted unresolved write")
        damaged = base / "synthetic-damaged-backup"
        shutil.copytree(backup, damaged)
        with (damaged / "fence.sqlite3").open("ab") as f:
            f.write(b"\nSYNTHETIC-TAMPER\n")
        try:
            restore_test_backup(
                damaged, base / "fictional-install-test-rejected.sqlite3")
        except ValueError:
            pass
        else:
            raise RuntimeError("Tampered backup was allowed")
        for app in (old, new):
            if _run_private(app, "--verify").returncode:
                raise RuntimeError("An application version became unverified")
    print("Different frozen builds: private fictional records, backup/restore, "
          "authorization, unresolved fence and tamper denial: PASS")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--old-source", type=Path, required=True)
    p.add_argument("--new-source", type=Path, required=True)
    a = p.parse_args(argv)
    qualify_upgrade(a.old_source, a.new_source)


if __name__ == "__main__":
    main()
