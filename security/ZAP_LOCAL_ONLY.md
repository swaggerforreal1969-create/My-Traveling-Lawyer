# $0-first security testing: Semgrep now, ZAP only on actual approved local HTTP app

## Semgrep (currently runnable)
- CI workflow: `.github/workflows/pr95-free-semgrep.yml`.
- Local rules: `security/semgrep-local.yml` covering dynamic Python execution, pickle, shell commands and dynamically built SQL.
- Run without a Semgrep login, remote rules or cloud source upload: `semgrep scan --config security/semgrep-local.yml --metrics off --disable-version-check src`.
- Restricted ten v1.4 originals are not on this branch and MUST NOT be uploaded or reconstructed to scan them.
- A finding is a lead, not an exploit. Reproduce any material issue in fictional-data tests before authorizing a fix.
- This targeted ruleset is not equivalent to a broad professional security assessment.

## OWASP ZAP: legitimate readiness, NOT a passing scan yet

ZAP is a free, open-source web security tool. It needs an actual running HTTP application.
The CURRENT authorized My Traveling Lawyer customer operator is native offline Tk; it has
no HTTP server. The original `src/secure_server.py` and browser JavaScript are among
the TEN RESTRICTED ORIGINALS NOT approved for publication. Therefore THERE IS NO
AUTHORIZED REAL HTTP APP TO ZAP-TEST in this branch.

We do not create a dummy HTTP endpoint and claim it is the product. We do not send
restricted originals or confidential records to public websites.

When a real HTTP build is separately approved and available, test it as follows:
1. Start the authorized fictional application on a disposable Ubuntu GitHub runner or
   an isolated test machine, explicitly bound ONLY to `127.0.0.1:8765`.
2. Confirm all responses use fictional data and no secrets. The target MUST be local;
   never point ZAP at any real customer, public, third-party, staging or production site.
3. With Docker available, run ONLY the short ZAP BASELINE passive scan. The baseline
   spider does make ordinary web requests; do not run an active attack/full scan.
4. Keep ZAP output private and review warnings manually. Never give production PASS
   based solely on a ZAP exit code or warnings. Shut down the app and delete all
   disposable test data at the end.

Example command, ONLY WHEN an actual approved local app is already running:
```bash
mkdir -p zap-local-results
docker run --rm --network host \
  -v "$PWD/zap-local-results:/zap/wrk:rw" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t http://127.0.0.1:8765/ -m 1 \
  -J /zap/wrk/zap-baseline.json -r /zap/wrk/zap-baseline.html
```

Never automatically run the command on the current native-only Tk app. Before
enabling a ZAP CI job, require an exact-SHA approved HTTP application, authorized
test-only launch procedure, real localhost health check, and preserved safety
scope. No Microsoft approval or expensive commercial security package is needed
for this limited engineering assessment, but independent human review, the ten
restricted originals, and 42/42 original-source acceptance remain mandatory.
