"""Black-box Windows acceptance: click recovery controls in the *frozen* EXE.

Only fictional records and temporary local files. No tokens or archives logged.
No application monkeypatching: the subprocess executes the PyInstaller binary.
"""
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from pywinauto import Desktop
from pywinauto.keyboard import send_keys
from src.offline_pilot import initialize_fictional_pilot
from src.secure_engine import SecureCore, Denied

TITLE = "My Traveling Lawyer"


@contextmanager
def core_session(path):
    core = SecureCore(path)
    try:
        yield core
    finally:
        core.close()

EXE = Path("dist/MyTravelingLawyer-Practice/MyTravelingLawyer-Practice.exe").resolve()


_ACTIVE_PID = None


def native_dialog():
    # Independently observed #32770 is a WIN32 class, not a UIA class.
    for candidate in Desktop(backend="win32").windows():
        try:
            if (candidate.is_visible() and candidate.process_id() == _ACTIVE_PID
                    and candidate.class_name() == "#32770"):
                return Desktop(backend="uia").window(
                    handle=candidate.handle).wrapper_object()
        except Exception:
            continue
    return None


def window(title, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if title == TITLE:
            dialog = native_dialog()
            if dialog is not None:
                return dialog
        try:
            for w in Desktop(backend="uia").windows():
                if (w.is_visible() and
                        (_ACTIVE_PID is None or w.process_id() == _ACTIVE_PID)
                        and title.lower() in (w.window_text() or "").lower()):
                    return w
        except Exception:
            pass
        time.sleep(.3)
    raise AssertionError("FROZEN_UI_WINDOW_MISSING: " + title)


def file_picker(timeout=20):
    # Run 43337782076: native #32770 file dialog titled with APP title.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        picker = native_dialog()
        if picker is not None:
            return picker
        time.sleep(.3)
    raise AssertionError("FROZEN_NATIVE_FILE_PICKER_NOT_FOUND")


def click(w, title):
    buttons = [b for b in w.descendants(control_type="Button")
               if b.window_text() == title and b.is_visible()]
    if buttons:
        buttons[0].click_input()
        return
    # Exact observed frozen Tk control tree (public startup only): six native
    # Button HWNDs, all unnamed, ordered like the six defined Tk buttons.
    native = [b for b in w.descendants(control_type="Button")
              if b.element_info.class_name == "Button" and b.is_visible()]
    startup = ("Create Practice Case", "Open Practice Case", "Practice Help",
               "Back Up Practice Case", "Restore Practice Backup", "Close")
    if len(native) == 6 and title in startup:
        # Verified in GitHub Actions 43437002166: the backup control is
        # fourth by increasing screen Y, not fourth in enumeration order.
        native = sorted(native, key=lambda b: b.rectangle().top)
        if len({b.rectangle().top for b in native}) != 6:
            raise AssertionError("FROZEN_STARTUP_BUTTON_GEOMETRY_AMBIGUOUS")
        native[startup.index(title)].click_input()
        return
    # Tk modal buttons can also be unnamed. Require exact count and action.
    if len(native) == 2 and title in ("OK", "Cancel"):
        native[0 if title == "OK" else 1].click_input()
        return
    if len(native) == 1 and title == "I saved the NEW codes":
        native[0].click_input()
        return
    raise AssertionError("FROZEN_BUTTON_UNRESOLVED: " + title +
                         " native_count=" + str(len(native)))


def choose_file(title, path):
    # The real backup picker was observed with exact title and native
    # Edit control ID 1148, action button ID 1 on run 43437002166.
    deadline = time.monotonic() + 15
    dlg = None
    while time.monotonic() < deadline:
        for candidate in Desktop(backend="win32").windows():
            try:
                if (candidate.process_id() == _ACTIVE_PID and candidate.is_visible()
                        and candidate.class_name() == "#32770"
                        and candidate.window_text() == title):
                    dlg = candidate
                    break
            except Exception:
                continue
        if dlg is not None:
            break
        time.sleep(.25)
    if dlg is None:
        raise AssertionError("FROZEN_EXACT_FILE_PICKER_NOT_FOUND: " + title)
    # Run 43437002166: Open picker filename Edit ID 1148.
    # Run 43437749574: Save picker filename Edit ID 1001 (first;
    # second matching edit belongs to the search box).
    filename_id = 1001 if title.startswith("Save ") else 1148
    edits = [c for c in dlg.descendants()
             if c.class_name() == "Edit" and c.control_id() == filename_id]
    actions = [c for c in dlg.descendants()
               if c.class_name() == "Button" and c.control_id() == 1]
    if (len(actions) != 1 or (len(edits) < 1 or
            (filename_id == 1148 and len(edits) != 1))):
        raise AssertionError("FROZEN_FILE_PICKER_CONTROL_TOPOLOGY_DENIED")
    # First ID-1001 field belongs to the save filename ComboBox; the later
    # ID-1001 field is native search. Never log the fictional filename.
    edits[0].set_edit_text(str(path))
    actions[0].click_input()
    return dlg


def acknowledge(title):
    dlg = window(title)
    click(dlg, "OK")


def wait_file(path, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and path.stat().st_size > 0:
            return
        time.sleep(.3)
    raise AssertionError("FROZEN_OUTPUT_MISSING: " + path.name)


def main():
    global _ACTIVE_PID
    if not EXE.is_file():
        raise AssertionError("FROZEN_EXE_MISSING")
    with tempfile.TemporaryDirectory(prefix="mtl-frozen-") as td:
        root = Path(td)
        source = root / "invented-case.sqlite3"
        backup = root / "invented-backup.json"
        restored = root / "invented-restored.sqlite3"
        accounts = initialize_fictional_pilot(source)
        owner = accounts["editor_token"]
        reviewer = accounts["reviewer_token"]
        with core_session(source) as core:
            matter = core.create_matter(owner, "Extra invented matter")
            core.create_task(owner, matter["id"], "Invented task", "2031-02-01T00:00:00Z")
            expected = {}
            for table in ("matters", "tasks", "audit_chain", "research_evidence"):
                expected[table] = [tuple(row) for row in core.db.execute(
                    "SELECT * FROM " + table + " ORDER BY rowid")]
            assert core.verify_audit()
        proc = subprocess.Popen([str(EXE)], cwd=str(EXE.parent),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _ACTIVE_PID = proc.pid
            app = window(TITLE, 30)
            click(app, "Back Up Practice Case")
            choose_file("Choose practice case to back up", source)
            choose_file("Save practice backup as", backup)
            if os.getenv("MTL_DIAG_SAVE_ONLY") == "1":
                print("FROZEN_SAVE_DIAGNOSTIC_ONLY=VERIFIED", flush=True)
                return
            prompt = window(TITLE)
            # Tk simpledialog has a live hidden Entry; no code in test output.
            entries = [x for x in prompt.descendants(control_type="Edit") if x.is_visible()]
            if not entries:
                raise AssertionError("OWNER_AUTH_DIALOG_MISSING")
            entries[-1].set_edit_text(owner)
            click(prompt, "OK")
            wait_file(backup)
            raw = backup.read_bytes()
            assert owner.encode() not in raw and reviewer.encode() not in raw
            assert hashlib.sha256(owner.encode()).hexdigest().encode() not in raw
            acknowledge(TITLE)
            print("FROZEN_EXE_BACKUP_BUTTON=VERIFIED")

            app = window(TITLE)
            click(app, "Restore Practice Backup")
            choose_file("Choose practice backup to restore", backup)
            choose_file("Save restored practice case as", restored)
            confirm = window(TITLE)
            click(confirm, "Yes")
            wait_file(restored)
            codes = window("Save NEW restored practice access codes")
            edits = codes.descendants(control_type="Edit")
            new_tokens = [e.window_text() for e in edits if e.window_text()]
            if len(new_tokens) < 2 or len(set(new_tokens)) != len(new_tokens):
                raise AssertionError("NEW_CODE_DIALOG_UNREADABLE")
            click(codes, "I saved the NEW codes")
            print("FROZEN_EXE_RESTORE_BUTTON=VERIFIED")

            # Readback is separate from the frozen EXE: verify what it actually wrote.
            with core_session(restored) as core:
                assert core.verify_audit()
                for table, rows in expected.items():
                    assert [tuple(v) for v in core.db.execute(
                        "SELECT * FROM " + table + " ORDER BY rowid")] == rows
                for token in (owner, reviewer):
                    try:
                        core._identity(token)
                    except Denied:
                        pass
                    else:
                        raise AssertionError("OLD_CODE_ACCEPTED")
                for token in new_tokens:
                    core._identity(token)
            print("FROZEN_EXE_RECORDS_AUDIT_NEW_AUTH_OLD_DENIAL=VERIFIED")

            # Existing destination must remain byte-for-byte unchanged.
            before = restored.read_bytes()
            click(window(TITLE), "Restore Practice Backup")
            choose_file("Choose practice backup to restore", backup)
            choose_file("Save restored practice case as", restored)
            acknowledge(TITLE)
            assert restored.read_bytes() == before
            print("FROZEN_EXE_OVERWRITE_DENIAL=VERIFIED")

            # Tamper real exported archive; a different unused file must not appear.
            invalid = root / "invented-tampered.json"
            bad = root / "tamper-destination.sqlite3"
            tampered = json.loads(raw)
            tampered["sha256"] = "0" * 64
            invalid.write_text(json.dumps(tampered), encoding="utf-8")
            click(window(TITLE), "Restore Practice Backup")
            choose_file("Choose practice backup to restore", invalid)
            choose_file("Save restored practice case as", bad)
            click(window(TITLE), "Yes")
            acknowledge(TITLE)
            assert not bad.exists()
            print("FROZEN_EXE_TAMPER_DENIAL=VERIFIED")
            click(window(TITLE), "Close")
            proc.wait(timeout=15)

            # A fresh OS process confirms file persistence, not just a hot refresh.
            reopened = subprocess.Popen([str(EXE)], cwd=str(EXE.parent),
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                window(TITLE, 30)
                with core_session(restored) as core:
                    assert core.verify_audit()
                    for table, rows in expected.items():
                        assert [tuple(v) for v in core.db.execute(
                            "SELECT * FROM " + table + " ORDER BY rowid")] == rows
                click(window(TITLE), "Close")
                reopened.wait(timeout=15)
            finally:
                if reopened.poll() is None:
                    reopened.kill()
                    reopened.wait()
            print("FROZEN_EXE_COLD_RESTART_AND_READBACK=VERIFIED")
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    main()
