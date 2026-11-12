# Diesel controlled code-writing agent — isolation and permissions

**Pilot contract:** This is a real GitHub-hosted code-writing **deterministic worker**, not a generative AI developer. It can make one bounded, testable application code change, commit it to its own `diesel/**` branch, and leave an audit record. It cannot accept arbitrary instructions or invent code changes.

**Queue:** `docs/diesel-agent-queue.json`, one allowlisted task: add plain-language Practice Help to fictional Windows home screen. Maximum one change attempt. No client data, model API, credentials, new recurring timer, or external data.

**Isolation:** Checkout exact SHA of `diesel/mtl-windows-agent-20261112`. Refuse wrong repository, event, branch, dirty working tree, source drift, other file paths, protected refs, or changing more than the two allowlisted paths. Only `tools/windows_fictional_gui.py` and a targeted `tests/test_windows_practice_help.py` may be touched. Test before commit, confirm remote exact SHA after isolated-branch push. This push uses GitHub Actions token and does **not** trigger a second CI workflow; do not claim external exact-SHA CI of the resulting commit.

**Verification:** 2 new focused help tests plus previously available 3 Windows build and 3 Store preparation tests. The on-run code verifies source after mutation; a new workflow at the resulting SHA would be needed for independent exact-SHA acceptance. No protected merge or delivery.

**CI costs:** The branch name `diesel/**` deliberately avoids pre-existing `experimental-regression.yml` push branch glob `engineering/**`. The prior broad runner is unmodified. This workflow triggers only on a push that modifies the queue file in this exact isolated branch; no cron, polling, or live loop.

**Permission limits:** Only `contents: write` for the job-scoped GitHub token to push the isolated branch. GitHub workflow permissions cannot themselves narrowly scope write access to a single branch, so application guard plus separate existing branch protection reduce risk; mandatory organization-level enforcement of that restriction remains unverified. Review rule/security hardening is required before any general agent receives write access.

**Next unsatisfied requirement:** A genuine independent AI developer needs an authorized persistent coding-agent service, an approved account/token and verified $0 billing/usage limits. None is provisioned here, so do not claim autonomous generative coding or 24/7 persistent operations. Recurrence remains disabled, as demanded by the approval gate. Stage 1 production NO-GO.
