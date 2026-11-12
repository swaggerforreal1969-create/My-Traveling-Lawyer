"""Restore UI must use the existing all-or-nothing fictional restore service."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from tools import windows_fictional_gui as gui

class RestoreUI(unittest.TestCase):
    def setUp(self):
        self.root=object()

    def test_cancel_archive_no_writes(self):
        with patch.object(gui.filedialog,"askopenfilename",return_value=""), \
             patch.object(gui.filedialog,"asksaveasfilename") as save, \
             patch.object(gui,"restore_fictional_pilot") as restore:
            gui.restore_case(self.root)
            save.assert_not_called()
            restore.assert_not_called()

    def test_cancel_destination_no_writes(self):
        with patch.object(gui.filedialog,"askopenfilename",return_value="fictional.json"), \
             patch.object(gui.filedialog,"asksaveasfilename",return_value=""), \
             patch.object(gui,"restore_fictional_pilot") as restore:
            gui.restore_case(self.root)
            restore.assert_not_called()

    def test_existing_destination_denied_no_overwrite(self):
        with TemporaryDirectory() as folder:
            destination=Path(folder)/"existing.sqlite3"
            destination.write_bytes(b"PRESERVE")
            with patch.object(gui.filedialog,"askopenfilename",return_value="fictional.json"), \
                 patch.object(gui.filedialog,"asksaveasfilename",return_value=str(destination)), \
                 patch.object(gui.messagebox,"askyesno") as ask, \
                 patch.object(gui,"restore_fictional_pilot") as restore, \
                 patch.object(gui.messagebox,"showerror") as err:
                gui.restore_case(self.root)
                ask.assert_not_called()
                restore.assert_not_called()
                err.assert_called_once()
                self.assertEqual(destination.read_bytes(),b"PRESERVE")

    def test_no_confirmation_no_restore(self):
        with TemporaryDirectory() as folder:
            target=str(Path(folder)/"unused.sqlite3")
            with patch.object(gui.filedialog,"askopenfilename",return_value="fictional.json"), \
                 patch.object(gui.filedialog,"asksaveasfilename",return_value=target), \
                 patch.object(gui.messagebox,"askyesno",return_value=False), \
                 patch.object(gui,"restore_fictional_pilot") as restore:
                gui.restore_case(self.root)
                restore.assert_not_called()

    def test_restore_failure_never_claims_issued_credentials(self):
        with TemporaryDirectory() as folder:
            target=str(Path(folder)/"unused.sqlite3")
            with patch.object(gui.filedialog,"askopenfilename",return_value="fictional.json"), \
                 patch.object(gui.filedialog,"asksaveasfilename",return_value=target), \
                 patch.object(gui.messagebox,"askyesno",return_value=True), \
                 patch.object(gui,"restore_fictional_pilot",side_effect=ValueError("bad archive")) as restore, \
                 patch.object(gui.messagebox,"showerror") as err, \
                 patch.object(gui.tk,"Toplevel") as window:
                gui.restore_case(self.root)
                restore.assert_called_once_with(Path("fictional.json"),Path(target))
                err.assert_called_once()
                window.assert_not_called()

    def test_restored_codes_are_new_and_once_only_in_dialog(self):
        with TemporaryDirectory() as folder:
            target=str(Path(folder)/"unused.sqlite3")
            entry_calls=[]
            class FakeEntry:
                def __init__(self,*args,**kwargs):pass
                def insert(self,where,text):entry_calls.append(text)
                def configure(self,**kwargs):self.state=kwargs
                def pack(self,**kwargs):pass
            with patch.object(gui.filedialog,"askopenfilename",return_value="fictional.json"), \
                 patch.object(gui.filedialog,"asksaveasfilename",return_value=target), \
                 patch.object(gui.messagebox,"askyesno",return_value=True), \
                 patch.object(gui,"restore_fictional_pilot",return_value={"accounts":[{"user":"Attorney","token":"NEW-PRIVATE-1"},{"user":"Reviewer","token":"NEW-PRIVATE-2"}]}) as restore, \
                 patch.object(gui.tk,"Toplevel") as toplevel, \
                 patch.object(gui.tk,"Label") as label, \
                 patch.object(gui.tk,"Entry",side_effect=FakeEntry), \
                 patch.object(gui.tk,"Button") as button:
                gui.restore_case(self.root)
                restore.assert_called_once()
                self.assertEqual(entry_calls,["NEW-PRIVATE-1","NEW-PRIVATE-2"])
                toplevel.assert_called_once()
                self.assertTrue(any("NEW codes" in str(c) for c in label.call_args_list))

    def test_restore_control_and_real_service_imported(self):
        source=Path(gui.__file__).read_text(encoding="utf-8")
        self.assertIn('tk.Button(root,text="Restore Practice Backup"',source)
        self.assertIn('backup_fictional_pilot, restore_fictional_pilot',source)

if __name__=="__main__":
    unittest.main()
