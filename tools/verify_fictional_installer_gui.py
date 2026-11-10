"""Host-native internal installer Tk acceptance with real frozen onedir copies.

This is not a real client installer or an encrypted backup. It stages one
existing verified fictional app into a NEW folder using its real GUI button.
"""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
from unittest.mock import patch

from tools.fictional_installer_window import FictionalInstallerWindow
from tools.qualify_fictional_install import executable_at


def verify(source: Path):
    with TemporaryDirectory(prefix="fictional-installer-tk-") as tmp:
        root = tk.Tk()
        root.withdraw()
        ui = FictionalInstallerWindow(root)
        target = Path(tmp) / "new-fictional-app"
        ui.source.set(str(source))
        ui.destination.set(str(target))
        ui.previous.set(str(source))
        ui.confirm.set(True)
        ui._refresh()
        try:
            with patch("tools.fictional_installer_window.messagebox.askyesno",
                       return_value=False):
                ui.install.invoke()
            if target.exists() or "Cancelled" not in ui.status.get():
                raise RuntimeError("Cancel modified installation")
            with patch("tools.fictional_installer_window.messagebox.askyesno",
                       return_value=True), \
                 patch("tools.fictional_installer_window.messagebox.showinfo"):
                ui.install.invoke()
            if ui.last_result != target or not executable_at(target).is_file():
                raise RuntimeError("Real Tk install failed")
            # Old and newly staged executables must both pass their integrity.
            ui.check_previous_version()
            if "verified" not in ui.status.get():
                raise RuntimeError("Old version is not usable after install")
            if not executable_at(source).is_file():
                raise RuntimeError("Old version overwritten")
            # A second click on an occupied path must never overwrite it.
            with patch("tools.fictional_installer_window.messagebox.showerror"):
                ui.install.invoke()
            if "denied" not in ui.status.get().lower():
                raise RuntimeError("Existing folder overwrite not denied")
        finally:
            if root.winfo_exists():
                root.destroy()
    print("Native fictional installer window: cancel, confirm, stage, "
          "previous version and overwrite denial PASS")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    args = p.parse_args()
    verify(args.source.resolve())


if __name__ == "__main__":
    main()
