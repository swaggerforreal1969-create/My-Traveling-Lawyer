"""Internal-only fictional installer-style Tk window, NOT a public installer.

Requires developer Python to run this testing window. The selected app itself
is a self-contained, unsigned executable. Never handles or modifies user
databases, access codes, trusted roots or production release state.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tools.qualify_fictional_install import stage_version, executable_at


class FictionalInstallerWindow:
    """Explicit choice + confirmation; old executable stays in place."""

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("My Traveling Lawyer - FICTIONAL INSTALL TEST ONLY")
        root.geometry("730x410")
        self.source = tk.StringVar(value="")
        self.destination = tk.StringVar(value="")
        self.previous = tk.StringVar(value="")
        self.confirm = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Choose a practice app folder and an unused new folder.")
        self.last_result: Path | None = None
        self._build()

    def _build(self):
        panel = ttk.Frame(self.root, padding=20)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="FICTIONAL PRACTICE ONLY - DO NOT USE CLIENT DATA",
                  font=("TkDefaultFont", 12, "bold")).grid(
                      row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        specs = (
            ("Choose the existing test app folder", self.source, 1, self._pick_source),
            ("Choose an unused NEW installation folder", self.destination, 2, self._pick_new),
            ("Optional: older app folder for safe return", self.previous, 3, self._pick_previous),
        )
        for label, var, row, action in specs:
            ttk.Label(panel, text=label).grid(row=row * 2 - 1, column=0,
                                              columnspan=3, sticky="w")
            ttk.Entry(panel, textvariable=var, width=72).grid(
                row=row * 2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            ttk.Button(panel, text="Browse", command=action).grid(
                row=row * 2, column=2, padx=(8, 0), sticky="ew")
        self.agree = ttk.Checkbutton(
            panel, text="I understand: fictional practice only. Keep all older versions.",
            variable=self.confirm, command=self._refresh)
        self.agree.grid(row=7, column=0, columnspan=3, sticky="w", pady=(5, 8))
        self.install = ttk.Button(panel, text="Install NEW test copy",
                                  command=self.install_version, state="disabled")
        self.install.grid(row=8, column=0, sticky="w")
        self.rollback = ttk.Button(panel, text="Check older version",
                                   command=self.check_previous_version)
        self.rollback.grid(row=8, column=1, sticky="w")
        ttk.Button(panel, text="Cancel", command=self.root.destroy).grid(
            row=8, column=2, sticky="e")
        ttk.Label(panel, textvariable=self.status, wraplength=660).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(15, 0))
        panel.columnconfigure(0, weight=2)
        panel.columnconfigure(1, weight=1)

    def _pick_source(self):
        choice = filedialog.askdirectory(title="Choose existing fictional app folder")
        if choice:
            self.source.set(choice)
            self._refresh()

    def _pick_new(self):
        choice = filedialog.askdirectory(title="Choose parent folder for NEW installation")
        if choice:
            self.destination.set(str(Path(choice) / "Fictional-Practice-New-Test-Copy"))
            self._refresh()

    def _pick_previous(self):
        choice = filedialog.askdirectory(title="Choose older fictional app folder")
        if choice:
            self.previous.set(choice)

    def _refresh(self):
        self.install.configure(
            state=("normal" if self.confirm.get() and self.source.get().strip()
                   and self.destination.get().strip() else "disabled"))

    def install_version(self):
        if not self.confirm.get():
            self.status.set("Installation denied: please confirm fictional-only use.")
            return
        try:
            src = Path(self.source.get()).expanduser()
            dest = Path(self.destination.get()).expanduser()
            if not src.is_dir() or src.is_symlink():
                raise ValueError("The selected app folder is missing or linked.")
            if not dest.name or dest.name in (".", "..") or dest.is_symlink():
                raise ValueError("Choose a new, unused installation folder.")
            if dest.exists():
                raise FileExistsError("This folder already exists. Nothing was replaced.")
            if dest.parent.resolve() == src.resolve():
                raise ValueError("Cannot install inside the existing app folder.")
            if not messagebox.askyesno(
                "Confirm fictional installation",
                "Copy the verified fictional app to the NEW folder?\n"
                "The older app and all practice records stay unchanged.",
                parent=self.root,
            ):
                self.status.set("Cancelled. No app files or records were changed.")
                return
            # Full copy + frozen verify; a failed copy is removed by the existing
            # qualified staging component. Database files are never installed.
            installed = stage_version(src, dest)
            self.last_result = installed
            self.status.set("Success. NEW fictional test app verified. Old app preserved.")
            messagebox.showinfo("Fictional installation complete",
                                "New test copy passed verification.\n"
                                "Your older version remains available.",
                                parent=self.root)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            self.status.set("Installation denied. Older app and practice records stay untouched.")
            messagebox.showerror("Test installation blocked",
                                 "Could not verify a safe new install.\n"
                                 "No existing folder was replaced.",
                                 parent=self.root)

    def check_previous_version(self):
        try:
            old = Path(self.previous.get()).expanduser()
            if not old.is_dir() or old.is_symlink():
                raise ValueError("Choose an older fictional app folder.")
            old_exe = executable_at(old)
            if old_exe.is_symlink() or not old_exe.is_file():
                raise ValueError("Earlier executable not found.")
            checked = subprocess.run([str(old_exe), "--verify"], cwd=str(old),
                                     capture_output=True, text=True, timeout=80)
            if checked.returncode != 0 or "integrity: PASS" not in checked.stdout:
                raise ValueError("Prior version integrity denied")
            self.status.set("Older fictional app is verified and remains available.")
        except (OSError, ValueError, subprocess.SubprocessError):
            self.status.set("Older app unavailable or failed verification. No files changed.")

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    root = tk.Tk()
    FictionalInstallerWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()
