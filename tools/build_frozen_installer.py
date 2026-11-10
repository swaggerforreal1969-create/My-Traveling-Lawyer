"""Produce LOCAL unsigned, self-contained fictional installer with sealed app.

Do not upload binaries. This is NOT a signed publisher installer or release.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from tools.qualify_fictional_install import executable_at, assert_private_tree

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "tools" / "frozen_installer_entry.py"
NAME = "MTL-Fictional-Installer-NOT-FOR-CLIENTS"


def payload_inventory(source: Path) -> dict[str, str]:
    assert_private_tree(source)
    found = {}
    for item in source.rglob("*"):
        name = item.relative_to(source).as_posix()
        if item.is_symlink():
            if not item.resolve(strict=True).is_relative_to(source.resolve()):
                raise ValueError("External payload link denied")
            found[name] = "link:" + os.readlink(item)
        elif item.is_file():
            if item.suffix in (".sqlite3", ".db"):
                raise ValueError("Confidential installer payload")
            found[name] = sha256(item.read_bytes()).hexdigest()
    if not found or not executable_at(source).is_file():
        raise ValueError("No frozen application payload found")
    return dict(sorted(found.items()))


def build(source: Path, output: Path) -> Path:
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Existing installer output is never overwritten")
    if not output.parent.is_dir():
        raise ValueError("Output parent missing")
    inventory = payload_inventory(source)
    with TemporaryDirectory(prefix="mtl-installer-build-") as tmp:
        stage = Path(tmp)
        template = ENTRY.read_text(encoding="utf-8")
        literal = "INVENTORY = {}  # sealed inventory injected only in private build"
        if template.count(literal) != 1:
            raise RuntimeError("Installer inventory placeholder missing")
        entry = stage / "sealed_installer_bootstrap.py"
        entry.write_text(
            template.replace(literal, "INVENTORY = " + repr(inventory)),
            encoding="utf-8")
        dist = stage / "dist"
        cmd = [
            sys.executable, "-m", "PyInstaller", "--onedir", "--clean",
            "--noconfirm", "--name", NAME, "--distpath", str(dist),
            "--workpath", str(stage / "work"),
            "--specpath", str(stage / "spec"),
            "--paths", str(ROOT),
            "--hidden-import", "tkinter",
            "--hidden-import", "tkinter.ttk",
            "--hidden-import", "tkinter.filedialog",
            "--hidden-import", "tkinter.messagebox",
            "--hidden-import", "tools.fictional_installer_window",
            "--hidden-import", "tools.qualify_fictional_install",
            "--add-data", str(source) + os.pathsep + "approved-fictional-app",
            str(entry),
        ]
        subprocess.run(cmd, check=True, cwd=str(ROOT))
        folder = dist / NAME
        executable = folder / (NAME + (".exe" if os.name == "nt" else ""))
        if not executable.is_file():
            raise RuntimeError("No native frozen installer executable")
        for args in (("--verify",), ("--self-test-installer",)):
            command = [str(executable), *args]
            if sys.platform.startswith("linux"):
                if not shutil.which("xvfb-run"):
                    raise RuntimeError("Linux GUI needs virtual display")
                command = ["xvfb-run", "-a", *command]
            # No PYTHONPATH or system Python is needed in the launched process.
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            subprocess.run(command, check=True, timeout=240, cwd=str(stage),
                           env=env)
        shutil.move(str(folder), str(output))
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    print("INTERNAL FICTIONAL ONLY. NOT A SIGNED OR DISTRIBUTABLE INSTALLER.")
    print("Validated installer folder:", build(args.source, args.output))


if __name__ == "__main__":
    main()
