"""Native Tk GUI + actual backup/restore engine acceptance, fiction-only.

No mocking of real backup/restore/authorization engine; dialogs use a scoped
scripted choice to prevent any real user input. No codes printed/artifacted.
"""
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from hashlib import sha256
import tkinter as tk

from tools import windows_fictional_gui as gui
from src.offline_pilot import initialize_fictional_pilot
from src.secure_engine import SecureCore, Denied
from src.durable_local_write_fence import LocalWriteFence

@contextmanager
def core_session(path):
    core=SecureCore(path)
    try:
        yield core
    finally:
        core.close()

def run():
    with TemporaryDirectory(prefix="mtl-native-recovery-") as folder:
        folder=Path(folder)
        original=folder/"fictional-original.sqlite3"
        backup=folder/"fictional-backup.json"
        restored=folder/"fictional-restored.sqlite3"
        accounts=initialize_fictional_pilot(original)
        editor=accounts["editor_token"]
        reviewer=accounts["reviewer_token"]
        with core_session(original) as core:
            second=core.create_matter(editor,"Second invented matter")
            core.create_task(editor,second["id"],"Second invented task","2031-02-01T00:00:00Z")
            assert core.verify_audit()
            expected={}
            for table in ("matters","tasks","audit_chain","research_evidence"):
                expected[table]=[tuple(r) for r in core.db.execute("SELECT * FROM "+table+" ORDER BY rowid")]
            assert len(expected["matters"])==2
            assert len(expected["tasks"])>=2
        errors=[]
        info=[]
        new_tokens=[]
        original_Tk=gui.tk.Tk
        original_Label=gui.tk.Label
        observed=[]
        def open_dialog(*args,**kwargs):
            title=kwargs["title"]
            if title=="Choose practice case to back up":
                return str(original)
            if title=="Choose practice backup to restore":
                return str(backup)
            raise AssertionError("Unexpected file dialog: "+title)
        def save_dialog(*args,**kwargs):
            title=kwargs["title"]
            if title=="Save practice backup as":
                return str(backup)
            if title=="Save restored practice case as":
                return str(restored)
            raise AssertionError("Unexpected save dialog: "+title)
        def auth_dialog(*args,**kwargs):
            assert kwargs.get("show")=="*"
            return editor
        def info_message(*args,**kwargs):
            info.append((args,kwargs))
        def error_message(*args,**kwargs):
            errors.append((args,kwargs))
        def confirm(*args,**kwargs):
            assert "NEW file" in args[1]
            return True
        def tk_factory(*args,**kwargs):
            root=original_Tk(*args,**kwargs)
            def on_wait(window):
                # Actual child modal and real Tk Entry widgets, but no human interaction.
                for widget in window.winfo_children():
                    if isinstance(widget,tk.Entry):
                        value=widget.get()
                        assert value and len(value)>16
                        new_tokens.append(value)
                window.destroy()
            root.wait_window=on_wait
            def execute():
                try:
                    buttons={w.cget("text"):w for w in root.winfo_children() if isinstance(w,tk.Button)}
                    for name in ("Back Up Practice Case","Restore Practice Backup","Close"):
                        assert name in buttons, name
                    buttons["Back Up Practice Case"].invoke()
                    assert backup.is_file(), "Backup button did not write real archive"
                    raw=backup.read_bytes()
                    for token in (editor,reviewer):
                        assert token.encode() not in raw
                        assert sha256(token.encode()).hexdigest().encode() not in raw
                    assert not errors, "Backup raised an error"
                    observed.append("REAL_NATIVE_BACKUP")
                    buttons["Restore Practice Backup"].invoke()
                    assert restored.is_file(), "Restore button did not write new database"
                    assert len(new_tokens)==2 and len(set(new_tokens))==2
                    assert not any(t in (editor,reviewer) for t in new_tokens)
                    assert not errors, "Restore raised an error"
                    observed.append("REAL_NATIVE_RESTORE_NEW_CODES")
                    with core_session(restored) as recovered:
                        assert recovered.verify_audit()
                        for table,rows in expected.items():
                            assert [tuple(r) for r in recovered.db.execute(
                                "SELECT * FROM "+table+" ORDER BY rowid")]==rows,table
                        for token in (editor,reviewer):
                            try:
                                recovered._identity(token)
                            except Denied:
                                pass
                            else:
                                raise AssertionError("Old token authorized restored case")
                        for token in new_tokens:
                            recovered._identity(token)
                        assert not LocalWriteFence(restored).is_pending()
                    observed.append("RECORDS_AUDIT_ISOLATION_OLD_TOKEN_DENIAL")
                    old_bytes=restored.read_bytes()
                    buttons["Restore Practice Backup"].invoke()
                    assert restored.read_bytes()==old_bytes, "Existing restore destination overwritten"
                    assert errors, "Expected overwrite denial not shown"
                    observed.append("NO_DESTRUCTIVE_OVERWRITE")
                    # Corrupt backup: repair previous destination issue by selecting different
                    # path and confirm real engine refuses tampering.
                    bad=folder/"tampered-backup.json"
                    bad.write_bytes(raw.replace(b"fictional",b"forgedxx",1))
                    with patch.object(gui.filedialog,"askopenfilename",return_value=str(bad)), patch.object(
                        gui.filedialog,"asksaveasfilename",return_value=str(folder/"tampered-destination.sqlite3")):
                        prev_errors=len(errors)
                        buttons["Restore Practice Backup"].invoke()
                        assert len(errors)>prev_errors, "Tampered backup not denied"
                        assert not (folder/"tampered-destination.sqlite3").exists()
                    observed.append("TAMPERED_BACKUP_DENIED")
                    buttons["Close"].invoke()
                except Exception as ex:
                    observed.append("DENIED:"+type(ex).__name__+":"+str(ex))
                    root.destroy()
            root.after(300,execute)
            root.after(20000,lambda:root.destroy() if root.tk.call("winfo","exists",str(root)) else None)
            return root
        with ExitStack() as stack:
            stack.enter_context(patch.object(gui.tk,"Tk",side_effect=tk_factory))
            stack.enter_context(patch.object(gui.filedialog,"askopenfilename",side_effect=open_dialog))
            stack.enter_context(patch.object(gui.filedialog,"asksaveasfilename",side_effect=save_dialog))
            stack.enter_context(patch.object(gui.simpledialog,"askstring",side_effect=auth_dialog))
            stack.enter_context(patch.object(gui.messagebox,"showinfo",side_effect=info_message))
            stack.enter_context(patch.object(gui.messagebox,"showerror",side_effect=error_message))
            stack.enter_context(patch.object(gui.messagebox,"askyesno",side_effect=confirm))
            gui.main()
        if any(item.startswith("DENIED") for item in observed):
            raise AssertionError(";".join(observed))
        if observed!=["REAL_NATIVE_BACKUP","REAL_NATIVE_RESTORE_NEW_CODES",
                     "RECORDS_AUDIT_ISOLATION_OLD_TOKEN_DENIAL",
                     "NO_DESTRUCTIVE_OVERWRITE","TAMPERED_BACKUP_DENIED"]:
            raise AssertionError("Incomplete real GUI recovery: "+repr(observed))
        print("NATIVE_WINDOWS_BACKUP_RESTORE_REAL_ENGINE=VERIFIED")
        print("CROSS_MATTER_RECORDS_AND_AUDIT=VERIFIED")
        print("NEW_CODES_AND_OLD_CODE_DENIAL=VERIFIED")
        print("TAMPER_OVERWRITE_DENIAL=VERIFIED")
        print("NO_REAL_CLIENT_DATA=VERIFIED")

if __name__=="__main__":
    run()
