"""Real Tk controls for fictional installer, with no customer data."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from tools.fictional_installer_window import FictionalInstallerWindow


class InstallerWindowTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.panel = FictionalInstallerWindow(self.root)
        self.root.update()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_cancel_does_not_call_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "source"
            src.mkdir()
            dest = Path(tmp) / "unused"
            self.panel.source.set(str(src))
            self.panel.destination.set(str(dest))
            self.panel.confirm.set(True)
            self.panel._refresh()
            self.assertNotIn("disabled", self.panel.install.state())
            with patch("tools.fictional_installer_window.stage_version") as staged, \
                 patch("tools.fictional_installer_window.messagebox.askyesno", return_value=False):
                self.panel.install.invoke()
                staged.assert_not_called()
            self.assertFalse(dest.exists())
            self.assertIn("Cancelled", self.panel.status.get())

    def test_confirmation_required_and_existing_directory_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "source"
            src.mkdir()
            dest = Path(tmp) / "already-exists"
            dest.mkdir()
            sentinel = dest / "private.sqlite3"
            sentinel.write_bytes(b"DO NOT OVERWRITE")
            self.panel.source.set(str(src))
            self.panel.destination.set(str(dest))
            self.panel._refresh()
            self.assertIn("disabled", self.panel.install.state())
            self.panel.confirm.set(True)
            self.panel._refresh()
            with patch("tools.fictional_installer_window.stage_version") as staged, \
                 patch("tools.fictional_installer_window.messagebox.showerror"):
                self.panel.install.invoke()
                staged.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"DO NOT OVERWRITE")
            self.assertIn("denied", self.panel.status.get().lower())

    def test_real_button_installs_only_with_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "source"
            src.mkdir()
            dest = Path(tmp) / "new-version"
            self.panel.source.set(str(src))
            self.panel.destination.set(str(dest))
            self.panel.confirm.set(True)
            self.panel._refresh()
            def mock_stage(source, target):
                self.assertEqual(Path(source), src)
                self.assertEqual(Path(target), dest)
                dest.mkdir()
                return dest
            with patch("tools.fictional_installer_window.stage_version",
                       side_effect=mock_stage) as staged, \
                 patch("tools.fictional_installer_window.messagebox.askyesno", return_value=True), \
                 patch("tools.fictional_installer_window.messagebox.showinfo"):
                self.panel.install.invoke()
            staged.assert_called_once()
            self.assertEqual(self.panel.last_result, dest)
            self.assertTrue(dest.exists())
            self.assertIn("Success", self.panel.status.get())

    def test_cancel_button_destroys_window(self):
        buttons = [w for w in self.panel.root.winfo_children()[0].winfo_children()
                   if isinstance(w, __import__("tkinter.ttk", fromlist=["Button"]).Button)]
        next(w for w in buttons if w.cget("text") == "Cancel").invoke()
        with self.assertRaises(tk.TclError):
            self.root.winfo_exists()


if __name__ == "__main__":
    unittest.main()
