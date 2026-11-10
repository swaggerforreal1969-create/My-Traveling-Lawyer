"""Automated real-Tk acceptance INSIDE the unsigned fictional frozen binary.

The file dialogs and human confirmations use synthetic test inputs. The
windows, widgets, local database, core authorization, research, review and
task writes are genuine. No secrets are printed or retained outside memory.
This never authorizes production, real client data or independent authority.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import runpy
import sys


def widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from widgets(child)


def run(package_root: Path) -> int:
    import tkinter as tk
    from tkinter import messagebox, ttk
    from src.offline_pilot import (initialize_fictional_pilot,
                                   open_fictional_pilot, inspect_fictional_pilot)
    from src.private_attorney_operator import PrivateAttorneyOperator
    from src.secure_engine import Denied

    real_tk, real_top = tk.Tk, tk.Toplevel
    errors, state = [], {"opens": 0, "setup_windows": 0}
    with TemporaryDirectory(prefix="mtl-frozen-fictional-gui-") as workspace:
        db = Path(workspace) / "native-fictional.sqlite3"

        def create_fictional(path):
            issued = initialize_fictional_pilot(path)
            state["codes"] = issued
            return issued

        def open_native(path, token):
            # Exercise actual native Tk application, without blocking its mainloop.
            with patch.object(tk, "Tk", real_tk), patch.object(tk, "Toplevel", real_top):
                app, core = open_fictional_pilot(path, token, run_mainloop=False)
                try:
                    app.update()
                    assert "Local Operator" in app.title()
                    assert PrivateAttorneyOperator(core).matters(token)["matters"]
                    assert core.verify_audit()
                    lists = [x for x in widgets(app) if isinstance(x, tk.Listbox)]
                    buttons = {x.cget("text"): x for x in widgets(app)
                               if isinstance(x, ttk.Button)}
                    textboxes = [x for x in widgets(app)
                                 if isinstance(x, tk.Text)]
                    assert len(lists) == 3 and len(textboxes) == 2
                    assert {"Select matter", "Record review", "Complete task"}.issubset(buttons)
                    lists[0].selection_set(0)
                    lists[0].event_generate("<<ListboxSelect>>")
                    app.update()
                    buttons["Select matter"].invoke()
                    app.update()
                    if state["opens"] == 0:
                        assert lists[1].size() == 1 and lists[2].size() == 1
                        app.open_private_brief()
                        app.update()
                        briefs = [x for x in app.winfo_children()
                                  if isinstance(x, tk.Toplevel)]
                        assert len(briefs) == 1
                        private = [x for x in widgets(briefs[0])
                                   if isinstance(x, tk.Text)]
                        assert len(private) == 1
                        brief_text = private[0].get("1.0", "end-1c")
                        assert "Fictional Research Matter" in brief_text
                        assert "Fictional Source Title" in brief_text
                        briefs[0].destroy()
                        app.update()
                        lists[1].selection_set(0)
                        lists[1].event_generate("<<ListboxSelect>>")
                        app.update()
                        textboxes[0].insert("1.0", "Automated fictional manual review")
                        with patch.object(messagebox, "askyesno", return_value=True):
                            buttons["Record review"].invoke()
                        app.update()
                        assert core.db.execute(
                            "SELECT count(*) FROM source_second_review"
                        ).fetchone()[0] == 1
                        lists[2].selection_set(0)
                        lists[2].event_generate("<<ListboxSelect>>")
                        app.update()
                        with patch.object(messagebox, "askyesno", return_value=True):
                            buttons["Complete task"].invoke()
                        app.update()
                        assert core.db.execute(
                            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
                        ).fetchone()[0] == 1
                    else:
                        assert lists[1].size() == 0 and lists[2].size() == 0
                        assert core.db.execute(
                            "SELECT count(*) FROM source_second_review"
                        ).fetchone()[0] == 1
                        assert core.db.execute(
                            "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
                        ).fetchone()[0] == 1
                    assert core.verify_audit()
                    state["opens"] += 1
                finally:
                    app.destroy()
                    core.close()

        def make_root():
            root = real_tk()
            state["setup_windows"] += 1
            mode = state["setup_windows"]
            def click():
                try:
                    label = ("Create NEW practice workspace" if mode == 1
                             else "Open SAVED practice workspace")
                    next(x for x in widgets(root)
                         if isinstance(x, tk.Button)
                         and x.cget("text") == label).invoke()
                except Exception as exc:
                    errors.append(type(exc).__name__)
                    if root.winfo_exists():
                        root.destroy()
            root.after(85, click)
            root.after(15000, lambda: root.winfo_exists() and root.destroy())
            return root

        def make_codes(parent):
            win = real_top(parent)
            def acknowledge():
                try:
                    fields = [x for x in widgets(win) if isinstance(x, tk.Text)]
                    assert len(fields) == 1
                    shown = fields[0].get("1.0", "end-1c")
                    assert state["codes"]["editor_token"] in shown
                    assert state["codes"]["reviewer_token"] in shown
                    next(x for x in widgets(win)
                         if isinstance(x, tk.Button)
                         and x.cget("text") == "I saved both codes - Open practice").invoke()
                except Exception as exc:
                    errors.append(type(exc).__name__)
                    if win.winfo_exists():
                        win.destroy()
                    if parent.winfo_exists():
                        parent.destroy()
            win.after(85, acknowledge)
            return win

        def credential(*args, **kwargs):
            assert kwargs.get("show") == "*"
            return state["codes"]["editor_token"]

        with (patch.object(tk, "Tk", side_effect=make_root),
              patch.object(tk, "Toplevel", side_effect=make_codes),
              patch("tkinter.filedialog.asksaveasfilename", return_value=str(db)),
              patch("tkinter.filedialog.askopenfilename", return_value=str(db)),
              patch("tkinter.simpledialog.askstring", side_effect=credential),
              patch("src.offline_pilot.initialize_fictional_pilot",
                    side_effect=create_fictional),
              patch("src.offline_pilot.open_fictional_pilot",
                    side_effect=open_native)):
            for _ in range(2):
                prior = sys.argv
                try:
                    sys.argv = [str(package_root / "start_pilot.py"), "--gui"]
                    try:
                        runpy.run_path(str(package_root / "start_pilot.py"),
                                       run_name="__main__")
                    except SystemExit as exc:
                        assert exc.code in (None, 0)
                finally:
                    sys.argv = prior
                assert not errors and db.is_file()

        assert state["setup_windows"] == 2 and state["opens"] == 2
        assert (Path(str(db) + ".write-fence.sqlite3")).is_file()
        report = inspect_fictional_pilot(db, state["codes"]["editor_token"])
        assert not report["write_unresolved"]
        assert report["summary"]
        try:
            open_fictional_pilot(db, "invalid-fictional-code", run_mainloop=False)
        except Denied:
            pass
        else:
            raise AssertionError("Unauthorized fictional login was permitted")
        try:
            initialize_fictional_pilot(db)
        except Denied:
            pass
        else:
            raise AssertionError("Existing fictional records were overwritten")
    print("FROZEN FICTIONAL GUI: two real Tk windows, private research,"
          " review, task completion, safe restart, audit and denials PASS")
    return 0
