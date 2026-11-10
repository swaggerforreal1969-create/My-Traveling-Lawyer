"""Unit contracts for sealed fictional installer source selection and integrity."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools.build_frozen_installer import payload_inventory
from tools.frozen_installer_entry import verify_payload, SealedFictionalInstaller, main


class SealedPayloadTests(unittest.TestCase):
    def test_unfrozen_bootstrap_never_launches_a_customer_installer(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(main_for_test(), 2)

    def test_external_symlink_denied_before_hashing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            outside = root / "secret"
            outside.write_text("PRIVATE", encoding="utf-8")
            try:
                (source / "linked").symlink_to(outside)
            except (OSError, PermissionError):
                self.skipTest("No symlink access")
            with self.assertRaises(ValueError):
                payload_inventory(source)
            self.assertEqual(outside.read_text(), "PRIVATE")


def main_for_test():
    # main handles the explicit fail-closed frozen-only path.
    with patch.object(sys, "argv", ["installer", "--verify"]):
        return main()


if __name__ == "__main__":
    unittest.main()
