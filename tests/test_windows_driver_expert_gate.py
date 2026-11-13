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
        self.assertIn("def choose_file(title, path):", source)
        self.assertIn("candidate.window_text() == title", source)
        function = next(n for n in ast.parse(source).body
                        if isinstance(n, ast.FunctionDef) and n.name == "choose_file")
        function_source = ast.get_source_segment(source, function)
        self.assertNotIn("dlg = window(title)", function_source)

    def test_owner_input_uses_observed_native_tk_dialog_not_edit_tree(self):
        source = (ROOT / "tools/windows_frozen_recovery_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("def submit_owner_code(code, timeout=15):", source)
        self.assertIn('dlg.class_name() != "TkTopLevel"', source)
        self.assertIn("len(buttons) == 2", source)
        self.assertIn("send_keys(code, with_spaces=True", source)
        self.assertIn("submit_owner_code(owner)", source)
        self.assertNotIn('raise AssertionError("OWNER_AUTH_DIALOG_MISSING")', source)

    def test_owner_probe_does_not_read_or_print_credentials(self):
        source = (ROOT / "tools/windows_frozen_recovery_acceptance.py").read_text(encoding="utf-8")
        section = source.split('if os.getenv("MTL_DIAG_OWNER_ONLY") == "1":')[1].split("            prompt = window(TITLE)")[0]
        self.assertIn("FROZEN_OWNER_DIAG_ONLY=VERIFIED", section)
        self.assertNotIn("window_text(", section)
        self.assertNotIn("get_value(", section)
        self.assertNotIn("get_edit_text(", section)
        self.assertNotIn("owner", section.split("top = []",1)[1].split("FROZEN_OWNER_DIAG_ONLY")[0].replace("FROZEN_OWNER_", ""))

    def test_distinct_open_and_save_filename_controls(self):
        source = (ROOT / "tools/windows_frozen_recovery_acceptance.py").read_text(encoding="utf-8")
        self.assertIn('filename_id = 1001 if title.startswith("Save ") else 1148', source)
        self.assertIn("edits[0].set_edit_text(str(path))", source)
        self.assertIn('c.control_id() == 1', source)


    def test_full_driver_uses_verified_native_backup_and_filename_controls(self):
        source = (ROOT / "tools/windows_frozen_recovery_acceptance.py").read_text(encoding="utf-8")
        self.assertIn("sorted(native, key=lambda b: b.rectangle().top)", source)
        self.assertIn('filename_id = 1001 if title.startswith("Save ") else 1148', source)
        self.assertIn('c.class_name() == "Edit" and c.control_id() == filename_id', source)
        self.assertIn('c.class_name() == "Button" and c.control_id() == 1', source)
        self.assertIn("candidate.window_text() == title", source)

    def test_backup_selection_must_use_geometry_not_native_index(self):
        source = (ROOT / "tools/windows_dialog_probe.py").read_text(encoding="utf-8")
        self.assertIn("ordered = sorted(controls", source)
        self.assertIn("ordered[3]", source)
        self.assertIn('result["startup_buttons"]', source)
        self.assertNotIn("controls[3].click_input()", source)

    def test_dialog_diagnostic_never_exports_editable_values(self):
        source = (ROOT / "tools/windows_dialog_probe.py").read_text(encoding="utf-8")
        self.assertIn('result["native_controls"]', source)
        self.assertIn('result["uia_controls"]', source)
        self.assertIn('safe_label = label if label in', source)
        self.assertNotIn("get_value(", source)
        self.assertNotIn("get_edit_text(", source)

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
