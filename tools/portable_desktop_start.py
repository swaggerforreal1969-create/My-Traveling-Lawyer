"""Human-operated, fictional-only portable desktop pilot entrypoint.

Uses the verified packaged Python entrypoint for every operation. No network,
credentials on command lines, installed privileges or automatic write replay.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUNNER = BASE / "run_pilot.py"
WARNING = "FICTIONAL OFFLINE PILOT ONLY - NEVER USE REAL CLIENT DATA"


def checked_command(*args: str) -> int:
    """Invoke the local verified runner without a shell or secret arguments."""
    if getattr(sys, "frozen", False):
        # In a PyInstaller onedir app sys.executable is the fictional app,
        # not Python. Only a verification subprocess is allowed here.
        if args != ("--verify",):
            return 2
        return subprocess.call([sys.executable, "--verify"], cwd=str(BASE))
    return subprocess.call([sys.executable, str(RUNNER), *args], cwd=str(BASE))


def verify_package() -> bool:
    return checked_command("--verify") == 0



def visual_main() -> int:
    """Graphical first run for fictional, locally extracted pilots only.

    Reuse the same verified source and offline authorization core as the
    command-line path. Access codes are never placed in process arguments,
    saved configuration, logs, or automatically remembered after closing.
    """
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
    from src.offline_pilot import initialize_fictional_pilot, open_fictional_pilot
    from src.secure_engine import Denied, Invalid

    try:
        root = tk.Tk()
    except tk.TclError:
        print("Tk display unavailable. No pilot data was changed.", file=sys.stderr)
        return 3
    root.title("My Traveling Lawyer - Fictional Practice Only")
    root.geometry("550x270")
    root.minsize(480, 230)
    root.configure(padx=25, pady=20)

    tk.Label(root, text="My Traveling Lawyer - Practice Only",
             font=("TkDefaultFont", 15, "bold")).pack(pady=(0, 12))
    tk.Label(root, text="Use made-up information only. Not approved for clients.",
             wraplength=475).pack(pady=(0, 14))
    outcome = {"code": 0}

    def launch(path: Path, token: str):
        root.destroy()
        try:
            open_fictional_pilot(path, token)
        except (Denied, Invalid, OSError, ValueError):
            messagebox.showerror("Cannot open practice workspace",
                                 "Access denied or saved practice records unavailable. "
                                 "No action was repeated.")
            outcome["code"] = 2

    def create():
        selected = filedialog.asksaveasfilename(
            parent=root, title="Create a NEW fictional practice workspace",
            defaultextension=".sqlite3",
            filetypes=[("Practice database", "*.sqlite3")])
        if not selected:
            return
        path = Path(selected).expanduser()
        if path.suffix.lower() != ".sqlite3" or path.exists() or path.is_symlink():
            messagebox.showerror("Cannot create workspace",
                                 "Choose a NEW .sqlite3 file name. Existing files are never overwritten.",
                                 parent=root)
            return
        try:
            result = initialize_fictional_pilot(path)
        except (Denied, Invalid, OSError, ValueError):
            messagebox.showerror("Cannot create workspace",
                                 "Practice setup was denied. Check the chosen folder and use a new file name.",
                                 parent=root)
            return

        # This is the only time the newly generated access codes are displayed.
        # No clipboard write, disk file, remote service or stdout is involved.
        codes = tk.Toplevel(root)
        codes.title("Save your fictional practice access codes")
        codes.geometry("670x280")
        tk.Label(codes, text="Save these codes in a secure place before continuing.",
                 wraplength=610).pack(pady=10)
        text = tk.Text(codes, height=6, width=75, wrap="word")
        text.insert("1.0", "Fictional attorney code:\n" + result["editor_token"] +
                    "\n\nFictional reviewer code:\n" + result["reviewer_token"])
        text.configure(state="disabled")
        text.pack(padx=12, pady=8, fill="both", expand=True)
        saved = {"ok": False}
        def confirm_saved():
            saved["ok"] = True
            codes.destroy()
        tk.Button(codes, text="I saved both codes - Open practice",
                  command=confirm_saved).pack(pady=(0, 12))
        # Closing the only copy of a newly issued code without saving it
        # would strand the freshly created fictional workspace.
        codes.protocol("WM_DELETE_WINDOW",
                       lambda: messagebox.showwarning(
                           "Save both codes first",
                           "Save both practice access codes, then choose the button below.",
                           parent=codes))
        codes.transient(root)
        codes.grab_set()
        root.wait_window(codes)
        if saved["ok"]:
            launch(path, result["editor_token"])

    def open_saved():
        selected = filedialog.askopenfilename(
            parent=root, title="Open saved fictional practice workspace",
            filetypes=[("Practice database", "*.sqlite3")])
        if not selected:
            return
        path = Path(selected).expanduser()
        if path.suffix.lower() != ".sqlite3" or not path.is_file() or path.is_symlink():
            messagebox.showerror("Cannot open workspace",
                                 "Select an existing regular .sqlite3 practice file.", parent=root)
            return
        token = simpledialog.askstring(
            "Private practice access", "Enter your saved fictional access code:",
            show="*", parent=root)
        if not token:
            return
        launch(path, token)

    tk.Button(root, text="Create NEW practice workspace", width=34,
              command=create).pack(pady=6)
    tk.Button(root, text="Open SAVED practice workspace", width=34,
              command=open_saved).pack(pady=6)
    tk.Button(root, text="Cancel", width=34,
              command=root.destroy).pack(pady=6)
    root.mainloop()
    return outcome["code"]


def desktop_main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=WARNING)
    parser.add_argument("--gui", action="store_true",
                        help="Open graphical first-run and saved-workspace chooser")
    parser.add_argument("--check", action="store_true",
                        help="Verify the extracted package and Python/Tk availability")
    args = parser.parse_args(argv)
    print(WARNING, flush=True)
    if not verify_package():
        print("DENIED: package verification failed. No database opened.", file=sys.stderr)
        return 2
    try:
        import tkinter
        print("Tk module: available")
    except (ImportError, RuntimeError):
        print("Tk is unavailable; install a Python 3.11+ distribution with Tk support.",
              file=sys.stderr)
        return 3
    if args.check:
        return 0
    if args.gui:
        return visual_main()
    print("1 - Create a NEW fictional pilot database")
    print("2 - Reopen an existing fictional pilot")
    try:
        action = input("Choose 1 or 2 (or press Enter to cancel): ").strip()
    except (EOFError, KeyboardInterrupt):
        return 0
    if action not in ("1", "2"):
        return 0
    try:
        filename = input("Enter the full local .sqlite3 file path: ").strip()
    except (EOFError, KeyboardInterrupt):
        return 0
    if not filename or not filename.lower().endswith(".sqlite3"):
        print("DENIED: specify an explicit .sqlite3 path.", file=sys.stderr)
        return 2
    path = Path(filename).expanduser()
    # The underlying initializer uses O_EXCL and rejects existing symlinks;
    # this is merely an early user-friendly safeguard.
    if action == "1" and (path.exists() or path.is_symlink()):
        print("DENIED: existing files are never overwritten.", file=sys.stderr)
        return 2
    if action == "2" and (not path.is_file() or path.is_symlink()):
        print("DENIED: select an existing regular fictional pilot database.",
              file=sys.stderr)
        return 2
    return checked_command("init" if action == "1" else "open",
                           "--database", str(path))


if __name__ == "__main__":
    raise SystemExit(desktop_main())
