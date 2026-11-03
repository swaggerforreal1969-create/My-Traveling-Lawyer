# HTTP parser-error fail-closed acceptance — 2026-11-03

## Starting security boundary
- Independent review GitHub Issue #1 checked before modifications: **open, unassigned, zero comments**. Ten blocked v1.4 original files remain untouched; immutable original migration **32/42**.
- Previous verified GitHub commit: `ae600b4e36fc81af79c1a7dd75f38b33ca74a09c`.
- Changes strictly limited to separately authored experimental localhost HTTP handler and real-socket test file; no change to `main`, frozen archives, Koontcee, Diezel, production access or deployments.

## Defect and repair
- Python `BaseHTTPRequestHandler` responds to malformed request lines, oversized request targets and unsupported HTTP versions **before the application-level `do_GET` checks**. Its inherited error handling may emit an HTML error page or suppress HTTP output entirely due to a parsed `HTTP/0.9` request_version.
- Override `send_error` to force a bounded HTTP/1.1 error response using the same fail-closed `_deny` routine: no response body; `Cache-Control: no-store`, CSP/frame denial, `Content-Length: 0`, `Connection: close`. No request details, bearer credentials or ticket values appear in the response.
- No preview ticket is consumed on malformed parser requests.
- Three new raw-socket adversarial tests: malformed request line, oversized request target (414), unsupported HTTP/9.9 (505), all followed by a fresh authorized GET using the original unconsumed ticket. This is an experimental loopback HTTP boundary, not independently reviewed production ingress.

## Execution evidence
- Initial three-test run found 2 failures: malformed line and HTTP/9.9 suppressed the response under inherited request_version. Repaired by explicitly using HTTP/1.1 for parser-level error output; **3/3 new tests PASS**.
- First full quiet-run wrapper timed out without a final test summary; it was not counted. Subsequently verbose regression output completed with **518/518 PASS in 40.902 seconds**. The wrapper itself timed out before surfacing the complete output, but the saved log concluded `Ran 518 tests in 40.902s\nOK`.
- `python -m compileall -q src tests` PASS, exit code 0.
- Source/test Git blobs match tested local hashes:
  - `src/readiness_loopback_http.py`: `d502df93c32478799353a08e0523d1ec9abcef9f`
  - `tests/test_readiness_loopback_http.py`: `ed2f148454a0aac098b95f99f90086a5bb5db0e5`

## Outstanding release gates
- Independent reviewer disposition on Issue #1 missing. Original migration remains **32/42**.
- No verified GitHub exact-SHA Linux CI or authentic Chromium acceptance. Previous real Chromium navigation failed `ERR_BLOCKED_BY_ADMINISTRATOR`; do NOT bypass the administrator.
- Maintained-library WebAuthn, independent legal-source authenticity and treatment verification, external custody and operational 24/7 confidential AI remain incomplete.
- Only fictional data. No spending, real-client transmissions, provider AI egress or production deployment.

## Next milestone
1. Obtain independent security-review decision with named reviewer and recorded scope.
2. Once authorized, complete original 42/42 SHA-256 checks, then exact-SHA Linux CI and authorized same-commit Chromium acceptance with 200/403, replay, cross-firm and privacy checks.
3. While blocked, prioritize real, isolated attorney workflow improvements rather than cosmetic testing or repeated unauthorized browser attempts.
