# Loopback HTTP connection lifetime and pipeline-denial acceptance — 2026-11-03

## Purpose and release gate
- GitHub Issue #1 checked at start: **open**, unassigned, zero reviewer comments. No independent approval to modify/publish the ten frozen original v1.4 files. Original migration remains **32/42**.
- Prior checkpoint: `7d988cb6fca8292dcaa926de9af4cad04dae5637`. Only previously published experimental `src/readiness_loopback_http.py` and `tests/test_readiness_loopback_http.py` were changed. Frozen originals, main, Koontcee and Diezel preserved.

## Engineering change
- Previous handler denied suspicious headers with 403 but left HTTP/1.1 connections eligible for reuse even when unread request bytes remained. A parser could attempt to interpret a rejected POST body or pipelined bytes as an additional request.
- `_deny` now sets `close_connection=True` and emits `Connection: close` for every rejection (including 403, 404, 405). A successful preview also emits `Connection: close` and closes after the one authorized response.
- No new token issuance endpoint, no public binding, no external AI/provider egress, and no change to credential or single-use ticket requirements.
- **Three raw TCP adversarial tests** exercise duplicate Authorization header followed by a pipelined valid GET, rejected POST body followed by a valid GET, and two valid pipelined GET requests. All require exactly one HTTP response and a closed socket. Unused tickets remain usable through a fresh authorized request, while consumed tickets are rejected.
- This reduces a specific keep-alive/pipeline ambiguity in a localhost-only experimental HTTP server; it is **not** a security-reviewed production ingress.

## Executed evidence
- `python -m unittest tests.test_readiness_loopback_http -q` → **25/25 PASS in 14.025s**.
- `python -m unittest discover -s tests -v` → **509/509 PASS in 35.186s** (the complete 509-test successful unittest summary was retained in the local log; the surrounding command wrapper subsequently reported timeout; this is a wrapper caveat, not a claimed clean runner exit).
- `python -m compileall -q src tests` → PASS, exit 0.
- Exact tested code Git blobs:
  - `src/readiness_loopback_http.py`: `afb255296d3cc603af9ce6803f87b869c3849038`
  - `tests/test_readiness_loopback_http.py`: `7d2a4983e4a2536bc4588bd09b2522818c7d3cfd`

## Browser and CI status — explicitly NOT accepted
- Existing committed `tests/acceptance_chromium_readiness.py` tried genuine Chromium and received `net::ERR_BLOCKED_BY_ADMINISTRATOR` when navigating localhost. **No passing Chromium result**; do not bypass policy.
- No successful exact-SHA Linux CI established for this branch; ten original source paths remain blocked and integrity gate fails closed.
- Genuine WebAuthn, independently authenticated legal research, independent custody and operational 24/7 AI remain unfinished.

## Next
1. Obtain an independent reviewer decision in Issue #1.
2. Use an authorized GitHub Actions/runner environment to run exact-SHA tests and genuine Chromium acceptance; do not weaken original-source gate. Preserve screenshots or failure traces.
3. If approved, publish the ten originals unchanged through authorized channels and verify all 42 frozen SHA-256 fingerprints, followed by complete Linux/Chromium checks.
4. Keep implementing real, testable confidentiality controls while dependencies remain unavailable.
