"""Repository-wide workflow hygiene without bypassing mandated security gates."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/".github"/"workflows"
class RepoWorkflowGuard(unittest.TestCase):
    def test_every_workflow_sets_least_privilege_explicit_permissions(self):
        for file in FOLDER.glob("*.yml"):
            text=file.read_text(encoding="utf-8")
            with self.subTest(file=file.name):
                self.assertIn("\npermissions:\n",text)
                if "contents: write" in text:
                    self.assertEqual(file.name,"diesel-agent-one-shot.yml")
    def test_each_workflow_has_bounded_concurrency(self):
        for file in FOLDER.glob("*.yml"):
            text=file.read_text(encoding="utf-8")
            with self.subTest(file=file.name):
                self.assertIn("\nconcurrency:\n",text)
                self.assertIn("cancel-in-progress:",text)
    def test_each_runner_has_timeout(self):
        for file in FOLDER.glob("*.yml"):
            text=file.read_text(encoding="utf-8")
            with self.subTest(file=file.name):
                self.assertEqual(text.count("runs-on:"),text.count("timeout-minutes:"))
    def test_no_background_schedule(self):
        for file in FOLDER.glob("*.yml"):
            text=file.read_text(encoding="utf-8")
            with self.subTest(file=file.name):
                self.assertNotIn("\n  schedule:\n",text)
    def test_restricted_module_is_not_claimed_present(self):
        source=(FOLDER/"pr110-security-write-races.yml").read_text(encoding="utf-8")
        self.assertEqual(source.count("BLOCKED_REQUIRED_RESTRICTED_SOURCE"),4)
        self.assertIn('::error title=BLOCKED_REQUIRED_RESTRICTED_SOURCE',source)
    def test_broad_regression_avoids_docs_only_pushes(self):
        source=(FOLDER/"experimental-regression.yml").read_text(encoding="utf-8")
        self.assertIn("paths-ignore:",source)
        self.assertIn("docs/**",source)
if __name__=="__main__":
    unittest.main()
