"""Human-operated, fictional-only portable desktop pilot entrypoint.

Uses the verified packaged Python entrypoint for every operation. No network,
credentials on command lines, installed privileges or automatic write replay.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUNNER = BASE / "run_pilot.py"
WARNING = "FICTIONAL OFFLINE PILOT ONLY - NEVER USE REAL CLIENT DATA"


def checked_command(*args: str) -> int:
    """Invoke the local verified runner without a shell or secret arguments."""
    return subprocess.call([sys.executable, str(RUNNER), *args], cwd=str(BASE))


def verify_package() -> bool:
    return checked_command("--verify") == 0


def desktop_main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=WARNING)
    parser.add_argument("--check", action="store_true",
                        help="Verify the extracted package and Python/Tk availability")
    args = parser.parse_args(argv)
    print(WARNING, flush=True)
    if not verify_package():
        print("DENIED: package verification failed. No database opened.", file=sys.stderr)
        return 2
    try:
        import tkinter
        print("Tk module: available")
    except (ImportError, RuntimeError):
        print("Tk is unavailable; install a Python 3.11+ distribution with Tk support.",
              file=sys.stderr)
        return 3
    if args.check:
        return 0
    print("1 - Create a NEW fictional pilot database")
    print("2 - Reopen an existing fictional pilot")
    try:
        action = input("Choose 1 or 2 (or press Enter to cancel): ").strip()
    except (EOFError, KeyboardInterrupt):
        return 0
    if action not in ("1", "2"):
        return 0
    try:
        filename = input("Enter the full local .sqlite3 file path: ").strip()
    except (EOFError, KeyboardInterrupt):
        return 0
    if not filename or not filename.lower().endswith(".sqlite3"):
        print("DENIED: specify an explicit .sqlite3 path.", file=sys.stderr)
        return 2
    path = Path(filename).expanduser()
    # The underlying initializer uses O_EXCL and rejects existing symlinks;
    # this is merely an early user-friendly safeguard.
    if action == "1" and (path.exists() or path.is_symlink()):
        print("DENIED: existing files are never overwritten.", file=sys.stderr)
        return 2
    if action == "2" and (not path.is_file() or path.is_symlink()):
        print("DENIED: select an existing regular fictional pilot database.",
              file=sys.stderr)
        return 2
    return checked_command("init" if action == "1" else "open",
                           "--database", str(path))


if __name__ == "__main__":
    raise SystemExit(desktop_main())
