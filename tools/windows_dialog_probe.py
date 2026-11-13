"""Read-only-to-app Windows frozen Tk file-picker diagnosis; fictional case only.

Launches the actual frozen executable. Records only HWND/class/title metadata,
not screenshots, text contents, credentials, filesystem paths, or case data.
No automatic retries or customer acceptance claims.
"""
import json
import subprocess
import time
from pathlib import Path

from pywinauto import Desktop

EXE = Path("dist/MyTravelingLawyer-Practice/MyTravelingLawyer-Practice.exe").resolve()
REPORT = Path("frozen-dialog-diagnostic.json")


def visible_windows(pid):
    windows = []
    for w in Desktop(backend="win32").windows():
        try:
            if w.is_visible() and w.process_id() == pid:
                windows.append({
                    "handle": int(w.handle),
                    "class": str(w.class_name())[:70],
                    "title": str(w.window_text())[:110],
                })
        except Exception:
            continue
    return sorted(windows, key=lambda w: w["handle"])


def diagnose():
    if not EXE.is_file():
        raise RuntimeError("FROZEN_EXE_MISSING")
    proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    result = {"schema": "mtl.frozen.dialog.probe.v1",
              "exact_sha": __import__("os").environ.get("GITHUB_SHA", ""),
              "probe": "UNRESOLVED", "before": [], "after": [],
              "new_dialogs": [], "native_controls": [], "uia_controls": [],
              "startup_buttons": [], "selected_button": None,
              "note": "No customer acceptance asserted"}
    try:
        deadline = time.monotonic() + 20
        main = None
        while time.monotonic() < deadline:
            for w in Desktop(backend="win32").windows():
                try:
                    if w.process_id() == proc.pid and w.is_visible() and "My Traveling Lawyer" in w.window_text():
                        main = w
                        break
                except Exception:
                    pass
            if main:
                break
            time.sleep(.2)
        if not main:
            result["probe"] = "DENIED_MAIN_WINDOW_MISSING"
            return
        result["before"] = visible_windows(proc.pid)
        controls = [c for c in main.descendants()
                    if c.class_name() == "Button" and c.is_visible()]
        # Stable evidence: location, parent HWND, native class and control ID,
        # never the private content or inaccessible Tk widget text.
        geometry = []
        for child in controls:
            rect = child.rectangle()
            geometry.append({"handle": int(child.handle),
                             "parent": int(child.parent().handle),
                             "control_id": int(child.control_id()),
                             "class": child.class_name(),
                             "x": int(rect.left), "y": int(rect.top),
                             "width": int(rect.width()),
                             "height": int(rect.height())})
        result["startup_buttons"] = geometry
        if len(controls) != 6 or len({g["y"] for g in geometry}) != 6:
            result["probe"] = "UNRESOLVED_BUTTON_TOPOLOGY"
            result["button_count"] = len(controls)
            return
        ordered = sorted(controls, key=lambda c: c.rectangle().top)
        # GUI source defines vertical button order; confirm through physical
        # layout rather than unrelated Win32 enumeration order.
        selected = ordered[3]
        result["selected_button"] = {
            "selection": "fourth-by-screen-y",
            "handle": int(selected.handle),
            "control_id": int(selected.control_id()),
            "observed_y": int(selected.rectangle().top)}
        selected.click_input()
        time.sleep(2)
        result["after"] = visible_windows(proc.pid)
        previous = {w["handle"] for w in result["before"]}
        result["new_dialogs"] = [w for w in result["after"] if w["handle"] not in previous]
        result["probe"] = "DIALOG_DISCOVERED" if result["new_dialogs"] else "UNRESOLVED_NO_NEW_TOP_LEVEL_WINDOW"
        # Only inventory class/control ID and bounded, allowlisted generic labels.
        # Do not read file paths, editable values or credential fields.
        result["native_controls"] = []
        result["uia_controls"] = []
        for d in Desktop(backend="win32").windows():
            try:
                if d.process_id() != proc.pid or not d.is_visible() or d.class_name() != "#32770":
                    continue
                for child in d.descendants()[:60]:
                    kind = child.class_name()
                    cid = child.control_id()
                    label = child.window_text()
                    safe_label = label if label in ("File name:", "File name", "Open", "Save", "Cancel", "Files of type:", "All files (*.*)") else ""
                    result["native_controls"].append({"class": kind[:50], "control_id": cid, "safe_label": safe_label})
                uia = Desktop(backend="uia").window(handle=d.handle).wrapper_object()
                for child in uia.descendants()[:60]:
                    kind = child.element_info.control_type
                    result["uia_controls"].append({"type": kind[:50],
                                                    "class": child.element_info.class_name[:50]})
                break
            except Exception:
                result["probe"] = "UNRESOLVED_NATIVE_CHILD_INSPECTION"
                break
        if not result["native_controls"]:
            result["probe"] = "UNRESOLVED_NO_NATIVE_CHILD_CONTROLS"
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        REPORT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print("FROZEN_DIALOG_PROBE=" + result["probe"], flush=True)
        for w in result["new_dialogs"]:
            print("FROZEN_NEW_WINDOW_CLASS=" + w["class"] + " TITLE=" + w["title"], flush=True)
        print("FROZEN_STARTUP_BUTTON_Y=" + ",".join(str(b["y"]) for b in result["startup_buttons"]), flush=True)
        print("FROZEN_SELECTED_BUTTON=" + str(result["selected_button"]["selection"] if result["selected_button"] else "NONE"), flush=True)
        print("FROZEN_NATIVE_CONTROL_CLASSES=" + ",".join(c["class"] for c in result["native_controls"]), flush=True)
        print("FROZEN_NATIVE_CONTROL_IDS=" + ",".join(str(c["control_id"]) for c in result["native_controls"]), flush=True)


if __name__ == "__main__":
    diagnose()
