# My Traveling Lawyer — independent security audit and release unblock handoff

**Status:** REQUEST FOR INDEPENDENT REVIEW. No reviewer appointed, no security approval, no release clearance. This document is not a substitute for an audit.

**Frozen checkpoint:** `b8601d9b9103422a151129784069bdb03bf29381` (draft PR #26); hosted CI `41730501789`. 170/170 focused Linux acceptance tests passed including 14 durable-fence tests and 11 Xvfb native GUI tests. Overall CI **FAILS** the mandatory 42-file source gate. Full-tree diagnostic attempted 510 tests, reported 6 missing `src.secure_server` imports and 11 expected no-display skips. PR CI may evaluate the pull-request merge checkout, not necessarily exact source SHA: independent exact-checkout verification is required.

## A. External human reviewer required — not assigned

An independent reviewer must be a named security engineer with access **through approved channels** to the preserved v1.4 archive, immutable original manifest and permitted test environment. No tool or AI should invent independence, self-approve, or publish restricted originals. Record reviewer identity, date, methods, findings, and explicit accept/reject for each file. Evaluate conflicts of interest.

Scope: `My-Travelling-Lawyer-OPEN-ME.html`, `src/__init__.py`, `src/app.js`, `src/index.html`, `src/secure_app.js`, `src/secure_index.html`, `src/secure_server.py`, `tests/test_custody_v11.py`, `tests/test_engine.py`, `tests/test_milestone_v06.py`. Audit HTTP authorization, tokens/credential revocation, multi-tenant confidentiality, DOM injection, origin/host/CSP, client secrets, custody checkpoint verification, dependency integrity, and test validity. Scrutinize demo/legacy HTTP boundaries: no production activation.

## B. Independent rollback-resistant custody is NOT implemented

Existing `src/durable_local_write_fence.py` and `src/local_operator_gui.py` use local SQLite storage, a local marker, a salted review fingerprint and actor-authorized local reconciliation. They **cannot** detect a coordinated rollback of main DB and sidecar, cannot establish durable identity independently of local storage, and cannot certify incident resolution if the entire local witness disappears.

Required next integration: externally pinned, independently administered, authenticated append-only checkpoint authority with **atomic, non-replayable admission**, monotonic sequence, unique reservation version, signed response/provenance and independently verified readback. The write path must fail closed on timeout, duplicate, conflicting branch, rollback, revocation, malformed signatures, signer change and unavailable authority. Do not treat a signed but uncommitted response as proof. No secrets, provisioning, external egress or production permissions may be changed without authorization.

## C. Mandatory acceptance artifacts, each separately evidenced

- [ ] Named independent reviewer and completed findings for every restricted file.
- [ ] Approved source publication or authorized offline audit path; no reconstruction/bypass.
- [ ] All 42 source files accounted for and unchanged v1.4 hashes verified; repaired code must be versioned separately with approved manifest.
- [ ] Independent custody design reviewed, with a real provider and authenticated, independently pinned readback; optional synthetic tests cannot satisfy this gate.
- [ ] Crash/restart/revocation/concurrency/rollback/duplicate/replay and corrupt-checkpoint adversarial report.
- [ ] Final **exact SHA** Linux full regression, source/hash gates and permitted browser/UI acceptance.
- [ ] Human keyboard/screen-reader and privacy review using fictional data.
- [ ] Explicit release signoff; no implied approval from 170 passing focused tests.

## D. Current blockers and ownership

**Blocker 1 — external reviewer:** Owner/user must nominate a real independent reviewer; engineering cannot self-approve. **Blocker 2 — restricted originals:** reviewer and source owner agree on an authorized artifact/transfer method and hash verification. **Blocker 3 — custody authority:** architecture and actual provider trust root require independent operational ownership; not available in current experimental environment. Engineering may design interfaces and tests but cannot claim live verification.

## E. Reporting rule

Use binary acceptance `not started / underway / blocked / approved` per gate, not a false 20% audit-completion metric. Product implementation completion and release trust are separate axes. Document every finding with exact file, SHA, CI job, reviewer and resolution. Freeze originals and preserve all failures. No main merge, deployment, purchases, permission changes or external AI egress.
