"""Fail-closed, credential-free Windows pilot acceptance receipt.

Run *after* the existing package, lifecycle, backup/restore and native Tk
GitHub Actions steps have succeeded. This does not test the app again, grant
production approval, or turn other platforms' failures into a Windows failure.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
from zipfile import ZipFile


def receipt(archive: Path, env: dict[str, str]) -> dict:
    if env.get("GITHUB_ACTIONS") != "true" or env.get("RUNNER_OS") != "Windows":
        raise ValueError("Acceptance evidence requires actual GitHub Windows runner")
    expected_sha = env.get("GITHUB_SHA", "")
    if len(expected_sha) != 40 or any(c not in "0123456789abcdef" for c in expected_sha):
        raise ValueError("Missing exact commit SHA")
    actual_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, encoding="utf-8"
    ).strip()
    if actual_sha != expected_sha:
        raise ValueError("Checked-out source differs from workflow SHA")
    run_id = env.get("GITHUB_RUN_ID", "")
    if not run_id.isdecimal() or int(run_id) <= 0:
        raise ValueError("Missing GitHub run ID")
    if not archive.is_file() or archive.is_symlink():
        raise ValueError("Missing or linked fictional ZIP")
    with ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError("Invalid ZIP entry checksum")
        names = z.namelist()
        root = "mtl-fictional-preview/"
        if len(names) != len(set(names)) or any(not n.startswith(root) for n in names):
            raise ValueError("Unsafe ZIP layout")
        manifest = json.loads(z.read(root + "MANIFEST.json"))
        if (manifest.get("purpose") != "FICTIONAL OFFLINE PREVIEW"
                or manifest.get("production_use") is not False
                or manifest.get("independent_security_approval") is not False):
            raise ValueError("Preview must be explicitly nonproduction")
        checksums = manifest.get("sha256", {})
        if not isinstance(checksums, dict) or not checksums:
            raise ValueError("No authenticated source modules")
        if len(checksums) != manifest.get("source_count"):
            raise ValueError("Source inventory mismatch")
        for name, digest in checksums.items():
            if (not name.startswith("src/") or ".." in Path(name).parts
                    or not name.endswith(".py")
                    or sha256(z.read(root + name)).hexdigest() != digest):
                raise ValueError("Unauthenticated or unsafe module")
        actual_source = {n[len(root):] for n in names if n.startswith(root + "src/")}
        if actual_source != set(checksums):
            raise ValueError("Unexpected source payload")
        for needed in ("launch-windows.cmd", "start_pilot.py", "run_pilot.py"):
            if root + needed not in names:
                raise ValueError("Missing Windows pilot entrypoint")
    return {
        "schema": "mtl-windows-fictional-acceptance-v1",
        "result": "VERIFIED",
        "release_status": "NO-GO",
        "platform": "Windows",
        "commit_sha": expected_sha,
        "github_run_id": run_id,
        "github_run_attempt": env.get("GITHUB_RUN_ATTEMPT", "1"),
        "workflow": env.get("GITHUB_WORKFLOW", ""),
        "archive_sha256": sha256(archive.read_bytes()).hexdigest(),
        "source_modules_authenticated": len(checksums),
        "passed_prior_steps": [
            "portable_extraction_and_database_init",
            "offline_pilot_first_login_authorization_and_restart",
            "fictional_backup_and_restore",
            "native_windows_tk_widget_acceptance",
            "reproducible_preview_build",
        ],
        "limitations": [
            "not_an_unaided_human_evaluation",
            "no_independent_security_approval",
            "mandatory_original_source_release_gate_unresolved",
            "no_production_or_real_client_data",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refusing to overwrite an existing receipt")
    data = receipt(args.archive, dict(os.environ))
    args.output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as f:
            f.write(
                "### Windows fictional pilot: VERIFIED (not production)\n"
                f"- Exact SHA: \`{data['commit_sha']}\`\n"
                f"- GitHub run: \`{data['github_run_id']}\`\n"
                f"- Verified modules: {data['source_modules_authenticated']}\n"
                f"- Fictional ZIP SHA-256: \`{data['archive_sha256']}\`\n"
                "- Prior Windows tests: package, pilot/login/restart, backup/restore, native Tk — PASS\n"
                "- Release: **NO-GO**; independent review and source gates remain separate\n"
            )
    print("WINDOWS FICTIONAL PILOT ACCEPTANCE VERIFIED; PRODUCTION NO-GO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
