# Real authenticated mobile matter chain — verified local acceptance

## Verified functionality

End-to-end, **without fake authorization or fake briefing objects**:

`SecureCore._identity(token)` and `_role(user, matter)` → `ResearchEvidence` → `AuthorityReview` → `MatterBrief.prepare()` → `render_mobile_brief()` → `MobilePreviewGateway.prepare()`.

The new regression module `tests/test_real_mobile_chain.py` uses a real temporary SQLite database and fictional firms, users, matters, notes, tasks and research excerpts. No external network/AI provider, real client data, HTTP listener, deployment or purchase.

## Acceptance checks
- **16/16 new real-chain tests PASS**, covering successful authenticated HTML output and security headers, viewer reads without authority review writes, outsider/cross-firm denial, ungranted same-firm denial, revoked/expired/idle credentials, tampered source and human-review digest, incomplete human source review risk flag, HTML injection escaping, no socket connection, no added business audit event for reads, unauthorized matter, bounded output rejection, and preservation of review status after SQLite restart.
- **338/338 complete local regression PASS** in **14.605s**, containing preserved v1.4 original tests (292), mobile renderer tests (14), gateway tests (16) and the 16 real-chain tests.
- `python -m compileall -q src tests` PASS on the local integrated tree.
- **Seven relevant GitHub blob SHA values matched the exact locally tested modules:** original `secure_engine.py` and `research_evidence.py`; new `authority_review.py`, `matter_brief.py`, `mobile_matter_view.py`, `mobile_preview_gateway.py`; new `tests/test_real_mobile_chain.py` (`0165047b7f6b6511d09e29805d5a475a81104d51`).
- The test loaded the **actual** authority and matter-brief modules; previous stand-in usage is retired for this acceptance case.

## Scope and gaps
- This is an **in-process application chain**, not deployed HTTP or authenticated browser acceptance. The local renderer produces HTML, but a fully authorized browser-navigation test did not run.
- The local integrated directory includes all preserved original v1.4 files for a complete regression. The connected GitHub engineering branch still has **32/42 original v1.4 paths**. All previously published original GitHub source paths have passed the historical exact-hash check, but the ten unpublished originals remain blocked.
- GitHub Issue #1 for independent security approval remains **open, unassigned, zero reviewer comments** at last inspection; do not bypass the safety blocks. No independent review approval.
- GitHub Linux CI remains unverified/unpassed (expected fail-closed due missing original source).
- Human review flags are recorded attestations, **not independent source authenticity or citation currency validation**. The input dates are user-entered reminders, not legally calculated deadlines.
- Genuine maintained-library WebAuthn, official online legal authority retrieval, independent audit custody and 24/7 hosted AI remain unimplemented.
- No changes to `main`, frozen originals, Koontcee or Diezel.

## Next coherent acceptance
1. Obtain named independent reviewer findings/approval in GitHub Issue #1.
2. Finish source migration via an approved channel, reconcile all 42 exact SHA-256 hashes and obtain successful exact-SHA GitHub Linux CI.
3. Run real browser acceptance and authenticated HTTP denial tests in a permitted environment using fictional data.
4. Integrate maintained WebAuthn passkeys and legal-source provenance with explicit no-client-data outbound boundaries, then operational 24/7 AI readiness.
