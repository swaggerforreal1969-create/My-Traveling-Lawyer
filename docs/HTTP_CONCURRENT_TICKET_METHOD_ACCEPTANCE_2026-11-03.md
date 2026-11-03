# HTTP single-use concurrency and method boundary — acceptance (2026-11-03)

## Gate status before work
- Independent security review Issue #1: open, unassigned, zero comments. No permission to publish the ten blocked original v1.4 files. Migration remains **32/42**.
- Resumed from verified `729e536e4ab195813e9fe9e2b68ddb419135e41e`; only separately authored experimental HTTP handler and tests were edited. No merge or deployment. Frozen original sources, `main`, Koontcee and Diezel remain untouched.

## Functional change
- `LoopbackReadinessHandler.do_GET` now rejects any request that does not declare exactly HTTP/1.1 before credential/ticket use; inherited HTTP/1.0 behavior must not lead to an accepted preview.
- Explicitly rejects PATCH, TRACE and CONNECT with HTTP 405, empty body and Connection: close, rather than delegating to the inherited default unsupported-method response.
- Six simultaneous real HTTP GET requests reusing a single legitimately issued matter-bound ticket must yield exactly **one 200 and five 403**, and subsequent reuse returns 403.
- Rejection of HTTP/1.0 and unsupported methods does **not** consume an authorized preview ticket.
- This remains a **localhost-only, in-process-ticket** experimental adapter. It is not reviewed production transport or WebAuthn.

## Executed evidence
- `python -m unittest tests.test_readiness_loopback_http -q`: **28/28 PASS in 15.681 seconds** (three new tests).
- `python -m unittest discover -s tests -v`: log reported **512/512 PASS in 36.311 seconds**. The containing execution tool/wrapper subsequently timed out; its process exit was not successfully confirmed. Do not misstate clean CI completion.
- `python -m compileall -q src tests`: PASS, exit code 0.
- Published GitHub blobs match locally tested Git hashes:
  - `src/readiness_loopback_http.py`: `1c0e422a7e5ded410805f23f16198774eb4ec2eb`
  - `tests/test_readiness_loopback_http.py`: `e9e2bb140b8928a60f8c262e7369dcdf73bbf773`

## Genuine Chromium attempt — blocked, NOT accepted
- Executed unchanged committed `tests/acceptance_chromium_readiness.py` using real Chromium/Playwright on fictional localhost data and a real loopback socket.
- Navigation failed with `Page.goto: net::ERR_BLOCKED_BY_ADMINISTRATOR`; the script exited with code **1**. Browser content, screenshots and full acceptance were not achieved. No administrator-control bypass attempted.
- GitHub exact-SHA Linux CI and authenticated browser acceptance remain unverified. No successful workflow run was associated with the starting SHA, and GitHub actions were not triggered during this cycle.

## Open release requirements
- Obtain named independent security reviewer decision in Issue #1; do not upload ten blocked original paths until approved.
- Upon authorization, complete all 42 frozen SHA-256 fingerprints, exact-SHA Linux CI, and genuinely authenticated Chromium acceptance in a supported runner.
- Maintained-library WebAuthn ceremonies, independently authenticated official legal sources and operational confidential 24/7 AI remain unfinished.
- Fictional data only. No external AI egress, client data, production access or purchases.
