# DIESEL repository workflow efficiency rollout (review-first)

Scope: audit and improve **all 12 GitHub Actions workflow definitions** on isolated `diesel/mtl-repository-efficiency-20261112`, without merging protected source. Preserve every existing mandatory security and customer acceptance test.

Changes: add ref-scoped latest-commit concurrency to workflows lacking it (no new runners); for broad `engineering/**` regression, skip **documentation-only** pushes while retaining application, tests, and workflow-code triggers. Security PR110 exact-SHA jobs fail quickly with explicit **BLOCKED_REQUIRED_RESTRICTED_SOURCE** if `src/secure_server.py` is unavailable. This is a failure, not a PASS, removal of the test, or substitute for authorized source recovery. Do not publish any restricted originals.

Safety: no schedules, no new GitHub-paid runner sizes, only preexisting standard hosted `ubuntu-latest` and `windows-latest`. Retain checks and permissions; the exception is existing isolated code-writing workflow's `contents: write` which must never be expanded outside a reviewed, bounded task. Add a six-test repository-wide workflow policy audit. The staged efficiency workflow tests config on cheap Linux preflight, conditionally uses Windows on real application code changes, and must stay nonproduction.

Rollout status: isolated branch demonstration is not a merge into main or PR #110. A reviewable draft PR is the next safe integration mechanism. Changing historical workflow definitions on a new branch does not alter already-running workflows on their original branches. Future adoption must be reviewed for each security lane before merge.

Functional requirement still unproven: full backup+restore controls inside the frozen EXE. Earlier native Tk real backend journey was verified (Actions 43329708911), and exact-SHA packaged EXE startup was verified. Do not collapse those two separate facts into frozen EXE journey acceptance.

Production NO-GO. No real data, spending, restricted source publication, unsigned distribution, permissions escalation or security bypass.
