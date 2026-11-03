"""Capture ONLY fictional local Tk GUI screenshots on an authorized X display.

Offline synthetic acceptance utility, never use real client credentials/data.
Writes PNGs and hash manifest under ignored CI artifacts; no network calls.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

from src.secure_engine import SecureCore
from src.attorney_research_workflow import AttorneyResearchWorkflow
from src.local_operator_gui import launch_gui


def capture_fictional_windows(destination):
    capture_tool = shutil.which("import")
    if capture_tool is None:
        raise RuntimeError("SCREENSHOT NOT CAPTURED: approved ImageMagick import unavailable")
    folder = Path(destination)
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix="mtl-fictional-tk-") as temporary:
        core = SecureCore(Path(temporary) / "fictional.sqlite3")
        root = None
        try:
            firm = core.provision_firm("Imaginary Legal Practice")
            _, author = core.provision_user(firm, "Fictional Author")
            reviewer_id, reviewer = core.provision_user(firm, "Fictional Reviewer")
            matter_id = core.create_matter(author, "SYNTHETIC CASE")["id"]
            core.grant(author, matter_id, reviewer_id, "editor", 1)
            core.create_task(author, matter_id, "SYNTHETIC TASK",
                             "2026-10-01T00:00:00Z")
            flow = AttorneyResearchWorkflow(core)
            evidence = flow.evidence.add(author, matter_id, "SYNTHETIC SOURCE",
                    "https://example.org/fictional", "SYNTHETIC EXCERPT")["id"]
            flow.observations.capture(author, matter_id, evidence,
                    "Fictional manual capture", "Synthetic observation only")
            root = launch_gui(core, reviewer, run_mainloop=False)
            root.update()
            widgets = []
            def walk(node):
                for child in node.winfo_children():
                    widgets.append(child)
                    walk(child)
            walk(root)
            from tkinter import Listbox
            from tkinter.ttk import Button
            matters = next(w for w in widgets if isinstance(w, Listbox))
            select = next(w for w in widgets
                          if isinstance(w, Button) and w.cget("text") == "Select matter")
            matters.selection_set(0)
            matters.event_generate("<<ListboxSelect>>")
            root.update()
            select.invoke()
            root.update()
            # Window dimensions are actual native X geometry, not guessed.
            for w, h in ((580, 520), (760, 650), (1024, 768)):
                root.geometry(f"{w}x{h}+0+0")
                root.update()
                if (root.winfo_width(), root.winfo_height()) != (w, h):
                    raise RuntimeError("Native Tk window geometry differs from requested size")
                out = folder / f"fictional_operator_{w}x{h}.png"
                # A read-only capture of the visible synthetic Tk window.
                subprocess.run([capture_tool, "-window", str(root.winfo_id()),
                                str(out)], check=True, timeout=20, capture_output=True)
                data = out.read_bytes()
                if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) < 1024:
                    raise RuntimeError("Screenshot missing or not a valid PNG")
                records.append({"file": out.name, "width": w, "height": h,
                     "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        finally:
            if root is not None:
                root.destroy()
            core.close()
    manifest = {"schema": "mtl.synthetic.tk.screenshots.v1",
        "synthetic_only": True, "screenshot_count": len(records),
        "captures": records, "human_visual_verified": False,
        "screen_reader_verified": False, "production_approved": False}
    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if len(records) != 3:
        raise RuntimeError("Three graphical screenshot captures required")
    print("SYNTHETIC TK SCREENSHOTS: 3 valid PNGs; screenshots are not visual certification")
    return manifest


if __name__ == "__main__":
    capture_fictional_windows("artifacts/tk-screenshots")
