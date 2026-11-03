import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.verify_source_manifest import verify

class ManifestGateTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        self.paths=[f'src/part{i:02d}.py' for i in range(42)]
        for p in self.paths:
            f=self.root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('fictional-only')
        self.manifest={'schema':'mtl-source-v14-sha256-v1','files':{p:hashlib.sha256(b'fictional-only').hexdigest() for p in self.paths}}
        (self.root/'SOURCE_V14_SHA256.json').write_text(json.dumps(self.manifest))
    def test_all_42_valid(self):self.assertEqual(verify(self.root),[])
    def test_tamper_fails(self):
        (self.root/self.paths[0]).write_text('changed')
        self.assertIn('mismatch',verify(self.root)[0])
    def test_missing_fails(self):
        (self.root/self.paths[0]).unlink()
        self.assertIn('missing',verify(self.root)[0])
    def test_symlink_fails(self):
        original=self.root/self.paths[0];original.unlink();original.symlink_to(self.root/self.paths[1]);self.assertIn('unsafe',verify(self.root)[0])
    def test_extra_or_duplicate_manifest_fails(self):
        self.manifest['files'].pop(self.paths[0]);(self.root/'SOURCE_V14_SHA256.json').write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError):verify(self.root)
    def test_path_traversal_fails(self):
        self.manifest['files']['../outside']=self.manifest['files'].pop(self.paths[0]);(self.root/'SOURCE_V14_SHA256.json').write_text(json.dumps(self.manifest))
        self.assertIn('unsafe',verify(self.root)[0])

if __name__=='__main__':unittest.main()