# Integrated attorney journey — functional acceptance (2026-11-03)

## Independent review and source boundary
- Before work, GitHub security Issue #1 was **open, unassigned and had zero comments**. Frozen-original migration remains **32/42**. Ten restricted originals, main, Koontcee, Diezel and the prior engineering branch are untouched.
- Forked isolated `engineering/attorney-journey-20261103` from previously verified `22ae1e3c8660b765e4a310d3214a8f9c1db5152b`. No production, external AI, purchases or real-client data.

## Working increment
- New `src/attorney_journey.py` implements `AttorneyJourney`: authenticated matter selection via `AttorneyWorkbench.matters`; authorized task queue via `AttorneyWorkbench.matter`; a private readiness snapshot via existing `ReadinessJSON.prepare` (production default) and script-free `render_authenticated_readiness`; and version-checked `complete_and_refresh` using the existing atomic audited `SecureCore.complete_task`.
- During `open`, checks matter identity, denies claims of verified deadlines, court filing or source authenticity, renders only strict minimal JSON, reconciles task counts and user-entered past-date counts with the actual authorized queue, then repeats authorization and queue read to reject state changing during preparation.
- On completion, **never silently retries the write** when a subsequent read fails. A caller must inspect current state read-only after an uncertain refresh. No public HTTP endpoint, browser UI or new authority.
- 12 new adversarial real-core tests include owner list/open/complete/refresh, viewer read-only, unrelated firm and ungranted same-firm denial, revoked credential, wrong-matter task denial, replay, six simultaneous task completions (one success), no private title/note/IDs in HTML, false filing flag, mismatched JSON counts and no double-write on a failed post-commit refresh.
- The tests use actual SQLite-backed `SecureCore` and `AttorneyWorkbench`. **Readiness provider is a controlled fixture** in these tests, although runtime default imports the real `ReadinessJSON`. Therefore a true real research-chain integrated acceptance is **still outstanding**.

## Executed evidence
- Isolated coordinator focused suite: **12/12 PASS**, about 1.45 seconds.
- Frozen v1.4 local authorized baseline + the workbench, current script-free JSON renderer and new journey files: `python -m unittest discover -s tests -q` -> **339/339 PASS in 31.455 seconds**, exit **0**. `python -m compileall -q src tests` -> PASS.
- This 339-test run is **NOT** the unavailable full historical 544+ experimental suite; the complete current research-projection stack is not present in this isolated local checkout.
- GitHub fetched both published new files and matched exact tested Git blobs:
  - `src/attorney_journey.py` = `0cc8e0401ab0463f8eb00a7e3d657bad0324dad9`
  - `tests/test_attorney_journey.py` = `c6b4f7484d5e8af3712df0f77cb94a1559c5ef81`
- The isolated branch's `.github/workflows/experimental-regression.yml` now adds the journey tests before the unchanged required-originals gate. Full original 42-file verification remains **fail-closed**.

## NOT accepted and next measurable priority
- No genuine Chromium acceptance: previous localhost Chromium failed `ERR_BLOCKED_BY_ADMINISTRATOR`; no administrator bypass.
- No independently observed passing exact-SHA Linux GitHub Actions run. The connector's available commit-run lookup is PR-triggered-only and cannot establish all push-run results.
- Issue #1 reviewer approval and ten restricted original uploads remain blocked, original migration 32/42.
- Real WebAuthn, independently authenticated official legal sources and confidential 24/7 operational AI are unfinished.
- Next: assemble an authorized current engineering checkout and replace the controlled readiness fixture with a real source-integrity, observation and second-review workflow; verify end-to-end matter/task/research snapshot then run exactly one complete Linux gate and authorized Chromium.
