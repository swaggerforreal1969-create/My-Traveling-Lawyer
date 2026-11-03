# Isolated Matter Preparation Snapshot — Experimental

## Deliverable
- `src/matter_brief.py`: authenticated, read-only, single-matter briefing built from the existing SecureCore notes and tasks, research_evidence and authority_review records.
- `tests/test_matter_brief.py`: 12 focused tests using fictional matters, people and authority references.
- The output provides open tasks, source titles/URLs, the **latest human review assertion**, and warnings for past **user-entered** dates and research needing recheck.
- The output explicitly sets `legal_deadlines_verified=false`, `legal_authorities_verified_by_software=false`, `outbound_ai_transmission=false`; it does not calculate judicial deadlines, interpret substantive law, fetch court sources, or send anything to AI.
- Firm/matter ACLs checked for each snapshot. Token revocation and cross-firm denial covered. Evidence and reviewer digest mismatches fail closed. Read-only snapshot does not write new business audit entries. 100-entry bounds apply to each notes/tasks/research collection; oversize snapshot is rejected rather than silently truncated.

## Local evidence
- New module: **12/12 passed** in 3.562 seconds.
- Focused integration set: `tests.test_matter_brief tests.test_authority_review tests.test_secure_engine`: **40/40 passed** in 2.892 seconds.
- `python -m compileall -q src tests`: passed.
- A separate attempted module-addressed invocation including `tests.test_research_v14` produced one import error because that older test requires top-level `test_secure_http` import; the focused subset was rerun without it. Do not mistake that error as a passing result.
- New GitHub source and test files fetched and matched their locally tested Git blob hashes exactly (2/2).
- Full `unittest discover` exceeded execution limit in this cycle. The previous full-suite pass (302/302) is historical evidence only and **does not include this new module**.

## Release boundaries
- Issue #1 independent review is **open, unassigned, zero comments** at start of this cycle. No security clearance.
- Frozen original v1.4 source migration remains 32/42, exact 32/32 published blobs. No modifications to ten blocked files, main, or other engines.
- Full GitHub CI and real browser acceptance have not been verified; current immutable 42-file source gate intentionally blocks release.
- This module is **not wired into the v1.4 HTTP server or a mobile UI**. It must not be represented as an end-to-end accepted feature.
- Genuine WebAuthn, authoritative legal citation retrieval, independent audit custody and reliable hosted 24/7 AI remain future milestones.

## Next
1. Independent reviewer approval/remediation of blocked originals, no bypass.
2. Full exact-SHA source verification and Linux/browser CI.
3. Integrate this isolated briefing behind strict authenticated HTTP routes and mobile display.
4. Pursue standards-based WebAuthn and live AI with user-approved confidentiality boundaries.
