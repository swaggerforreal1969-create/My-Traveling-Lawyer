# Fail-closed source review release projection — experimental acceptance (2026-11-03)

## Executed functionality
- `src/source_release_projection.py` implements `SourceReleaseProjection.project(token, matter_id)`, a single-matter, read-only research-disposition view using the **real** SecureCore, SourceObservation and SecondSourceReview implementations. No fake authorization providers.
- Revalidates current research source integrity, each observation fingerprint and each second-review fingerprint on every read. Any mismatch raises `EvidenceInvalid`; missing or unfamiliar review state never produces positive output.
- The newest observation is authoritative **for procedural workflow status only**. A newer observation invalidates the earlier one's two-person-review status until itself countersigned.
- Statuses are precisely `needs_first_observation`, `needs_independent_second_review`, `needs_additional_review`, `rejected_by_second_reviewer`, or `two_people_reviewed_unverified`.
- Every response and source entry explicitly sets legal-authentication, legal-currency and court-filing-approval flags to **false**. No contents, URLs, manually captured text or attorney notes are returned; at most 100 sources per matter (fail closed rather than truncate).
- Token, firm and matter permission checks use the existing demo core. No AI or network egress or production change.

## Actual verification
- **15/15 new focused integration/adversarial tests passed** in 1.803s.
- **454/454 full locally assembled regression tests passed** in 19.381s, using the original v1.4 archive plus all previously published isolated experimental components, through `python -m unittest discover -s tests -q`.
- `python -m compileall -q src tests` passed.
- The newly published GitHub blobs were fetched and matched the tested local bytes:
  - `src/source_release_projection.py` = `625514c47e0e90251289c98e23f2caf0924277f0`.
  - `tests/test_source_release_projection.py` = `93ea302a8a9f70e22db91ea6b43542b6a5d76627`.
- Tests cover initial/no observation, missing second review, two humans never certifying law, negative review, stale corroboration after newer observation, source and review tampering, revoked and cross-firm credentials, viewer data minimization, persistence across restart, no network, no business audit writes, input validation and collection overflow.

## Not accepted or independently verified
- **Issue #1 remains open, unassigned and without reviewer comments** at check. No approval to publish the ten originally blocked v1.4 files.
- Original frozen-source migration remains **32/42**, exact historical original hashes preserved and blocked files untouched. No change to `main`, frozen archive, Koontcee or Diezel.
- GitHub exact-SHA Linux CI and genuine browser acceptance not verified. The published GitHub branch is missing ten original source files and the fail-closed source gate remains active.
- Neither maintained `webauthn` nor `fido2` package exists locally; no authentic WebAuthn registration/assertion is implemented. A custom signed-device challenge must never be called WebAuthn.
- A two-person local review is a procedural record, NOT official-source authentication, verified legal treatment or independently trusted custody. No operational 24/7 AI, real client information, external services, purchases or deployment.

## Next engineering gate
1. Assign an independent reviewer to Issue #1 and record findings and approvals. Do not bypass rejected publication controls.
2. After approval, publish the remaining original paths through an authorized method, verify all 42 SHA-256 fingerprints, and run exact-SHA Linux CI plus genuine browser acceptance.
3. In a permitted dependency environment, implement maintained-library WebAuthn with origin/RP binding, replay prevention, authenticator counter handling and revocation tests.
4. Add independently authenticated official legal-source retrieval and citation-treatment validation with attorney sign-off, preserving Confidential Mode and zero real-client-data egress until separately authorized.
