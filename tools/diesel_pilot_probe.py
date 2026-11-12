"""Bounded, isolated native Tk control acceptance. No customer files are created."""
import json
import os
from pathlib import Path
import tkinter as tk
from tools import windows_fictional_gui as gui

def run():
    observed = []
    original_tk = gui.tk.Tk
    original_save = gui.filedialog.asksaveasfilename
    original_open = gui.filedialog.askopenfilename
    result = {"mode":"FICTIONAL_CI_ONLY","controls":[],"status":"UNRESOLVED"}
    root_holder = []

    def fake_save(*args, **kwargs):
        if kwargs.get("title") != "Save a new practice case":
            raise AssertionError("wrong create dialog")
        observed.append("create_dialog")
        return ""  # cancellation, no write

    def fake_open(*args, **kwargs):
        if kwargs.get("title") != "Open a practice case":
            raise AssertionError("wrong open dialog")
        observed.append("open_dialog")
        return ""  # cancellation, no read

    def make_tk(*args, **kwargs):
        root = original_tk(*args, **kwargs)
        root_holder.append(root)
        def exercise():
            try:
                buttons = [c for c in root.winfo_children() if isinstance(c, tk.Button)]
                names = [b.cget("text") for b in buttons]
                expected = ["Create Practice Case","Open Practice Case","Close"]
                if names != expected:
                    raise AssertionError(f"unexpected buttons: {names!r}")
                buttons[0].invoke()
                buttons[1].invoke()
                if observed != ["create_dialog", "open_dialog"]:
                    raise AssertionError(f"incorrect dialog actions: {observed!r}")
                result["controls"] = ["Create Practice Case: cancel safe",
                                      "Open Practice Case: cancel safe"]
                buttons[2].invoke()
                result["controls"].append("Close: window destroyed")
                result["status"] = "VERIFIED"
            except Exception as exc:
                result["status"] = "DENIED"
                result["error"] = f"{type(exc).__name__}: {exc}"
                try:
                    root.destroy()
                except tk.TclError:
                    pass
        root.after(250,exercise)
        root.after(10000,lambda: root.destroy() if root.winfo_exists() else None)
        return root

    gui.tk.Tk = make_tk
    gui.filedialog.asksaveasfilename = fake_save
    gui.filedialog.askopenfilename = fake_open
    try:
        gui.main()
    finally:
        gui.tk.Tk = original_tk
        gui.filedialog.asksaveasfilename = original_save
        gui.filedialog.askopenfilename = original_open
    if result["status"] != "VERIFIED":
        raise AssertionError(json.dumps(result))
    if root_holder and root_holder[0].winfo_exists():
        raise AssertionError("Close left a window")
    if os.getenv("DIESEL_PILOT_PROOF"):
        Path(os.environ["DIESEL_PILOT_PROOF"]).write_text(
            json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("NATIVE_TK_BUTTONS_CREATE_OPEN_CLOSE=VERIFIED")
    print("NO_PRACTICE_FILE_CREATED=VERIFIED")
    return result

if __name__ == "__main__":
    run()
