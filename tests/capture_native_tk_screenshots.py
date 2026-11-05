"""Capture ONLY fictional local Tk GUI screenshots on an authorized X display.

Offline synthetic acceptance utility, never use real client credentials/data.
Writes PNGs and hash manifest under ignored CI artifacts; no network calls.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import ctypes
import ctypes.util
import struct
import zlib
import tempfile

from src.secure_engine import SecureCore
from src.attorney_research_workflow import AttorneyResearchWorkflow
from src.local_operator_gui import launch_gui


def _png_chunk(kind, contents):
    data = kind + contents
    return (struct.pack("!I", len(contents)) + data +
            struct.pack("!I", zlib.crc32(data) & 0xffffffff))


def _native_x11_png(root, output):
    """Read pixels from this synthetic Tk window through existing libX11.

    Xvfb on hosted Linux is truecolor 24-bit with RGB component masks.
    This does not create a network listener, install dependencies or
    capture other applications.
    """
    library = ctypes.util.find_library("X11")
    if not library:
        raise RuntimeError("SCREENSHOT NOT CAPTURED: libX11 unavailable")
    x11 = ctypes.CDLL(library)
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XGetImage.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                             ctypes.c_int, ctypes.c_int, ctypes.c_uint,
                             ctypes.c_uint, ctypes.c_ulong, ctypes.c_int]
    x11.XGetImage.restype = ctypes.c_void_p
    x11.XGetPixel.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    x11.XGetPixel.restype = ctypes.c_ulong
    x11.XDestroyImage.argtypes = [ctypes.c_void_p]
    x11.XDestroyImage.restype = ctypes.c_int
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    x11.XCloseDisplay.restype = ctypes.c_int
    display = x11.XOpenDisplay(None)
    if not display:
        raise RuntimeError("SCREENSHOT NOT CAPTURED: graphical display unavailable")
    image = None
    try:
        width, height = root.winfo_width(), root.winfo_height()
        if root.winfo_depth() < 24 or root.winfo_visual() != "truecolor":
            raise RuntimeError("SCREENSHOT NOT CAPTURED: unsupported X visual")
        image = x11.XGetImage(display, int(root.winfo_id()), 0, 0,
                             width, height, ctypes.c_ulong(-1).value, 2)
        if not image:
            raise RuntimeError("SCREENSHOT NOT CAPTURED: XGetImage failed")
        rows = []
        for y in range(height):
            pixels = bytearray(width * 3 + 1)
            for x in range(width):
                px = x11.XGetPixel(image, x, y)
                offset = 1 + x * 3
                pixels[offset] = (px >> 16) & 255
                pixels[offset + 1] = (px >> 8) & 255
                pixels[offset + 2] = px & 255
            rows.append(bytes(pixels))
        body = zlib.compress(b"".join(rows), level=6)
        output.write_bytes(
            b"\x89PNG\r\n\x1a\n" +
            _png_chunk(b"IHDR", struct.pack("!IIBBBBB",
                       width, height, 8, 2, 0, 0, 0)) +
            _png_chunk(b"IDAT", body) + _png_chunk(b"IEND", b""))
    finally:
        if image:
            x11.XDestroyImage(image)
        x11.XCloseDisplay(display)


def capture_fictional_windows(destination):
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
                # Fail the actual screenshot job when essential keyboard help
                # is outside the native client area, especially at 580x520.
                from tkinter import ttk
                help_labels = [item for item in widgets
                    if isinstance(item, ttk.Label)
                    and str(item.cget("text")).startswith("Keyboard: Alt+M")]
                if len(help_labels) != 1:
                    raise RuntimeError("Native keyboard-help label missing")
                help_label = help_labels[0]
                bottom = help_label.winfo_rooty() - root.winfo_rooty() + help_label.winfo_height()
                if not help_label.winfo_ismapped() or bottom > root.winfo_height():
                    raise RuntimeError(
                        f"Native keyboard-help footer clipped at {w}x{h}: "
                        f"bottom={bottom}, height={root.winfo_height()}")
                out = folder / f"fictional_operator_{w}x{h}.png"
                # A read-only capture of the visible synthetic Tk window.
                _native_x11_png(root, out)
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
