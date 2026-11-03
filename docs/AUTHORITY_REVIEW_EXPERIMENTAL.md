# Experimental human authority-review journal — isolated increment

## What works
- `src/authority_review.py` implements a persistent append-only human research assessment journal, scoped to an existing matter.
- A reviewer must hold an **active demonstration bearer token** and owner/editor matter grant to record a review. Read access permits owner/editor/viewer, subject to the same firm and matter ACL.
- Review types: `checked_against_original`, `needs_recheck`, `rejected`.
- Review notes are mandatory. Every record binds the stored original research source digest and captures the authenticated user, matter, evidence ID, timestamp, and immutable review ID.
- The existing audit hash chain receives `research.human_review` events.
- Missing/wrong-matter source IDs, tampered research excerpts, revoked credentials, cross-firm access and viewer writes fail closed.
- Separate test module `tests/test_authority_review.py` covers 10 cases including persistence and reassessment events.

## Evidence
- Local isolated full test suite: **302/302 passed in 28.543 seconds**, original v1.4 suite plus 10 new tests.
- Both new GitHub source blobs have exact matching hashes against locally tested files.
- GitHub CI is **not accepted** while the ten unapproved v1.4 original files remain missing and the existing 42-path immutable gate fails closed.

## Unimplemented dependencies — release blockers
- This is a **low-level server-side module**, not a browser/mobile workflow or authenticated HTTP route. Integration with `src/secure_server.py` is blocked by pending source approval.
- `checked_against_original` stores a human assertion, **not cryptographic proof, autonomous retrieval, Shepardizing/KeyCite, jurisdictional validation, binding authority, or current legal citation verification**. All outputs explicitly state that software has not authenticated or legally verified the source.
- No real client data. Not legal advice or live case research.
- Independent review issue: https://github.com/swaggerforreal1969-create/My-Traveling-Lawyer/issues/1 — still open, unassigned and no approval at last check.
- Genuine WebAuthn and operational 24/7 AI remain future work, no deployment or spending.

## Next acceptance
1. Obtain independent approval or repair findings for remaining ten original files; do not bypass tool safety blocks.
2. Verify all 42 hashes and exact GitHub Linux/browser acceptance after approved publication.
3. Integrate the review journal behind authenticated existing API with browser tests; verify legal sources from official authorities with human sign-off.
4. Separately implement real maintained-library WebAuthn and operational 24/7 AI with strict confidentiality gating.
