"""Qualify a private, unsigned fictional onedir app folder replacement.

This is an internal test of staged, versioned copies, NOT a customer installer,
signing, distribution, software auto-updater, or real legal-record migration.
"""
from __future__ import annotations
from contextlib import closing
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.build_self_contained_pilot import APP_NAME
from src.offline_pilot import initialize_fictional_pilot
from src.durable_local_write_fence import LocalWriteFence


def executable_at(folder: Path) -> Path:
    return folder / (APP_NAME + (".exe" if os.name == "nt" else ""))


def assert_private_tree(source: Path) -> None:
    source = Path(source)
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Untrusted fictional source folder")
    for item in source.rglob("*"):
        if item.is_symlink():
            if item.readlink().is_absolute():
                raise ValueError("Absolute link inside fictional package denied")
            if not item.resolve(strict=True).is_relative_to(source.resolve()):
                raise ValueError("Symlink outside fictional package denied")


def stage_version(source: Path, destination: Path) -> Path:
    """Exclusive install to NEW folder; never modify or replace prior version."""
    source, destination = Path(source), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Existing installed files never overwritten")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError("Parent install folder missing or linked")
    assert_private_tree(source)
    if not executable_at(source).is_file():
        raise ValueError("Fictional executable not found")
    try:
        # copytree itself creates a new directory exclusively, rejecting a
        # competing existing path. Any failed private copy is removed.
        shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=False)
        check = subprocess.run([str(executable_at(destination)), "--verify"],
                               cwd=str(destination), capture_output=True,
                               text=True, timeout=80)
        if check.returncode != 0 or "integrity: PASS" not in check.stdout:
            raise RuntimeError("Installed fictional package verification denied")
        return destination
    except BaseException:
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        raise


def read_state(app: Path, database: Path, token: str, expect_pending: bool) -> None:
    # Test-only authenticated inspection by the *frozen* executable, never
    # passing tokens through process arguments, logs or environment variables.
    input_data = json.dumps({"database": str(database), "token": token}) + "\n"
    run = subprocess.run([str(executable_at(app)), "--self-test-readonly"],
                         input=input_data, capture_output=True, text=True,
                         cwd=str(app), timeout=80)
    target = ("write fence UNRESOLVED" if expect_pending else "write fence CLEAR")
    if run.returncode != 0 or target not in run.stdout:
        raise RuntimeError("Frozen persisted-record readback denied")


def reject_wrong_code(app: Path, database: Path) -> None:
    attempt = subprocess.run(
        [str(executable_at(app)), "--self-test-readonly"],
        input=json.dumps({"database": str(database), "token": "INCORRECT-FICTIONAL-CODE"}) + "\n",
        capture_output=True, text=True, cwd=str(app), timeout=80)
    if attempt.returncode == 0:
        raise RuntimeError("Unauthorized fictional readback unexpectedly allowed")


def database_snapshot(database: Path) -> tuple:
    # App persistence boundary is independent of its executable directory.
    # sqlite3.Connection.__exit__ does not close the file handle on Windows.
    # Use explicit closing so temporary client records remain replaceable.
    with closing(sqlite3.connect(str(database))) as conn:
        results = (
            conn.execute("SELECT count(*) FROM firms").fetchone()[0],
            conn.execute("SELECT count(*) FROM matters").fetchone()[0],
            conn.execute("SELECT count(*) FROM tasks WHERE completed=0").fetchone()[0],
            conn.execute("SELECT count(*) FROM source_second_review").fetchone()[0],
            tuple(conn.execute(
                "SELECT row_hash FROM audit_chain ORDER BY seq").fetchall()),
            tuple(conn.execute(
                "SELECT marker FROM local_write_fence_anchor").fetchall()),
        )
    return results


def qualify(source: Path) -> None:
    source = Path(source).resolve()
    assert_private_tree(source)
    with TemporaryDirectory(prefix="fictional-versioned-install-") as tmp:
        base = Path(tmp)
        app_a = stage_version(source, base / "fictional-version-a")
        db = base / "fictional-install-test-preserved.sqlite3"
        created = initialize_fictional_pilot(db)
        assert db.is_file() and db.with_name(db.name + ".write-fence.sqlite3").is_file()
        token = created["editor_token"]
        before = database_snapshot(db)
        read_state(app_a, db, token, expect_pending=False)
        reject_wrong_code(app_a, db)
        app_b = stage_version(source, base / "fictional-version-b")
        assert app_a.exists() and app_b.exists()
        if database_snapshot(db) != before:
            raise RuntimeError("Fictional records altered by application replacement")
        read_state(app_b, db, token, expect_pending=False)
        reject_wrong_code(app_b, db)
        if database_snapshot(db) != before:
            raise RuntimeError("Fictional audit or records changed by reopening")
        # A crash-like, unresolved local write reservation is never cleared
        # just because a new version of the app is installed.
        fence = LocalWriteFence(db)
        fence.begin()
        assert fence.is_pending()
        read_state(app_b, db, token, expect_pending=True)
        if not LocalWriteFence(db).is_pending():
            raise RuntimeError("Replacement cleared uncertain write fence")
        if database_snapshot(db) != before:
            raise RuntimeError("Replacement replayed or changed a write")
        # No embedded user database or token is allowed inside either app.
        for folder in (app_a, app_b):
            for item in folder.rglob("*"):
                if item.is_file() and item.suffix == ".sqlite3":
                    raise RuntimeError("Installed program includes fictional user records")
        # Damage the isolated NEW version, require strict denial; the old
        # verified version and separate user records remain untouched.
        matches = list(app_b.rglob("mtl-fictional-preview/start_pilot.py"))
        if len(matches) != 1:
            raise RuntimeError("Installed launcher integrity path unexpected")
        file = matches[0]
        file.write_bytes(file.read_bytes() + b"\n# tamper-only fictional test\n")
        deny = subprocess.run([str(executable_at(app_b)), "--verify"],
                              capture_output=True, text=True, cwd=str(app_b),
                              timeout=80)
        if deny.returncode == 0:
            raise RuntimeError("Altered installed package was allowed")
        checked = subprocess.run([str(executable_at(app_a)), "--verify"],
                                 capture_output=True, text=True, cwd=str(app_a),
                                 timeout=80)
        if checked.returncode != 0:
            raise RuntimeError("Prior version damaged by attempted replacement")
        if database_snapshot(db) != before or not LocalWriteFence(db).is_pending():
            raise RuntimeError("Tampering damaged separate fictional records")
    print("Fictional staged installation: two versions, preserved records, "
          "denied unauthorized access, unresolved fence and tamper: PASS")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args(argv)
    qualify(args.source)


if __name__ == "__main__":
    main()
