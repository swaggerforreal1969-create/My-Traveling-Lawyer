"""Conservative classification: an unrelated event never proves an MTL defect."""
import json,sys
from pathlib import Path
KNOWN={"0xc0e90002":"Windows reputation or signing trust denial","0xc0000135":"Missing Windows DLL","0xc000007b":"Invalid executable or DLL format","0xc0000005":"Process access violation","0x80070005":"Windows access denied"}
def classify(code,event_id=None,exact_path=False):
    code=str(code).strip().lower() if code is not None else None
    if not exact_path: return {"verdict":"UNRESOLVED","reason":"No exact MTL executable correlation"}
    if event_id==3077 and code=="0xc0e90002": return {"verdict":"VERIFIED_POLICY_BLOCK","reason":KNOWN[code]}
    if code in KNOWN: return {"verdict":"REQUIRES_INVESTIGATION","reason":KNOWN[code]}
    return {"verdict":"UNRESOLVED","reason":"Unknown or missing status"}
if __name__=="__main__":
    d=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    print(json.dumps({"sha":d["git_sha"],"authenticode":d["authenticode"],"window_opened":d["window_opened"],"smart_app_control":"NOT_PROVEN_ON_GITHUB_RUNNER","correlated_events":[classify(e.get("status"),e.get("id"),e.get("exact_path")) for e in d.get("events",[])]},indent=2))
