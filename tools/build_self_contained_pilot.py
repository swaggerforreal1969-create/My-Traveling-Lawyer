"""Local unsigned, fictional-only PyInstaller onedir candidate. NEVER DISTRIBUTE.

Uses only the existing tested offline preview closure. Not an installer or
release artifact, not a security approval, and not permission to publish originals.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.build_offline_pilot_preview import build as build_preview, ROOT_NAME

BOOTSTRAP = ROOT / "tools" / "frozen_pilot_bootstrap.py"
APP_NAME = "MTL-Fictional-Practice-NOT-FOR-CLIENTS"
FORBIDDEN = {
    "My-Travelling-Lawyer-OPEN-ME.html", "src/__init__.py", "src/app.js",
    "src/index.html", "src/secure_app.js", "src/secure_index.html",
    "src/secure_server.py", "tests/test_custody_v11.py", "tests/test_engine.py",
    "tests/test_milestone_v06.py",
}


def extract_approved(archive: Path, destination: Path) -> Path:
    """Never extract an unlisted member, restricted source, or symlink."""
    root = destination / ROOT_NAME
    with ZipFile(archive) as z:
        members = z.infolist()
        prefix = ROOT_NAME + "/"
        if any(not m.filename.startswith(prefix) for m in members):
            raise ValueError("Unexpected preview archive root")
        names = [m.filename[len(prefix):] for m in members]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate preview archive entry")
        if any(m.is_dir() or ((m.external_attr >> 16) & 0o170000) == 0o120000 for m in members):
            raise ValueError("Directory or symlink entry forbidden")
        if FORBIDDEN.intersection(names) or any(n.startswith("tests/") for n in names):
            raise ValueError("Restricted original in candidate package")
        manifest = json.loads(z.read(prefix + "MANIFEST.json"))
        source = manifest["sha256"]
        assets = manifest["asset_sha256"]
        expected = set(source) | set(assets) | {"MANIFEST.json"}
        if set(names) != expected:
            raise ValueError("Unexpected or missing candidate package files")
        if len(source) != 23:
            raise ValueError("Unexpected allowed Python module count")
        if any(not n.startswith("src/") or not n.endswith(".py") or
               len(Path(n).parts) != 2 for n in source):
            raise ValueError("Disallowed application source path")
        root.mkdir(parents=True, exist_ok=False)
        for name in sorted(names):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(prefix + name))
    return root


def prepare_staging(staging: Path) -> tuple[Path, Path]:
    staging.mkdir(parents=True, exist_ok=False)
    preview = staging / "approved-preview.zip"
    build_preview(preview)
    package = extract_approved(preview, staging)
    manifest_sha = sha256((package / "MANIFEST.json").read_bytes()).hexdigest()
    template = BOOTSTRAP.read_text(encoding="utf-8")
    if template.count("__MANIFEST_SHA256__") != 1:
        raise ValueError("Unexpected frozen bootstrap digest placeholder")
    boot = staging / "frozen_bootstrap.py"
    boot.write_text(template.replace("__MANIFEST_SHA256__", manifest_sha),
                    encoding="utf-8")
    # Include only this newly authored fictional acceptance driver as a
    # staged build-time module. Never expose full repository source to the
    # PyInstaller analyzer (the ten restricted originals stay out of scope).
    harness = ROOT / "tools" / "frozen_gui_acceptance.py"
    (staging / "frozen_gui_acceptance.py").write_bytes(harness.read_bytes())
    return package, boot


def build(output: Path) -> Path:
    """Build locally, verify the resulting executable, and never overwrite."""
    output = Path(output).resolve()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Existing output is never overwritten")
    if not output.parent.is_dir():
        raise FileNotFoundError("Build output folder missing")
    with TemporaryDirectory(prefix="mtl-frozen-") as tmp:
        package, bootstrap = prepare_staging(Path(tmp) / "staging")
        dist = Path(tmp) / "dist"
        cmd = [
            sys.executable, "-m", "PyInstaller", "--onedir", "--noconfirm",
            "--clean", "--name", APP_NAME, "--distpath", str(dist),
            "--workpath", str(Path(tmp) / "work"),
            "--specpath", str(Path(tmp) / "spec"),
            "--paths", str(package.parent),
            "--paths", str(package),
            "--add-data", str(package) + os.pathsep + ROOT_NAME,
            "--hidden-import", "tkinter",
            "--hidden-import", "tkinter.filedialog",
            "--hidden-import", "tkinter.messagebox",
            "--hidden-import", "tkinter.simpledialog",
            "--hidden-import", "sqlite3", "--hidden-import", "_sqlite3",
            "--hidden-import", "frozen_gui_acceptance",
            str(bootstrap),
        ]
        subprocess.run(cmd, cwd=str(package.parent), check=True)
        built = dist / APP_NAME
        if not built.is_dir():
            raise RuntimeError("PyInstaller did not create a one-folder prototype")
        executable = built / (APP_NAME + (".exe" if os.name == "nt" else ""))
        if not executable.is_file():
            raise RuntimeError("Self-contained fictional executable not found")
        subprocess.run([str(executable), "--verify"], cwd=str(built),
                       check=True, timeout=60)
        # The actual compiled executable drives native Tk in a disposable
        # directory; OS file choosers/confirmations receive synthetic inputs.
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["MTL_FICTIONAL_CI_ACCEPTANCE"] = "1"
        command = [str(executable), "--gui-acceptance"]
        if sys.platform.startswith("linux") and not env.get("DISPLAY"):
            if not shutil.which("xvfb-run"):
                raise RuntimeError("Virtual X display required for Linux Tk")
            command = ["xvfb-run", "-a", *command]
        subprocess.run(command, cwd=str(built), env=env,
                       check=True, timeout=210)
        # The compiled binary itself must reject modified bundled assets.
        internal = built / "_internal" / ROOT_NAME
        if not internal.is_dir():
            raise RuntimeError("Expected bundled fictional package missing")
        for name in ("MANIFEST.json", "run_pilot.py", "start_pilot.py"):
            item = internal / name
            original = item.read_bytes()
            try:
                item.write_bytes(original + b"\n# synthetic modification\n")
                result = subprocess.run(
                    [str(executable), "--verify"], cwd=str(built),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=60)
                if result.returncode == 0:
                    raise RuntimeError("Frozen tampered package accepted: " + name)
            finally:
                item.write_bytes(original)
        subprocess.run([str(executable), "--verify"], cwd=str(built),
                       check=True, timeout=60)
        shutil.move(str(built), str(output))
    return output


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args(argv)
    print("FICTIONAL ONLY - NOT FOR CLIENTS - DO NOT DISTRIBUTE", flush=True)
    print(json.dumps({"output": str(build(a.output)), "signed": False,
                      "production_approved": False}, sort_keys=True))


if __name__ == "__main__":
    main()
