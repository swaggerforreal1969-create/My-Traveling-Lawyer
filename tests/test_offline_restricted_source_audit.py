"""Fictional offline audit fixtures only; no protected original is copied."""
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.offline_restricted_source_audit import (
    RESTRICTED, audit_restricted_sources, main)


class RestrictedSourceOfflineAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.archive=root/"private-fictional-archive"
        self.archive.mkdir()
        self.manifest=root/"fictional-manifest.json"
        entries={}
        for i,name in enumerate(RESTRICTED):
            data=("fictional-original-%d" % i).encode()
            path=self.archive/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            entries[name]=hashlib.sha256(data).hexdigest()
        for i in range(32):
            entries["fictional-extra-file-%02d" % i]=hashlib.sha256(str(i).encode()).hexdigest()
        self.entries=entries
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps({
            "schema":"mtl-source-v14-sha256-v1",
            "files":self.entries}),encoding="utf-8")

    def test_matching_ten_originals_reports_digests_only(self):
        result=audit_restricted_sources(self.archive,self.manifest)
        self.assertEqual(result["originals_verified"],10)
        self.assertEqual(result["originals_required"],10)
        self.assertFalse(result["reviewer_security_approval"])
        self.assertFalse(result["hosted_42_file_release_gate_passed"])
        self.assertTrue(all(f["status"]=="match" for f in result["findings"]))
        self.assertNotIn("fictional-original",json.dumps(result))

    def test_changed_original_fails_without_showing_bytes(self):
        (self.archive/RESTRICTED[3]).write_bytes(b"confidential-altered-bytes")
        result=audit_restricted_sources(self.archive,self.manifest)
        self.assertEqual(result["originals_verified"],9)
        self.assertEqual(result["findings"][3]["status"],"mismatch")
        self.assertNotIn("confidential-altered-bytes",json.dumps(result))

    def test_missing_original_is_incomplete_not_accepted(self):
        (self.archive/RESTRICTED[-1]).unlink()
        result=audit_restricted_sources(self.archive,self.manifest)
        self.assertEqual(result["originals_verified"],9)
        self.assertEqual(result["findings"][-1]["status"],"missing_or_unsafe")

    def test_protected_symlink_is_denied(self):
        path=self.archive/RESTRICTED[1]
        path.unlink()
        path.symlink_to(self.manifest)
        result=audit_restricted_sources(self.archive,self.manifest)
        self.assertEqual(result["findings"][1]["status"],"missing_or_unsafe")

    def test_symlinked_parent_directory_is_denied(self):
        outside=Path(self.tmp.name)/"outside"
        outside.mkdir()
        for name in RESTRICTED:
            if name.startswith("src/"):
                origin=self.archive/name
                dest=outside/Path(name).name
                dest.write_bytes(origin.read_bytes())
        (self.archive/"src"/"__init__.py").unlink()
        # Point only a single source to outside while maintaining the rest.
        (self.archive/"src"/"__init__.py").symlink_to(outside/"__init__.py")
        self.assertEqual(audit_restricted_sources(
            self.archive,self.manifest)["findings"][1]["status"],"missing_or_unsafe")

    def test_manifest_missing_protected_original_rejected(self):
        self.entries.pop(RESTRICTED[0])
        self.entries["fictional-forty-second"]=hashlib.sha256(b"x").hexdigest()
        self.write_manifest()
        with self.assertRaises(ValueError):
            audit_restricted_sources(self.archive,self.manifest)

    def test_manifest_traversal_and_invalid_hash_rejected(self):
        self.entries["fictional-extra-file-00"]="../../etc/passwd"
        self.write_manifest()
        with self.assertRaises(ValueError):
            audit_restricted_sources(self.archive,self.manifest)
        self.entries["fictional-extra-file-00"]=hashlib.sha256(b"0").hexdigest()
        self.entries["../unsafe"]=self.entries.pop("fictional-extra-file-01")
        self.write_manifest()
        with self.assertRaises(ValueError):
            audit_restricted_sources(self.archive,self.manifest)

    def test_no_private_archive_returns_nonzero(self):
        self.assertEqual(main(["--archive-root",str(self.archive/"absent"),
                               "--manifest",str(self.manifest)]),1)

    def test_cli_incomplete_archive_returns_nonzero(self):
        (self.archive/RESTRICTED[0]).unlink()
        self.assertEqual(main(["--archive-root",str(self.archive),
                               "--manifest",str(self.manifest)]),1)

    def test_cli_complete_does_not_self_approve_release(self):
        self.assertEqual(main(["--archive-root",str(self.archive),
                               "--manifest",str(self.manifest)]),0)


if __name__=="__main__":
    unittest.main()
