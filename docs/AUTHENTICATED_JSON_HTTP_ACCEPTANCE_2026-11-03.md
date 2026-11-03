# Authenticated localhost JSON matter readiness integration — acceptance (2026-11-03)

## Permission and release boundary
- At startup, GitHub independent security-review Issue #1 was **open, unassigned, zero comments**; no authorization to upload or modify the ten blocked frozen originals. Original migration remains **32/42**.
- Resumed from verified `abb95bf6239f98a607e12972cb44a73fe816966f` on `engineering/v1.4-preserved-handoff`. Two **new** isolated files authored; frozen originals, `main`, Koontcee and Diezel untouched.

## Functional feature
- `src/readiness_json_http.py` adds `LoopbackJSONReadinessServer`, a local-only adaptation of the existing authenticated `LoopbackReadinessServer`. The server uses the existing exact `GET /v1/matters/{matter_id}/readiness` route but fixes the representation **at construction** to `ReadinessJSON`; no user-controlled format negotiation.
- Reuses the exact working HTTP security protections: literal 127.0.0.1 binding, valid SecureCore bearer, atomic single-use matter-scoped ticket, duplicate/unsafe header and Host denial, method denial, connection close, bounded worker pool, idle timeout, empty no-store failure and no HTTP ticket-minting endpoint.
- JSON response contains only bounded procedural counts and explicit false legal-source/court-filing/AI assertions. No matter/evidence identifiers, titles, notes, excerpts or source URLs; no external calls or AI egress.
- This is **not** a reviewed production service or public endpoint. Caller must issue ticket in-process; the new class does not deploy or start a server on import.

## Executed evidence
- `python -m unittest tests.test_readiness_json_http -q` — **10/10 PASS in 5.648 seconds**. Real localhost HTTP responses tested with fictional firms and matters.
- First full quiet-run wrapper timed out without a result and is not counted.
- `python -m unittest discover -s tests -v` — **544/544 PASS in 49.335 seconds, exit code 0**, verified from separately monitored complete log and recorded exit file.
- `python -m compileall -q src tests` PASS.
- Both newly published GitHub blobs were fetched and match tested source hashes:
  - `src/readiness_json_http.py` = `3abd942cfe324622afe806719dd44850b7515c43`.
  - `tests/test_readiness_json_http.py` = `8c2bcb90130317299a1534dcecdf40d19d6aabb0`.
- Tests cover proper JSON headers and no private data, replay denial, wrong matter not burning ticket, cross-firm denial, revoked credential, unsafe Origin, source tampering denying and burning ticket, unsafe Host denial, disallowed POST and strictly loopback binding.

## Unfinished gates
- Original 42-file migration incomplete at 32/42 pending independent reviewer decision, Issue #1.
- No exact-SHA successful GitHub Linux CI verified. Genuine Chromium previously failed `net::ERR_BLOCKED_BY_ADMINISTRATOR` on the local URL, and has **not** passed in this milestone. Do not bypass that policy.
- Maintained-library WebAuthn, independently verified current official legal sources, independent custody and deployed confidential 24/7 AI remain unfinished.
- The localhost JSON HTTP response is not approved production hosting or a mobile UI; formal transport review, real browser acceptance and authorized deployment are still needed.

## Next
1. Name and obtain a disposition from independent reviewer on Issue #1.
2. After approval, complete all 42 frozen source hashes; run full same-commit Linux CI and genuine Chromium acceptance on authorized runner; retain pass/fail artifacts.
3. Extend the acceptance runner for JSON response privacy, cache headers, revoked/cross-matter denial, ticket replay and source tampering without bypassing browser policy.
4. Continue substantive isolated security/product progress with fictional data only.
