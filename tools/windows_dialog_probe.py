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
              "new_dialogs": [], "note": "No customer acceptance asserted"}
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
        controls = [c for c in main.descendants() if c.class_name() == "Button"]
        # The six unnamed Tk buttons were independently observed on run 43336349270.
        if len(controls) != 6:
            result["probe"] = "UNRESOLVED_BUTTON_TOPOLOGY"
            result["button_count"] = len(controls)
            return
        controls[3].click_input()
        time.sleep(2)
        result["after"] = visible_windows(proc.pid)
        previous = {w["handle"] for w in result["before"]}
        result["new_dialogs"] = [w for w in result["after"] if w["handle"] not in previous]
        result["probe"] = "DIALOG_DISCOVERED" if result["new_dialogs"] else "UNRESOLVED_NO_NEW_TOP_LEVEL_WINDOW"
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


if __name__ == "__main__":
    diagnose()
