"""Static MSIX packaging safeguards; do not require Windows or credentials."""
import struct
import unittest
import xml.etree.ElementTree as ET
from tools.make_store_msix import manifest, png, require_identity

class StorePackagePreparation(unittest.TestCase):
    def test_identity_must_be_from_partner_center_not_placeholder(self):
        for name, publisher, version in (
            ("", "CN=Test", "1.0.0.0"),
            ("A", "CN=Test", "1.0.0.0"),
            ("My App", "CN=Test", "1.0.0.0"),
            ("Example.App", "NotACertificate", "1.0.0.0"),
            ("Example.App", "CN=Test", "1.0"),
        ):
            with self.subTest(name=name, publisher=publisher, version=version):
                with self.assertRaises(ValueError):
                    require_identity(name, publisher, version)

    def test_manifest_entirely_local_full_trust_and_nonproduction(self):
        m = manifest("Example.Practice", "CN=FictionalPublisher",
                     "Example Publisher", "0.1.0.0")
        root = ET.fromstring(m)
        namespace = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10}"
        identity = root.find(namespace+"Identity")
        self.assertEqual(identity.attrib["ProcessorArchitecture"], "x64")
        self.assertEqual(identity.attrib["Publisher"], "CN=FictionalPublisher")
        self.assertIn(b"packagedClassicApp", m)
        self.assertIn(b"runFullTrust", m)
        self.assertIn(b"MyTravelingLawyer-Practice.exe", m)
        self.assertIn(b"Fictional", m)
        self.assertNotIn(b"restricted", m.lower())  # forbidden source files not packaged here

    def test_icons_png_dimensions(self):
        for n in (44, 50, 150):
            data = png(n)
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (n, n))

if __name__ == "__main__":
    unittest.main()
