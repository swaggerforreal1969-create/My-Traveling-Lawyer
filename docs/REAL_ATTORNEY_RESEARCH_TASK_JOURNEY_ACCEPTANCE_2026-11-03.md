# Real attorney research, human review and task journey — functional acceptance (2026-11-03)

## Approval and branch boundary
- Checked independent security review Issue #1 at start: **OPEN, unassigned, 0 comments**. Ten restricted original v1.4 files remain unchanged and unapproved. Original migration remains **32/42**.
- Checked source branch `engineering/attorney-journey-20261103`: no newer commits over `5206fb0ec4ce67d6b1afb6778218a442439513c3`; no PR-scoped workflow run available.
- Created isolated branch `engineering/real-research-task-journey-20261103` from that commit. No changes to main, frozen archive, handoff branch, Koontcee, Diezel, production authority or deployment. Only fictional inputs, no purchases or AI egress.

## Substantial new working functionality
- New `src/attorney_research_workflow.py`: one in-process local workflow API that composes the **actual**, separately authenticated `AttorneyJourney`, `ResearchEvidence`, `SourceObservation`, and `SecondSourceReview` services. Its `open` path uses default real `ReadinessJSON`, `MatterReadiness`, `SourceReleaseProjection`, `MatterBrief`, and strict `render_authenticated_readiness` mobile renderer — **not a synthetic readiness provider**.
- Authorized attorney can: list accessible matters → view work queue/private minimal readiness → add a fictional source → manually observe it → have a *different authorized account* independently review the observation → receive revised procedural status in private HTML → complete a version-checked task → view the refreshed queue.
- Each write delegates to the existing database-backed authorization, digest checks, concurrency/audit semantics. Returned `WorkflowResult` includes the committed new ID and refreshed minimized snapshot. If the write returns successfully but refresh fails, `RefreshUnresolved` alerts the caller to **reopen read-only**, rather than automatically replaying a potentially committed write.
- Human second review stays **procedural only**; the system always reports unverified official legal status, court-deadline and court-filing approval. No new internet, public HTTP, WebAuthn or AI authority.

## Reproducible executed adversarial acceptance
- New `tests/test_attorney_research_workflow.py`: **5/5** passed with actual SQLite-backed core and the *real* research/observation/second-review/readiness chain.
- New `tests/test_real_attorney_research_journey.py`: **6/6** passed independently using the default (non-injected) `AttorneyJourney` readiness service.
- Verified scenarios: original source pending first observation → second observation review required → second distinct human account corroborates procedural review → private HTML reflects 'two people reviewed; law unverified' → task completion → count goes to zero; subsequent new observation invalidates previous second review; same-author second review denied; viewer cannot mutate; cross-firm and wrong-matter access denied; revoked token denied; stale/replayed task completion denied; corrupt observation or second-review database records fail closed; post-commit refresh failure yields explicit `RefreshUnresolved` with only one source write and one audit event.
- Reconstructed the needed experimental **unchanged modules from GitHub through the approved connector** into a local test-only directory and verified their exact `git hash-object` identities: core `4327571baaed2daf2b2211981a7fed89cc93e582`; research notebook `6f317e788bc5fcdb3000ccc0f4b7c837b03942bb`; source observation `b5da8b06029f32934f93716846bfd7c042b3c396`; independent second review `9599de15c2eddaee9844c47ed837d329a92b4c73`; release projection `625514c47e0e90251289c98e23f2caf0924277f0`; matter brief `4db60be99d578eee552f6613e4200e5218f3c635`; matter readiness `07bbfba4299b2f3b56d317660124b61ba3f5c19c`; private JSON `bf4f4ce85660310ae7bdeac5020ed8c4b47a197f`; mobile gateway `dd482f092485322e1df169f2db341664c390e232`; mobile matter renderer `1e9584d19aed554c5c91fd5c90ad522993383a75`; authenticated workbench `ef6c43c4909cd965891b22f824c287d9c3a00c5c`; existing journey `0cc8e0401ab0463f8eb00a7e3d657bad0324dad9`; strict private HTML renderer `287be91e70ac841dec4748696f2468b8acb9a2e8`.
- Final **frozen-v1.4 local baseline + available previously published workbench/journey/renderer + real research modules + 11 new tests**: `python -m unittest discover -s tests -v` → **350/350 PASS in 30.960 seconds, exit code 0**; `python -m compileall -q src tests` → PASS.
- An earlier quiet-mode regression wrapper timed out without final output; **not counted**. Full verbose run ended with `Ran 350 tests in 30.960s\nOK`, clean zero exit.
- New files published and GitHub fetched identical tested Git blobs:
  - `src/attorney_research_workflow.py`: `b6a7083557478b602c4000e801291a6a24e42268`.
  - `tests/test_attorney_research_workflow.py`: `4e0ef5aecb395ab44bd7537350fa289eca154da0`.
  - `tests/test_real_attorney_research_journey.py`: `247ba389ac1d9f947c75ee8714ee9b21846d2a68`.
- Updated only isolated branch's existing experimental GitHub Actions workflow, inserting the two real research test suites into the fast pre-release gate. Preserved required 42-source-file check, immutable source hashes and final full Linux regression. Workflow Git blob: `aaf762043745e7c8f7b8e26f1e4d1b84bd736806`.

## Explicit limitations and next gates
- The 350-test run verifies an authorized test-only assembled **frozen baseline and selected current modules**. It is NOT the entire >500-test experimental repository suite and it is not GitHub CI.
- The GitHub connector's `fetch_commit_workflow_runs` is scoped to pull-request-triggered runs and cannot verify push-run success. No successful exact-SHA Linux run has been independently checked for this branch.
- Chromium browser acceptance remains **NOT PASSED**, previously blocked by `ERR_BLOCKED_BY_ADMINISTRATOR`; no bypass. This in-process workflow is not a deployed mobile frontend and has no HTTP ticket issuance.
- Security Issue #1 reviewer disposition is missing; original source migration 32/42 and all ten restricted originals remain blocked.
- Genuine maintained-library WebAuthn, independently authenticated official law/treatment/currency, independent rollback-resistant custody, and private production 24/7 AI remain unfinished.
- Next: obtain named security review and authorized complete checkout; run true full exact-SHA Linux CI and permitted Chromium HTML/JSON acceptance; subsequently connect the validated in-process journey to an explicitly approved mobile HTTP UX with one-use ticket and revocation checks. Preserve all policy boundaries.
