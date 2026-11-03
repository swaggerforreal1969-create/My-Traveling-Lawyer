# Task completion recovery increment — 2026-11-03

## Scope and provenance
- Parent: 585751f75de5f27daf571bb13cbed48525841e19 on engineering/real-research-task-journey-20261103, itself five commits ahead of 5206fb0ec4ce67d6b1afb6778218a442439513c3.
- Independent security Issue #1 is open and unassigned; no independent clearance. Original source migration remains 32/42. The protected ten originals and 42-file fail-closed gates are not weakened.
- Real in-process research and review lifecycle from the parent branch is retained; this increment does not claim official legal validation or public mobile deployment.

## Functionality added
- Local-only read-only reconcile_task checks current credential and matter ACL, exact task/matter association and local audit-chain consistency before reporting observed_completed, still_open or unresolved.
- observed_completed means only that current local state is completed at expected_version+1. It does NOT prove the same caller committed the write or that an independent checkpoint exists.
- Reconciliation accepts viewers for authorized read-only observation, but cannot complete a task or write an audit entry.
- AttorneyResearchWorkflow.reconcile_completion exposes this operation after uncertain task completion. The caller must not automatically replay the completion command.
- All status fields retain legal_deadlines_verified=false, court_filing_approved=false and independent_audit_verified=false.

## Tests and remaining acceptance
- Seven fictional-data unittest cases were added for no writes, completed and still-open states, viewer and cross-firm restrictions, wrong matter, revoked credentials, stale and corrupt versions, and local audit corruption.
- The existing experimental workflow runs these tests before the unchanged strict 42-file source path and immutable hash gate.
- These new tests are **published, not executed/verified** in this milestone. Do not count them as pass until complete exit 0 is observed.
- Full exact-SHA Linux CI and permitted Chromium also remain unverified. No bypass of ERR_BLOCKED_BY_ADMINISTRATOR.
- Next: execute focused plus full regression in authorized complete checkout, review a race between task read and simultaneous writer, acquire independent reviewer for ten originals, and obtain permissioned CI/browser evidence.

## Follow-up engineering verification attempt
- Checked Issue #1 again: no named reviewer or approved restricted-source migration.
- Verified d5837470def85e8079da7a118cd35cf35b72968d was the then-current head without newer commits. Opened draft PR #2 against engineering/real-research-task-journey-20261103, not main; draft remains not for merge.
- Added pull_request workflow trigger for the engineering parent, leaving all 42 required file/hash checks unchanged.
- Improved AttorneyResearchWorkflow.complete_task to distinguish a successfully committed task write from a failed subsequent read: raises RefreshUnresolved('task.complete') and never retries the task write.
- Added real-core regression case exercising failed post-commit refresh, exactly one audit task.complete event, read-only observed completion, and stale replay rejection.
- The seven existing reconciliation tests and the newly added integration case remain UNVERIFIED. The accessible environment had no private repository checkout or direct GitHub network access. GitHub commit-run lookup and combined status returned no recorded run or passing status; this does NOT show that CI succeeded or that no push run exists.
- Browser acceptance still unverified and no administrator-policy bypass attempted. Complete 42-file gate cannot pass while ten restricted originals are missing.
- Next gate: acquire permitted same-SHA runner, inspect fast test outcomes; inspect and repair demonstrated failures, then run complete regression and strict gate without shrinking its requirements. Obtain independent security Issue #1 disposition before restricted originals can be published.
