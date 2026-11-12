"""Windows startup-backup acceptance with only fictional paths and mock calls."""
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from tools import windows_fictional_gui as gui

class StartupBackupUI(unittest.TestCase):
    def setUp(self):
        self.root = object()

    def test_cancel_case_does_not_request_archive_or_token(self):
        with patch.object(gui.filedialog, "askopenfilename", return_value="") as opened, \
             patch.object(gui.filedialog, "asksaveasfilename") as target, \
             patch.object(gui.simpledialog, "askstring") as secret, \
             patch.object(gui, "backup_fictional_pilot") as save:
            gui.backup_case(self.root)
            opened.assert_called_once()
            target.assert_not_called()
            secret.assert_not_called()
            save.assert_not_called()

    def test_existing_target_denied_before_asking_for_secret(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "existing.json"
            path.write_text("KEEP", encoding="utf-8")
            with patch.object(gui.filedialog, "askopenfilename", return_value="fictional.sqlite3"), \
                 patch.object(gui.filedialog, "asksaveasfilename", return_value=str(path)), \
                 patch.object(gui.simpledialog, "askstring") as secret, \
                 patch.object(gui, "backup_fictional_pilot") as save, \
                 patch.object(gui.messagebox, "showerror") as error:
                gui.backup_case(self.root)
                secret.assert_not_called()
                save.assert_not_called()
                error.assert_called_once()
                self.assertEqual(path.read_text(encoding="utf-8"), "KEEP")

    def test_cancel_secret_writes_nothing(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "unused.json")
            with patch.object(gui.filedialog,"askopenfilename",return_value="fictional.sqlite3"), \
                 patch.object(gui.filedialog,"asksaveasfilename",return_value=path), \
                 patch.object(gui.simpledialog,"askstring",return_value=None), \
                 patch.object(gui,"backup_fictional_pilot") as save:
                gui.backup_case(self.root)
                save.assert_not_called()
                self.assertFalse(Path(path).exists())

    def test_owner_only_uses_real_backup_boundary_without_secret_echo(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "backup.json"
            with patch.object(gui.filedialog,"askopenfilename",return_value="fictional.sqlite3"), \
                 patch.object(gui.filedialog,"asksaveasfilename",return_value=str(target)), \
                 patch.object(gui.simpledialog,"askstring",return_value="FICTIONAL-SECRET") as secret, \
                 patch.object(gui,"backup_fictional_pilot",return_value={"sha256":"abc"}) as save, \
                 patch.object(gui.messagebox,"showinfo") as info:
                gui.backup_case(self.root)
                save.assert_called_once_with(Path("fictional.sqlite3"),"FICTIONAL-SECRET",target)
                self.assertEqual(secret.call_args.kwargs["show"], "*")
                info.assert_called_once()
                self.assertNotIn("FICTIONAL-SECRET",str(info.call_args))
                self.assertIn("not encrypted",str(info.call_args))

    def test_denied_backup_does_not_claim_success(self):
        with TemporaryDirectory() as folder:
            target = str(Path(folder) / "backup.json")
            with patch.object(gui.filedialog,"askopenfilename",return_value="fictional.sqlite3"), \
                 patch.object(gui.filedialog,"asksaveasfilename",return_value=target), \
                 patch.object(gui.simpledialog,"askstring",return_value="FICTIONAL-SECRET"), \
                 patch.object(gui,"backup_fictional_pilot",side_effect=PermissionError("denied")), \
                 patch.object(gui.messagebox,"showerror") as err, \
                 patch.object(gui.messagebox,"showinfo") as info:
                gui.backup_case(self.root)
                err.assert_called_once()
                info.assert_not_called()
                self.assertFalse(Path(target).exists())

    def test_plain_language_instructions_and_controls_present(self):
        src=Path(gui.__file__).read_text(encoding="utf-8")
        self.assertIn('tk.Button(root,text="Back Up Practice Case"', src)
        self.assertIn('from src.fictional_pilot_backup import backup_fictional_pilot',src)

if __name__ == "__main__":
    unittest.main()
