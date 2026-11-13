"""Static, low-cost specialist check to stop known black-box driver regressions."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FrozenDriverExpertGate(unittest.TestCase):
    def test_no_invalid_securecore_context_manager(self):
        source = (ROOT / "tools/windows_frozen_recovery_acceptance.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        # Last verified failure: SecureCore has no context manager protocol.
        for node in ast.walk(tree):
            if isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    call = item.context_expr
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                        self.assertNotEqual(call.func.id, "SecureCore")

    def test_no_window_specification_method_called_on_wrapper(self):
        source = (ROOT / "tools/windows_frozen_recovery_acceptance.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        # Prior failure: Desktop.windows returns UIAWrapper, not WindowSpecification.
        self.assertFalse(any(isinstance(n, ast.Call) and
                             isinstance(n.func, ast.Attribute) and
                             n.func.attr == "child_window"
                             for n in ast.walk(tree)))

    def test_frozen_picker_is_class_based_not_label_assumption(self):
        source = (ROOT / "tools/windows_frozen_recovery_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('candidate.class_name() == "#32770"', source)
        self.assertIn('Desktop(backend="win32").windows()', source)
        self.assertIn('handle=candidate.handle', source)
        self.assertIn("def file_picker(", source)
        self.assertIn("dlg = file_picker()", source)
        function = next(n for n in ast.parse(source).body
                        if isinstance(n, ast.FunctionDef) and n.name == "choose_file")
        function_source = ast.get_source_segment(source, function)
        self.assertNotIn("dlg = window(title)", function_source)

    def test_dialog_probe_has_finite_single_process_and_scrubbed_report(self):
        source = (ROOT / "tools/windows_dialog_probe.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertIn("UNRESOLVED_NO_NEW_TOP_LEVEL_WINDOW", source)
        self.assertIn("proc.terminate()", source)
        self.assertNotIn("screenshot(", source)
        self.assertNotIn("token", source.lower())
        self.assertIsInstance(tree, ast.Module)


if __name__ == "__main__":
    unittest.main()
