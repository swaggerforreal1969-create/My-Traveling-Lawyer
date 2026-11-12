"""Narrow build-candidate checks; no production source changes."""
from pathlib import Path
import unittest

class WindowsCandidate(unittest.TestCase):
    def test_frozen_gui_import_and_buttons(self):
        src = (Path(__file__).resolve().parents[1]/"tools"/"windows_fictional_gui.py").read_text(encoding="utf-8")
        self.assertIn("from src.local_operator_gui import launch_gui", src)
        self.assertIn("Create Practice Case", src)
        self.assertIn("Open Practice Case", src)
        self.assertIn("root.destroy", src)

    def test_build_only_does_not_require_signing_cert(self):
        src = (Path(__file__).resolve().parents[1]/"tools"/"build_signed_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$BuildOnly",src)
        self.assertNotIn("[Parameter(Mandatory=$true)][string]$TrustedCertificateThumbprint",src)
        self.assertIn('if ($BuildOnly)',src)
        self.assertIn("NOT SIGNED",src)

    def test_existing_practice_file_never_overwritten(self):
        from src.offline_pilot import initialize_fictional_pilot
        from src.secure_engine import Denied
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            path=Path(folder)/"existing.sqlite3"
            path.write_bytes(b"KEEP-EXISTING")
            with self.assertRaises(Denied):
                initialize_fictional_pilot(path)
            self.assertEqual(path.read_bytes(),b"KEEP-EXISTING")

if __name__ == "__main__":
    unittest.main()
