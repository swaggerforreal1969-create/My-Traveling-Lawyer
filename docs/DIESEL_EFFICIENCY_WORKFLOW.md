# Diesel Efficiency-by-Design — GitHub engineering pipeline

## Measured baseline (2026-11-12)
GitHub Actions first 100 recent runs inspected, 26 from 2026-11-12 UTC. On the *isolated* `diesel/**` branches, 8 runs: **5 success / 3 failure**. In the earlier `engineering/diesel-contained-...` pilot, broad `experimental-regression.yml` ran redundantly on `engineering/**`: 5 total runs (1 success / 2 fail / 2 cancelled) including three unrelated broad regression jobs. Other security branch: 12 runs, 0 successes (8 failures/4 cancelled); the test `tests/test_secure_http.py` requires absent protected `src/secure_server.py`, and CI reported ModuleNotFoundError. The protected ten original files must not be published or fabricated. These are *run outcomes*, not quality or true billed-minutes comparisons.

## Applied architecture
One scoped workflow on distinct `diesel/mtl-efficient-pipeline-20261112` branch, outside legacy `engineering/**` triggers. Stage 1: cheap Ubuntu runner with pure-Python seven-test rule validator, exact-SHA diff against protected recovery baseline and authorized Issue #111-derived task queue; emits inspectable status. Stage 2: hosted Windows runner is **conditional** upon actually changed Windows customer code. Infrastructure-only commit reuses earlier customer-acceptance evidence without rerunning it. A missing restricted HTTP component is explicitly **BLOCKED** rather than PASS; this does not bypass an independent release gate.

No new self-hosted runner or larger billed GitHub runner added: existing GitHub-hosted `ubuntu-latest` and `windows-latest` are sufficient for scoped work; new capacity requires independent free-tier/billing verification. No persistent loop, cron, external credentials, autonomous deployment, branch protection changes, protected merge, signing or customer distribution.

## Future optimizations pending separate verification
(1) A repo-wide workflow dispatch policy for all *nonprotected* branches; (2) restrictive branch rules and read-only/least-privilege runner tokens; (3) checked reusable exact-SHA artifact handoff; (4) frozen-EXE full backup/restore control interaction, not falsely equated with the separately accepted source-level Tk journey; (5) separate authorized independent security and signing gate. Do not rewrite historical mandatory security workflows to make red jobs green. Broad workflow redesign should be reviewed before altering protected PR #110 or release work.

## What success proves
If Ubuntu CI succeeds with Windows job skipped, the efficiency pipeline correctly avoids a needless native rebuild on infrastructure-only edits. This is proof of orchestration, not proof of reduced spend, higher coding productivity, AI background persistence, release acceptance, or signed customer readiness.
