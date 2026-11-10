"""Frozen NONPRODUCTION-only bootstrap for the authorized fictional preview.

The builder replaces the pinned digest. SHA-256 here is NOT code signing.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import runpy
import sys

MANIFEST_SHA256 = "__MANIFEST_SHA256__"
PILOT_DIR = "mtl-fictional-preview"


def verify_tree(root: Path, manifest_sha: str) -> None:
    """Check the original approved preview before executing any external code."""
    root = Path(root)
    manifest = root / "MANIFEST.json"
    if root.is_symlink() or manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("Fictional package integrity denied")
    raw = manifest.read_bytes()
    if len(manifest_sha) != 64 or hashlib.sha256(raw).hexdigest() != manifest_sha:
        raise RuntimeError("Fictional package manifest mismatch")
    assets = json.loads(raw).get("asset_sha256", {})
    runner = root / "run_pilot.py"
    if runner.is_symlink() or not runner.is_file():
        raise RuntimeError("Fictional package verifier missing")
    if hashlib.sha256(runner.read_bytes()).hexdigest() != assets.get("run_pilot.py"):
        raise RuntimeError("Fictional package verifier modified")
    old_argv = sys.argv
    try:
        sys.argv = [str(runner), "--verify"]
        runpy.run_path(str(runner), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise RuntimeError("Fictional package integrity denied") from None
    finally:
        sys.argv = old_argv


def frozen_gui_acceptance(package: Path) -> int:
    """Drive real Tk windows and disposable fictional SQLite INSIDE frozen EXE.

    This explicit, nonproduction test never logs secrets, touches existing user
    files, phones home, or treats a source-only test as frozen acceptance.
    """
    import tempfile
    import tkinter as tk
    from tkinter import ttk, filedialog, simpledialog, messagebox
    import src.offline_pilot as pilot
    from src.private_attorney_operator import PrivateAttorneyOperator
    from src.secure_engine import Denied

    native_tk, native_top = tk.Tk, tk.Toplevel
    real_init, real_open = pilot.initialize_fictional_pilot, pilot.open_fictional_pilot

    def descendants(widget):
        out = []
        for child in widget.winfo_children():
            out.append(child)
            out.extend(descendants(child))
        return out

    with tempfile.TemporaryDirectory(prefix="fictional-frozen-test-") as tmp:
        path = Path(tmp) / "never-real-clients.sqlite3"
        context = {"stage": 0, "opens": 0, "ack": False, "masked": 0, "errors": []}

        def check(ok):
            if not ok:
                raise RuntimeError("Frozen fictional graphical acceptance denied")

        def initialize(selected):
            result = real_init(selected)
            context["credentials"] = result
            return result

        def open_interactively(selected, token):
            check(Path(selected) == path)
            stage = context["stage"]
            check(token == context["credentials"][
                "editor_token" if stage in (0, 2) else "reviewer_token"])
            # Run the genuine Tk operator; only prevent its blocking mainloop.
            tk.Tk, tk.Toplevel = native_tk, native_top
            try:
                window, core = real_open(selected, token, run_mainloop=False)
            finally:
                tk.Tk, tk.Toplevel = auto_root, auto_codes
            original_consent = messagebox.askyesno
            original_info = messagebox.showinfo
            original_warning = messagebox.showwarning
            original_error = messagebox.showerror
            messagebox.askyesno = lambda *a, **k: True
            messagebox.showinfo = lambda *a, **k: None
            messagebox.showwarning = lambda *a, **k: None
            messagebox.showerror = lambda *a, **k: (_ for _ in ()).throw(
                RuntimeError("Frozen graphical operation denied"))
            try:
                window.update()
                view = PrivateAttorneyOperator(core).matters(token)
                check(bool(view["matters"]))
                widgets = descendants(window)
                lists = [w for w in widgets if isinstance(w, tk.Listbox)]
                texts = [w for w in widgets if isinstance(w, tk.Text)]
                buttons = {w.cget("text"): w for w in widgets
                           if isinstance(w, ttk.Button)}
                check(len(lists) >= 3 and len(texts) >= 2)
                check("Select matter" in buttons)
                lists[0].selection_set(0)
                lists[0].event_generate("<<ListboxSelect>>")
                window.update()
                buttons["Select matter"].invoke()
                window.update()
                if stage == 0:
                    check(lists[1].size() == 1 and lists[2].size() == 1)
                elif stage == 1:
                    check(lists[1].size() == 1 and lists[2].size() == 1)
                    lists[1].selection_set(0)
                    lists[1].event_generate("<<ListboxSelect>>")
                    window.update()
                    texts[0].insert("1.0", "Fictional second person reviewed imaginary evidence")
                    buttons["Record review"].invoke()
                    window.update()
                    check(core.db.execute(
                        "SELECT count(*) FROM source_second_review").fetchone()[0] == 1)
                    check(lists[1].size() == 0)
                    lists[2].selection_set(0)
                    lists[2].event_generate("<<ListboxSelect>>")
                    window.update()
                    buttons["Complete task"].invoke()
                    window.update()
                    check(core.db.execute(
                        "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
                    ).fetchone()[0] == 1)
                    check(lists[2].size() == 0)
                else:
                    check(lists[1].size() == 0 and lists[2].size() == 0)
                    check(core.db.execute(
                        "SELECT count(*) FROM audit_chain WHERE action='task.complete'"
                    ).fetchone()[0] == 1)
                check(core.verify_audit())
                context["opens"] += 1
            finally:
                messagebox.askyesno = original_consent
                messagebox.showinfo = original_info
                messagebox.showwarning = original_warning
                messagebox.showerror = original_error
                window.destroy()
                core.close()

        def auto_root():
            root = native_tk()
            stage = context["stage"]
            def click():
                try:
                    buttons = [w for w in descendants(root)
                               if isinstance(w, tk.Button)]
                    wanted = ("Create NEW practice workspace" if stage == 0
                              else "Open SAVED practice workspace")
                    next(b for b in buttons if b.cget("text") == wanted).invoke()
                except Exception as exc:
                    context["errors"].append(type(exc).__name__)
                    root.destroy()
            def timeout():
                context["errors"].append("TIMEOUT")
                try:
                    root.destroy()
                except tk.TclError:
                    pass
            root.after(100, click)
            root.after(12000, timeout)
            return root

        def auto_codes(parent):
            window = native_top(parent)
            def confirm():
                try:
                    text = [w for w in descendants(window)
                            if isinstance(w, tk.Text)]
                    check(len(text) == 1)
                    contents = text[0].get("1.0", "end-1c")
                    check(all(context["credentials"][key] in contents for key
                              in ("editor_token", "reviewer_token")))
                    context["ack"] = True
                    next(w for w in descendants(window)
                         if isinstance(w, tk.Button) and
                         w.cget("text") == "I saved both codes - Open practice").invoke()
                except Exception as exc:
                    context["errors"].append(type(exc).__name__)
                    window.destroy()
                    parent.destroy()
            window.after(100, confirm)
            return window

        def saved_code(*args, **kwargs):
            check(kwargs.get("show") == "*")
            context["masked"] += 1
            return context["credentials"][
                "reviewer_token" if context["stage"] == 1 else "editor_token"]

        real_save, real_pick, real_ask = (filedialog.asksaveasfilename,
                                        filedialog.askopenfilename,
                                        simpledialog.askstring)
        try:
            tk.Tk, tk.Toplevel = auto_root, auto_codes
            pilot.initialize_fictional_pilot = initialize
            pilot.open_fictional_pilot = open_interactively
            filedialog.asksaveasfilename = lambda **kwargs: str(path)
            filedialog.askopenfilename = lambda **kwargs: str(path)
            simpledialog.askstring = saved_code
            # Load the verified packaged entrypoint, not an unbundled tools module.
            visual_main = runpy.run_path(
                str(package / "start_pilot.py"),
                run_name="frozen_gui_acceptance_entry")["visual_main"]
            for stage in range(3):
                context["stage"] = stage
                check(visual_main() == 0)
                check(not context["errors"])
                check(path.is_file())
            check(context["ack"] and context["opens"] == 3)
            check(context["masked"] == 2)
            file_bytes = path.read_bytes()
            check(all(context["credentials"][key].encode() not in file_bytes
                      for key in ("editor_token", "reviewer_token")))
            print("Frozen fictional GUI: create/review/complete/reopen PASS")
            return 0
        except (Exception, SystemExit):
            print("Frozen fictional GUI acceptance: DENIED", file=sys.stderr)
            return 2
        finally:
            tk.Tk, tk.Toplevel = native_tk, native_top
            pilot.initialize_fictional_pilot = real_init
            pilot.open_fictional_pilot = real_open
            filedialog.asksaveasfilename = real_save
            filedialog.askopenfilename = real_pick
            simpledialog.askstring = real_ask


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in ([], ["--verify"], ["--self-test-gui"]):
        print("Fictional application denied: unsupported command", file=sys.stderr)
        return 2
    if not getattr(sys, "frozen", False):
        print("This entrypoint is for a self-contained fictional prototype only.", file=sys.stderr)
        return 2
    root = Path(sys._MEIPASS) / PILOT_DIR
    try:
        verify_tree(root, MANIFEST_SHA256)
    except (OSError, ValueError, RuntimeError) as exc:
        print("Fictional package integrity DENIED: " + str(exc), file=sys.stderr)
        return 2
    if args == ["--verify"]:
        print("Fictional self-contained package integrity: PASS")
        return 0
    sys.path.insert(0, str(root))
    if args == ["--self-test-gui"]:
        return frozen_gui_acceptance(root)
    sys.argv = [str(root / "start_pilot.py"), "--gui"]
    try:
        runpy.run_path(str(root / "start_pilot.py"), run_name="__main__")
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        return int(exc.code) if isinstance(exc.code, int) else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
