# Attorney matter workbench — functional engineering acceptance, 2026-11-03

## Scope, latest review and source protections
- Independent security review Issue #1 inspected before editing: OPEN, unassigned, zero comments. The ten blocked original v1.4 files remain restricted. Original migration is **32/42**.
- Started from verified `8942c38d1c4c6407b462f06e2ba0c6c4afcb842a` and created isolated branch `engineering/attorney-workbench-20261103`. No changes to main, `engineering/v1.4-preserved-handoff`, frozen originals, Koontcee or Diezel.
- All tests use fictional firms, lawyers, matters and task dates. No public endpoints, deployments, purchases, external legal research or AI egress.

## Substantial functional work
- New `src/attorney_workbench.py` composes the **existing real SecureCore**, not a mocked authentication fixture.
- `matters(token)`: authenticated, firm- and grant-scoped matter index with no note or matter-title disclosure and bounded results.
- `matter(token, matter_id)`: authenticated matter-scoped open task queue, user-entered date/past-due indications, real version IDs, viewer vs owner/editor permissions, no notes, and explicit NOT-VERIFIED legal-deadline/source/court flags.
- `complete(token, matter_id, task_id, expected_version)`: authenticated, matter-scoped, owner/editor-only task completion using core's atomic optimistic version check and hash-chain audit. Viewer, other-firm, missing matter, stale version and repeat completion fail closed.
- No new authority: this is in-process software, not a live mobile user interface, production WebAuthn or legal deadline calculation.

## Reproducible executed tests
- `python -m unittest tests.test_attorney_workbench -v`: **10/10 PASS** (1.205 s), real SQLite-backed SecureCore.
- `python -m compileall -q src tests`: PASS.
- Frozen v1.4 local handoff ZIP extracted to a temporary working directory, with only the two isolated new workbench files added. `python -m unittest discover -s tests -q`: **302/302 PASS in 24.691 seconds**, exit code **0**.
- The 302-run covers frozen v1.4 plus the workbench; it is NOT the unavailable full historical >500-test experimental suite.
- Verified source Git blobs match locally tested bytes:
  - `src/attorney_workbench.py` = `ef6c43c4909cd965891b22f824c287d9c3a00c5c`
  - `tests/test_attorney_workbench.py` = `b775863e78ca14f5b79ae78740ef34627cd62c04`
- Real-core tests cover owner read→complete→disappear, viewer read-only, cross-firm and ungranted same-firm denial, wrong-matter task denial, stale replay, revoked token, invalid versions, no confidential note disclosure, valid audit chain and **six competing completions yielding exactly one success**.
- Updated only this branch's `.github/workflows/experimental-regression.yml` to execute workbench compilation and focused tests before protected 42-file source verification. The required-file gate and full Linux regression remain **unchanged and fail closed**. New workflow file blob: `5faf53fcf302a553ef32420434bf0e6849b7f8d2`.

## Acceptance limitations
- New GitHub Actions run for final SHA has not been independently observed; do not treat workflow edit as passing CI. The available `fetch_commit_workflow_runs` API is PR-triggered-only and cannot verify push runs.
- Real Chromium/Playwright localhost navigation previously returned `ERR_BLOCKED_BY_ADMINISTRATOR`. **No passing Chromium acceptance**. Do not bypass that policy.
- Original-source release gate remains 32/42 pending independent reviewer approval. Maintained-library WebAuthn, independently validated official law, research/status mobile integration, independent custody and private operational 24/7 AI remain unfinished.
- The 302-test local suite is not the full current engineering checkout. Do not claim release-ready or add test counts across different worktrees.

## Next product milestone
- Connect this authorized workbench to the existing matter research-readiness projection and private script-free mobile presentation in one explicitly approved in-process adapter, then verify cross-matter data minimization and a full end-to-end task update.
- Obtain reviewer disposition on Issue #1 and an approved source checkout and Chromium runner; run exact-SHA Linux and genuine browser acceptance without bypass.
