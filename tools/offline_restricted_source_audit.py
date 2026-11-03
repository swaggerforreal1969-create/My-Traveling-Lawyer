"""Read-only offline audit of ten *preserved* restricted v1.4 source files.

Run ONLY in a reviewer-authorized local environment against the owner-retained
archive; no copying or uploading originals. No network, source reconstruction,
manifest modification, reviewer self-approval or release-gate bypass.
The manifest MUST be authenticated by the reviewer through a separate channel.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

RESTRICTED = (
    "My-Travelling-Lawyer-OPEN-ME.html",
    "src/__init__.py",
    "src/app.js",
    "src/index.html",
    "src/secure_app.js",
    "src/secure_index.html",
    "src/secure_server.py",
    "tests/test_custody_v11.py",
    "tests/test_engine.py",
    "tests/test_milestone_v06.py",
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024


def _ordinary_file(root: Path, relative: str):
    """Reject symlinked archive paths AND symlinked ancestor directories."""
    current = root
    for segment in Path(relative).parts:
        if segment in ("", ".", ".."):
            raise ValueError("Unsafe source path")
        current = current / segment
        if current.is_symlink():
            raise ValueError("Symlinked source path")
    if not current.is_file():
        raise ValueError("Missing original file")
    st = current.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_SOURCE_BYTES:
        raise ValueError("Invalid original file type or size")
    return current


def audit_restricted_sources(archive: Path, manifest_path: Path):
    """Return status-only results; never include original bytes or text."""
    archive = Path(archive)
    manifest_path = Path(manifest_path)
    if not archive.is_dir() or archive.is_symlink():
        raise ValueError("Approved local archive directory required")
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError("Original manifest must be an ordinary file")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Manifest exceeds validation limit")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if type(manifest) is not dict or manifest.get("schema") != "mtl-source-v14-sha256-v1":
        raise ValueError("Unsupported original manifest schema")
    expected = manifest.get("files")
    if type(expected) is not dict or len(expected) != 42:
        raise ValueError("Frozen manifest must contain exactly 42 sources")
    for name, digest in expected.items():
        if (type(name) is not str or not name or Path(name).is_absolute()
                or name.startswith("./") or "\\" in name
                or any(p in ("", ".", "..") for p in name.split("/"))
                or type(digest) is not str or not SHA256.fullmatch(digest)):
            raise ValueError("Invalid original manifest paths or digests")
    if not all(name in expected for name in RESTRICTED):
        raise ValueError("Frozen manifest omits protected original")
    findings = []
    for name in RESTRICTED:
        try:
            target = _ordinary_file(archive, name)
            digest = hashlib.sha256()
            with target.open("rb") as source:
                while part := source.read(1024 * 1024):
                    digest.update(part)
            ok = digest.hexdigest() == expected[name]
            findings.append({"path": name, "status": "match" if ok else "mismatch"})
        except (ValueError, OSError):
            findings.append({"path": name, "status": "missing_or_unsafe"})
    return {
        "schema": "mtl-restricted-offline-audit-v1",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "originals_verified": sum(x["status"] == "match" for x in findings),
        "originals_required": len(RESTRICTED),
        "reviewer_security_approval": False,
        "hosted_42_file_release_gate_passed": False,
        "findings": findings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify restricted original hashes in place (offline, no publication)")
    parser.add_argument("--archive-root", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_restricted_sources(Path(args.archive_root), Path(args.manifest))
    except (ValueError, OSError, TypeError, json.JSONDecodeError) as exc:
        # Never echo archive content, path, or an exception with sensitive text.
        print(json.dumps({"schema": "mtl-restricted-offline-audit-v1",
                          "status": "invalid_input", "error_type": type(exc).__name__,
                          "reviewer_security_approval": False,
                          "hosted_42_file_release_gate_passed": False}))
        return 1
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["originals_verified"] == len(RESTRICTED) else 1


if __name__ == "__main__":
    sys.exit(main())
