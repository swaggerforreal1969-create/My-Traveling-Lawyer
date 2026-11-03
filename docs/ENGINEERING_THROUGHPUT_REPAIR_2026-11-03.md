# Engineering throughput repair — 2026-11-03

## Measured blockers
- Prior checkpoint: `fb1c558d66284ba96f06de4c74d7508986830227`; branch is 140 commits ahead of main with 105 changed files as examined at start.
- Issue #1: open, unassigned, no reviewer comments. Ten original frozen v1.4 files remain blocked; original migration 32/42.
- Existing `.github/workflows/experimental-regression.yml` placed the 42-file required-source check before any Python test. The protected source gate intentionally fails until approved, so CI could not run experimental tests in that order.
- GitHub connector `fetch_commit_workflow_runs` returns **pull-request-triggered workflow runs only**. A returned empty list does NOT establish absence of push-triggered CI; do not assert broad no-CI from that API alone. Commit combined statuses were empty when examined.
- Repeated temporary local reconstructions, blocked Chromium navigation and three-test security-only increments yielded limited product-integration progress.

## Actual authorized fix
- Updated the *existing* engineering-branch workflow; left its required 42-file source gate, immutable hash verifier and full Linux regression commands intact.
- Added *before* the source gate a lightweight independent functional gate:
  `python -m py_compile src/json_mobile_document.py tests/test_json_mobile_document.py`
  `python -m unittest discover -s tests -p test_json_mobile_document.py -q`
- Added workflow concurrency cancellation for superseded in-flight runs on the same branch, without bypassing any source or release integrity check.
- Exact new workflow Git blob fetched from GitHub: `34f0e38d6d617f3c3c33c2239667efb28ea27d4d`. Fast smoke step precedes unchanged 42-file fail-closed gate.
- Ran those exact two fast-gate commands locally against GitHub-identical renderer source/test blobs: **25/25 PASS**, process exit **0**. Code blob IDs: `287be91e70ac841dec4748696f2468b8acb9a2e8` and `85fae96ba1084ed30b0766a3e2601303aa85537e`.

## Important limitations
- Publishing the workflow does NOT prove GitHub Actions executed or passed for the commit. Verify live run URL and logs separately before claiming GitHub CI.
- This is a *smoke test and workflow efficiency repair*, not completion of missing full regression, 42-file integrity, production WebAuthn, browser or independently verified official legal sources.
- Chromium localhost was previously blocked by administrator policy. No bypass or fresh passing acceptance.
- No original frozen file changes, main merge, deployment, purchases or external AI egress.

## New engineering operating rule
1. Stop repetitive three-test incremental spins when they don't materially advance a working end-to-end attorney feature.
2. Group substantive feature work with focused tests, then run a single final complete gate on the final exact SHA when approved source is present.
3. Keep lightweight experimental smoke separate from protected full release validation; never mark the latter green when 32/42.
4. Reuse current source manifests, acceptance scripts and previously verified unchanged evidence instead of rebuilding a full local checkout every turn.
5. Require a named independent reviewer, documented source disposition and authorized Chromium runner for release. Until then prioritize useful isolated product functionality.

## Next dependency
- Assign a qualified independent reviewer to Issue #1 and record a decision. Separately verify the new workflow's exact SHA on a GitHub Actions run; connector PR-only workflow-run lookup cannot substitute for push-run evidence.
