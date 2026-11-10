"""Internal-only frozen fictional installer; no public signing or distribution.

The installer contains a sealed inventory of its BUILT-IN fictional practice app,
not a user-selected executable. Hash consistency is NOT publisher authenticity.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk
from unittest.mock import patch
from tools.fictional_installer_window import FictionalInstallerWindow
from tools.qualify_fictional_install import executable_at

INVENTORY = {}  # sealed inventory injected only in private build
BUNDLE_DIR = "approved-fictional-app"


def payload_root() -> Path:
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Installer is for sealed internal executable only")
    return Path(sys._MEIPASS) / BUNDLE_DIR


def verify_payload(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("Fictional installer payload denied")
    seen = {}
    for item in path.rglob("*"):
        name = item.relative_to(path).as_posix()
        if item.is_symlink():
            target = item.resolve(strict=True)
            if not target.is_relative_to(path.resolve()):
                raise RuntimeError("External payload symlink denied")
            seen[name] = "link:" + os.readlink(item)
        elif item.is_file():
            if name.endswith(".sqlite3") or name.endswith(".sqlite3-wal"):
                raise RuntimeError("Client database is forbidden in installer")
            seen[name] = hashlib.sha256(item.read_bytes()).hexdigest()
    if seen != INVENTORY:
        raise RuntimeError("Fictional installer integrity denied")
    if not executable_at(path).is_file():
        raise RuntimeError("Fictional practice executable missing")


class SealedFictionalInstaller(FictionalInstallerWindow):
    def __init__(self, root, payload):
        self.sealed_source = Path(payload).resolve()
        super().__init__(root)
        self.source.set(str(self.sealed_source))
        self.status.set("Choose an unused NEW folder. The approved fictional app is included.")
        self._refresh()
        # The approved source is fixed; no arbitrary executable chooser.
        panel = root.winfo_children()[0]
        for item in panel.winfo_children():
            gi = item.grid_info()
            if int(gi.get("row", -1)) == 2:
                if isinstance(item, (tk.Entry, ttk.Entry)):
                    item.configure(state="disabled")
                elif hasattr(item, "configure"):
                    try:
                        item.configure(state="disabled")
                    except tk.TclError:
                        pass

    def _pick_source(self):
        # Never allow selecting a source from an arbitrary user folder.
        self.status.set("The approved fictional app is already included.")

    def _refresh(self):
        valid = self.source.get() == str(self.sealed_source)
        self.install.configure(
            state=("normal" if valid and self.confirm.get()
                   and self.destination.get().strip() else "disabled"))

    def install_version(self):
        if self.source.get() != str(self.sealed_source):
            self.status.set("Installation denied. The approved app source cannot change.")
            return
        try:
            verify_payload(self.sealed_source)
        except (OSError, RuntimeError):
            self.status.set("Installation denied. The bundled app was changed.")
            return
        super().install_version()

    def check_previous_version(self):
        # Untrusted older executables must never be executed by this installer.
        # Versions with independently pinned provenance can be supported later.
        self.status.set("Previous app is kept. Independent older-version trust is not yet approved.")


def internal_gui_test(payload: Path) -> int:
    with tempfile.TemporaryDirectory(prefix="frozen-installer-acceptance-") as tmp:
        root = tk.Tk()
        root.withdraw()
        panel = SealedFictionalInstaller(root, payload)
        destination = Path(tmp) / "new-frozen-fictional-app"
        panel.destination.set(str(destination))
        panel.confirm.set(True)
        panel._refresh()
        try:
            with patch("tools.fictional_installer_window.messagebox.askyesno",
                       return_value=False):
                panel.install.invoke()
            if destination.exists() or "Cancelled" not in panel.status.get():
                raise RuntimeError("Cancel changed fictional installation")
            # A wrong source must never be accepted.
            panel.source.set(str(Path(tmp) / "untrusted"))
            panel._refresh()
            if "disabled" not in panel.install.state():
                raise RuntimeError("Untrusted executable chooser enabled")
            panel.source.set(str(payload))
            panel._refresh()
            with patch("tools.fictional_installer_window.messagebox.askyesno",
                       return_value=True), \
                 patch("tools.fictional_installer_window.messagebox.showinfo"):
                panel.install.invoke()
            if panel.last_result != destination or not executable_at(destination).is_file():
                raise RuntimeError("Verified frozen GUI copy did not install")
            if not executable_at(payload).is_file():
                raise RuntimeError("Bundled prior executable was damaged")
            with patch("tools.fictional_installer_window.messagebox.showerror"):
                panel.install.invoke()
            if "denied" not in panel.status.get().lower():
                raise RuntimeError("Occupied destination was overwritten")
            # A modified private COPY of the bundled payload must be rejected
            # before executing its binary.
            tampered = Path(tmp) / "tampered-copy"
            import shutil
            shutil.copytree(payload, tampered)
            targets = list(tampered.rglob("start_pilot.py"))
            if len(targets) != 1:
                raise RuntimeError("Known app source not present in payload")
            targets[0].write_bytes(targets[0].read_bytes() + b"\n# TEST TAMPER\n")
            try:
                verify_payload(tampered)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("Modified app was not denied")
        finally:
            root.destroy()
    print("Frozen installer GUI: cancel, sealed source, confirmed install, "
          "older app preserved, overwrite and tamper denied PASS")
    return 0


def main() -> int:
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] not in
                             ("--verify", "--self-test-installer")):
        return 2
    try:
        payload = payload_root()
        verify_payload(payload)
    except (OSError, RuntimeError):
        print("FICTIONAL INSTALLER DENIED: bundled app is not verified",
              file=sys.stderr)
        return 2
    if len(sys.argv) == 2 and sys.argv[1] == "--verify":
        print("Sealed fictional installer payload: PASS")
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test-installer":
        return internal_gui_test(payload)
    root = tk.Tk()
    SealedFictionalInstaller(root, payload)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
