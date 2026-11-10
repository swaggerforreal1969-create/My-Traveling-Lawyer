"""Prebuild and security regression for a fictional self-contained desktop app."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from zipfile import ZipFile

from tools.build_offline_pilot_preview import build as build_preview, ROOT_NAME
from tools.build_self_contained_pilot import extract_approved, prepare_staging
from tools.frozen_pilot_bootstrap import verify_tree


class FrozenPilotPrebuildAcceptance(unittest.TestCase):
    def test_stages_only_published_source_with_pinned_manifest(self):
        with TemporaryDirectory() as tmp:
            root, boot = prepare_staging(Path(tmp) / "stage")
            digest = sha256((root / "MANIFEST.json").read_bytes()).hexdigest()
            self.assertIn(digest, boot.read_text(encoding="utf-8"))
            self.assertEqual(len(list((root / "src").glob("*.py"))), 23)
            self.assertFalse((root / "src" / "__init__.py").exists())
            verify_tree(root, digest)
            with patch("sys.frozen", False, create=True):
                from tools.frozen_pilot_bootstrap import main
                self.assertEqual(main(["--verify"]), 2)

    def test_tampered_manifest_runner_launchers_and_modules_are_denied(self):
        with TemporaryDirectory() as tmp:
            root, _ = prepare_staging(Path(tmp) / "stage")
            digest = sha256((root / "MANIFEST.json").read_bytes()).hexdigest()
            for name in ("MANIFEST.json", "run_pilot.py", "start_pilot.py",
                         "Open-Practice-Windows.cmd", "src/offline_pilot.py"):
                with self.subTest(name=name):
                    file = root / name
                    original = file.read_bytes()
                    try:
                        file.write_bytes(original + b"\n# synthetic mutation\n")
                        with self.assertRaises(RuntimeError):
                            verify_tree(root, digest)
                    finally:
                        file.write_bytes(original)
            verify_tree(root, digest)

    def test_frozen_gui_acceptance_requires_explicit_nonproduction_flag(self):
        from tools.frozen_pilot_bootstrap import main
        with (patch("sys.frozen", True, create=True),
              patch("sys._MEIPASS", "/not-an-approved-package", create=True)):
            self.assertEqual(main(["--gui-acceptance"]), 2)

    def test_builder_must_run_frozen_gui_and_tamper_denials(self):
        from tools.build_self_contained_pilot import build
        import inspect
        source = inspect.getsource(build)
        self.assertIn("--gui-acceptance", source)
        self.assertIn("FROZEN", __import__(
            "tools.frozen_gui_acceptance", fromlist=["run"]).__doc__.upper())
        self.assertIn("Frozen tampered package accepted", source)

    def test_archive_rejects_restricted_and_extra_source(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = folder / "approved.zip"
            build_preview(original)
            with ZipFile(original) as z:
                entries = {name: z.read(name) for name in z.namelist()}
            for extra in ("src/secure_server.py", "src/unreviewed.py"):
                with self.subTest(name=extra):
                    changed = folder / (extra.replace("/", "-") + ".zip")
                    with ZipFile(changed, "w") as z:
                        for name, data in entries.items():
                            z.writestr(name, data)
                        z.writestr(ROOT_NAME + "/" + extra, b"# synthetic")
                    with self.assertRaises(ValueError):
                        extract_approved(changed, folder / "unpack")


if __name__ == "__main__":
    unittest.main()
