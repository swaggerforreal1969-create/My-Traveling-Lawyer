"""Frozen NONPRODUCTION-only bootstrap for the authorized fictional preview.

The builder replaces the pinned digest. SHA-256 here is NOT code signing.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

MANIFEST_SHA256 = "__MANIFEST_SHA256__"
PILOT_DIR = "mtl-fictional-preview"


def verify_tree(root: Path, manifest_sha: str) -> None:
    """Check the original approved preview before executing any external code."""
    root = Path(root)
    manifest = root / "MANIFEST.json"
    if root.is_symlink() or manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("Fictional package integrity denied")
    raw = manifest.read_bytes()
    if len(manifest_sha) != 64 or hashlib.sha256(raw).hexdigest() != manifest_sha:
        raise RuntimeError("Fictional package manifest mismatch")
    assets = json.loads(raw).get("asset_sha256", {})
    runner = root / "run_pilot.py"
    if runner.is_symlink() or not runner.is_file():
        raise RuntimeError("Fictional package verifier missing")
    if hashlib.sha256(runner.read_bytes()).hexdigest() != assets.get("run_pilot.py"):
        raise RuntimeError("Fictional package verifier modified")
    old_argv = sys.argv
    try:
        sys.argv = [str(runner), "--verify"]
        runpy.run_path(str(runner), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise RuntimeError("Fictional package integrity denied") from None
    finally:
        sys.argv = old_argv


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in ([], ["--verify"], ["--gui-acceptance"]):
        print("Fictional application denied: unsupported command", file=sys.stderr)
        return 2
    if not getattr(sys, "frozen", False):
        print("This entrypoint is for a self-contained fictional prototype only.", file=sys.stderr)
        return 2
    root = Path(sys._MEIPASS) / PILOT_DIR
    try:
        verify_tree(root, MANIFEST_SHA256)
    except (OSError, ValueError, RuntimeError) as exc:
        print("Fictional package integrity DENIED: " + str(exc), file=sys.stderr)
        return 2
    if args == ["--verify"]:
        print("Fictional self-contained package integrity: PASS")
        return 0
    sys.path.insert(0, str(root))
    if args == ["--gui-acceptance"]:
        # Test-only gate; a build cannot turn this into production authority.
        if os.environ.get("MTL_FICTIONAL_CI_ACCEPTANCE") != "1":
            print("Fictional GUI self-test not enabled", file=sys.stderr)
            return 2
        from frozen_gui_acceptance import run
        return run(root)
    sys.argv = [str(root / "start_pilot.py"), "--gui"]
    try:
        runpy.run_path(str(root / "start_pilot.py"), run_name="__main__")
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        return int(exc.code) if isinstance(exc.code, int) else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
