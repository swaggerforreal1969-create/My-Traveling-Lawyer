# Loopback HTTP mobile readiness — verified local socket acceptance, blocked Chromium (2026-11-03)

## Deliverable
- `src/readiness_loopback_http.py` introduces an **explicitly started, loopback-only** Python HTTP adapter. It binds only `127.0.0.1` (never external interfaces), and offers `GET /v1/matters/{matter_id}/readiness` with:
  - An existing valid `SecureCore` credential in the Authorization bearer header.
  - A separate `X-Preview-Ticket` issued **in-process** using the existing single-use, matter-bound PreviewSessionBroker. There is no anonymous ticket issuance endpoint.
  - Fresh credential and matter ACL checks at consumption, then real `MobileReadinessView.prepare()` and fail-closed integrity validation.
  - Exact Host header validation; rejection of Origin, Referer, Cookie, transfer-encoding or request bodies, URL query strings, and non-GET methods.
  - Empty denial bodies, no-store security headers, and suppressed request logs. Auth credentials and preview tickets never enter URLs, logs or persistent plaintext token storage.
- This is an experimental localhost HTTP boundary using fictional data, **not** a reviewed production HTTP server, network service or supported remote mobile app.

## Actual tests
- Initial real HTTP-focused run failed 3 tests due to missing initialization of optional research tables. Fixed initialization order within the new module; reran **16/16 focused tests PASS** in 9.271s.
- Full local v1.4 + all isolated experimental modules and tests `python -m unittest discover -s tests -q` → **500/500 PASS in 28.929s**.
- `python -m compileall -q src tests` PASS.
- Tested functional 200 rendering, exact response security headers, 403 replay, revocation, wrong matter and cross-firm denial, unauthorized token, unsafe Host/Origin/Referer/Cookie, attempted URL credential leakage, rejected POST/PUT/DELETE/HEAD/OPTIONS and binding restricted to loopback.
- All 3 GitHub source/test blobs matched exact locally tested `git hash-object`:
  - `src/readiness_loopback_http.py`: `6f3d0f3a216c1d9e26903d20d08c756249e0892b`
  - `tests/test_readiness_loopback_http.py`: `42644345af2f359627dc3d7334dbbe1df06d372f`
  - `tests/acceptance_chromium_readiness.py`: `86c8b683b1b368ef8d964814057431bde5dae339`

## Genuine Chromium attempted — blocked, not passing
- Installed real Chromium 144.0.7559.96 launched with Playwright, using a 390 × 844 mobile viewport, a real local server and fictional matter data.
- Playwright `page.goto(http://127.0.0.1:<random-port>/v1/matters/<matter>/readiness)` failed **`net::ERR_BLOCKED_BY_ADMINISTRATOR`** before page-content assertions could run.
- Do **not** mark browser acceptance successful. No alternate transport or bypass of the administrator restriction was attempted. The executable same-source Chromium acceptance script is committed for an authorized runner.
- No successful GitHub exact-SHA Linux CI exists for this branch.

## Release boundaries
- GitHub Issue #1: **open, unassigned, zero comments** at this cycle's check. No independent approval for ten previously blocked original v1.4 files. Frozen-source migration remains **32/42**; no bypass or changes to blocked originals.
- `main`, original archives, Koontcee and Diezel are unchanged.
- Genuine maintained-library WebAuthn, independent official legal source authentication, independent custody, operational 24/7 AI and production authorization review remain unfinished.
- Only fictional data; no external AI egress, purchases or deployment.

## Next gate
1. Obtain independent security review disposition on Issue #1; preserve all ten blocked files until explicitly approved.
2. Once authorized, finish 42/42 original SHA-256 and exact-SHA GitHub Linux/Chromium gates.
3. Run `PYTHONPATH=. python tests/acceptance_chromium_readiness.py` in an **authorized** runner that permits Chromium localhost, verify mobile rendering, 403 replay and cross-matter denial.
4. Add maintained-library WebAuthn and independently verified official legal-source provenance on an authorized network/dependency environment.
