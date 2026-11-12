"""Finite, local deterministic coding worker. NOT a generative AI or recurring agent.
One allowlisted onboarding feature, only on the isolated diesel branch.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "diesel/mtl-windows-agent-20261112"
QUEUE_PATH = ROOT / "docs" / "diesel-agent-queue.json"
GUI_PATH = ROOT / "tools" / "windows_fictional_gui.py"
TEST_PATH = ROOT / "tests" / "test_windows_practice_help.py"
ALLOWED = {"tools/windows_fictional_gui.py", "tests/test_windows_practice_help.py"}
BUTTON = 'tk.Button(root,text="Practice Help"'

def run(*args):
    print("$", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True, timeout=120)

def output(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, timeout=45).strip()

def verify_guards():
    q = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    if (q.get("version") != 1 or q.get("mode") != "ONE_SHOT" or
            q.get("allow_recurring") is not False or
            q.get("max_change_attempts") != 1 or
            q.get("max_changed_files") != 2 or not q.get("enabled")):
        raise RuntimeError("QUEUE_POLICY_DENIED")
    task = q.get("task", {})
    if task.get("id") != "windows-practice-help-onboarding":
        raise RuntimeError("UNAUTHORIZED_TASK")
    if set(task.get("allowed_files", [])) != ALLOWED or task.get("new_release_permission") is not False:
        raise RuntimeError("SCOPE_DENIED")
    if os.environ.get("GITHUB_REPOSITORY") != "swaggerforreal1969-create/My-Traveling-Lawyer":
        raise RuntimeError("REPOSITORY_DENIED")
    if os.environ.get("GITHUB_REF") != "refs/heads/" + BRANCH:
        raise RuntimeError("BRANCH_DENIED")
    if os.environ.get("GITHUB_EVENT_NAME") != "push":
        raise RuntimeError("EVENT_DENIED")
    if output("git","branch","--show-current") != BRANCH:
        raise RuntimeError("CHECKOUT_DENIED")
    if output("git","status","--porcelain","--untracked-files=no"):
        raise RuntimeError("UNCLEAN_TRACKED_BASELINE")
    if output("git","rev-parse","HEAD") != os.environ.get("GITHUB_SHA"):
        raise RuntimeError("NONEXACT_SOURCE_SHA")
    return q

def produce_change():
    before = GUI_PATH.read_text(encoding="utf-8")
    if BUTTON in before or "def show_practice_help(" in before or TEST_PATH.exists():
        raise RuntimeError("TASK_ALREADY_APPLIED_OR_CONFLICT")
    if before.count("def main():") != 1 or before.count('tk.Button(root,text="Close"') != 1:
        raise RuntimeError("SOURCE_DRIFT_DENIED")
    help_function = '''def show_practice_help(root):
    """Plain-language instructions for fictional, offline practice only."""
    messagebox.showinfo(
        TITLE,
        "1. Choose Create Practice Case to make a new practice file.\\n"
        "2. Save both access codes somewhere private. They will not appear again.\\n"
        "3. Choose Open Practice Case to open an existing practice file.\\n"
        "4. Only use made-up information. Never enter real client details.\\n"
        "5. The second reviewer's code belongs to another authorized person.\\n"
        "6. If you see an uncertain result, stop. Do not repeat the action.\\n"
        "7. Select Close when finished.",
        parent=root)

'''
    changed = before.replace("def main():",help_function+"def main():")
    changed = changed.replace('    tk.Button(root,text="Close",command=root.destroy).pack(pady=10)',
        '    tk.Button(root,text="Practice Help",width=28,command=lambda:show_practice_help(root)).pack(pady=3)\n'
        '    tk.Button(root,text="Close",command=root.destroy).pack(pady=10)')
    if changed == before or changed.count(BUTTON) != 1:
        raise RuntimeError("NO_VALID_SCOPED_CHANGE")
    tests = '''"""Standalone onboarding instructions — no actual Tk window required."""
import unittest
from unittest.mock import patch
from tools import windows_fictional_gui as gui

class PracticeHelpAcceptance(unittest.TestCase):
    def test_help_is_fictional_and_private(self):
        with patch.object(gui.messagebox,"showinfo") as display:
            root = object()
            gui.show_practice_help(root)
            display.assert_called_once()
            args, kwargs = display.call_args
            self.assertEqual(kwargs["parent"],root)
            text=args[1]
            for phrase in ("Create Practice Case","Open Practice Case",
                           "access codes","made-up information",
                           "second reviewer","uncertain result","Close"):
                self.assertIn(phrase.lower(),text.lower())
            self.assertIn("Never enter real client details",text)

    def test_existing_main_controls_preserved(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/
                "tools"/"windows_fictional_gui.py").read_text(encoding="utf-8")
        self.assertIn('tk.Button(root,text="Create Practice Case"',source)
        self.assertIn('tk.Button(root,text="Open Practice Case"',source)
        self.assertIn('tk.Button(root,text="Practice Help"',source)
        self.assertIn('tk.Button(root,text="Close"',source)

if __name__ == "__main__":
    unittest.main()
'''
    GUI_PATH.write_text(changed,encoding="utf-8")
    TEST_PATH.write_text(tests,encoding="utf-8")
    # Whitelist actual planned paths. Python __pycache__ files are not source edits.
    paths = set(output("git","diff","--name-only").splitlines())
    if TEST_PATH.exists():
        paths.add("tests/test_windows_practice_help.py")
    if paths != ALLOWED:
        raise RuntimeError(f"UNEXPECTED_FILES: {sorted(paths)}")
    run("git","diff","--check")
    for pattern in ("test_windows_practice_help.py","test_windows_build_candidate.py","test_store_msix_preparation.py"):
        run(sys.executable,"-m","unittest","discover","-s","tests","-p",pattern,"-v")
    run(sys.executable,"-m","py_compile",str(GUI_PATH),str(TEST_PATH))
    run("git","add","--","tools/windows_fictional_gui.py","tests/test_windows_practice_help.py")
    staged=output("git","diff","--cached","--name-only").splitlines()
    if set(staged) != ALLOWED:
        raise RuntimeError("STAGED_SCOPE_DENIED")
    return paths

def main():
    q=verify_guards()
    try:
        files=produce_change()
    except Exception:
        # No commit/push on any test or safety failure.
        print("DENIED: bounded code-change gate stopped; no source publication",flush=True)
        raise
    run("git","-c","user.name=Diesel Bounded Pilot","-c","user.email=diesel-bounded-pilot@users.noreply.github.com",
        "commit","-m","Add plain-language fictional Windows Practice Help with focused acceptance")
    sha=output("git","rev-parse","HEAD")
    if output("git","status","--porcelain","--untracked-files=no"):
        raise RuntimeError("POST_COMMIT_TRACKED_DIRTY")
    run("git","push","origin","HEAD:refs/heads/"+BRANCH)
    remote=output("git","ls-remote","origin","refs/heads/"+BRANCH).split()[0]
    if sha != remote:
        raise RuntimeError("REMOTE_HASH_MISMATCH")
    evidence={"result":"VERIFIED","type":"DETERMINISTIC_BOUNDED_CODING_WORKER_NOT_AI",
              "task":q["task"]["id"],"parent_sha":os.environ["GITHUB_SHA"],
              "new_commit_sha":sha,"files":sorted(files),
              "max_attempts":1,"recurring":False,"protected_merge":False,
              "signed":False,"smart_app_control":"UNRESOLVED",
              "production":"NO_GO"}
    (Path(os.environ.get("RUNNER_TEMP",str(ROOT)))/"diesel-agent-evidence.json").write_text(
        json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    print("DIESEL_AGENT_VERIFIED="+json.dumps(evidence,sort_keys=True),flush=True)

if __name__=="__main__":
    main()
