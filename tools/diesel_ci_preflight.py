"""DIESEL finite engineering CI planner: never disguise missing source as PASS."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = "b25fc1df65acd55e03ee77b193187e81d70bd21d"
WINDOWS_INPUTS = ("tools/windows_fictional_gui.py", "tools/build_signed_windows.ps1",
                  "src/offline_pilot.py", "src/fictional_pilot_backup.py",
                  "tools/windows_native_backup_restore_acceptance.py",
                  "tools/windows_frozen_recovery_acceptance.py")
INFRA_PREFIXES = ("docs/", ".github/workflows/")
INFRA_EXACT = ("tools/diesel_ci_preflight.py", "tests/test_diesel_ci_preflight.py")
REQUIRED_HTTP = ("src/secure_server.py", "tests/test_secure_http.py")

def get_plan(paths, *, http_source_present, queue):
    names = sorted(set(paths))
    unknown = [p for p in names if p.startswith("/") or ".." in Path(p).parts]
    if unknown:
        raise ValueError("Unsafe repository paths")
    windows = any(p in WINDOWS_INPUTS or p.startswith("native_windows_tests/") for p in names)
    source = [p for p in names if not p.startswith(INFRA_PREFIXES) and p not in INFRA_EXACT]
    security = {
        "status": "UNRESOLVED",
        "release_eligible": False,
        "missing_source": [],
    }
    if not http_source_present:
        security["status"] = "BLOCKED_REQUIRED_RESTRICTED_SOURCE"
        security["missing_source"] = ["src/secure_server.py"]
    elif "tests/test_secure_http.py" in REQUIRED_HTTP:
        security["status"] = "UNRESOLVED_REQUIRES_AUTHORIZED_SECURITY_RUN"
    if not isinstance(queue, dict) or queue.get("version") != 1 or queue.get("release") != "NO_GO":
        raise ValueError("Queue guard invalid")
    if queue.get("recurring_enabled") is not False:
        raise ValueError("Recurring automation denied")
    if not isinstance(queue.get("tasks"), list) or len(queue["tasks"]) != 4:
        raise ValueError("Four scoped tasks required")
    if any(task.get("state") not in ("VERIFIED", "UNRESOLVED", "BLOCKED") for task in queue["tasks"]):
        raise ValueError("Unknown queue state")
    return {
        "schema": "mtl.diesel.efficiency.preflight.v1",
        "changed_files": names,
        "customer_source_changed": bool(source),
        "windows_runner_required": windows,
        "linux_preflight_required": True,
        "security": security,
        "release": "NO_GO",
        "recurring_enabled": False,
        "tasks": queue["tasks"],
        "classification": "CUSTOMER_SOURCE_CHANGED" if source else "INFRA_ONLY_REUSE_CUSTOMER_EVIDENCE",
        "baseline_sha": BASE,
    }

def command(*args):
    return subprocess.check_output(args,cwd=ROOT,text=True,timeout=15).strip()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    sha=os.getenv("GITHUB_SHA","")
    ref=os.getenv("GITHUB_REF","")
    if ref!="refs/heads/diesel/mtl-efficient-pipeline-20261112":
        raise SystemExit("WRONG_BRANCH_DENIED")
    if os.getenv("GITHUB_EVENT_NAME")!="push":
        raise SystemExit("UNEXPECTED_EVENT_DENIED")
    if len(sha)!=40 or command("git","rev-parse","HEAD")!=sha:
        raise SystemExit("EXACT_SHA_DENIED")
    changed=command("git","diff","--name-only",BASE,sha).splitlines()
    queue=json.loads((ROOT/"docs"/"DIESEL_CUSTOMER_QUEUE.json").read_text(encoding="utf-8"))
    plan=get_plan(changed,http_source_present=(ROOT/"src"/"secure_server.py").is_file(),queue=queue)
    plan["source_sha"]=sha
    output=Path(args.out)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(plan,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    outputs=os.getenv("GITHUB_OUTPUT")
    if outputs:
        with open(outputs,"a",encoding="utf-8") as f:
            f.write("windows_required="+str(plan["windows_runner_required"]).lower()+"\n")
            f.write("source_changed="+str(plan["customer_source_changed"]).lower()+"\n")
            f.write("security_state="+plan["security"]["status"]+"\n")
    print("EXACT_SHA="+sha)
    print("WORK_SCOPE="+plan["classification"])
    print("WINDOWS_RUNNER_REQUIRED="+str(plan["windows_runner_required"]).upper())
    print("SECURE_HTTP_GATE="+plan["security"]["status"])
    print("CUSTOMER_RELEASE=NO_GO")

if __name__=="__main__":
    main()
