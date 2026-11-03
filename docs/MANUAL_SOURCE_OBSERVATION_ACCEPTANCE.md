# Manual legal-source observation and custody — isolated acceptance (2026-11-03)

## Implementation
- `src/source_observation.py`: `SourceObservation` records an authorized owner's/editor's manually entered observation of a research source already attached to a particular matter.
- Captures bounded text with SHA-256, source-evidence digest, actor, UTC time, reviewer note and an immutable-content integrity digest for each new record; every capture appends a new row and the existing application audit event.
- Read-only history is available to owner/editor/viewer under the same matter access check, with bounded results, and intentionally returns *only metadata/digests*, not full manually captured body text.
- Detects modified body text, altered metadata, mismatched evidence binding and tampered original research excerpts, failing closed.
- No website fetch, legal citation treatment check, external authenticity proof, network request or AI transmission.
- Fields expressly state `official_source_authenticated=False` and `current_legal_authority_verified=False`. A hash proves local integrity against this mutable database snapshot, not legal authenticity or independently trusted custody.

## Evidence (executed)
- `python -m unittest discover -s tests -p test_source_observation.py -q`: **15/15 passed in 1.027 seconds**.
- Unified local v1.4 baseline plus all isolated published components and new observation journal: `python -m unittest discover -s tests -q`: **402/402 passed in 16.427 seconds**.
- `python -m compileall -q src tests`: passed.
- New GitHub source and test files fetched and matched the locally tested Git blobs:
  - `src/source_observation.py`: `b5da8b06029f32934f93716846bfd7c042b3c396`.
  - `tests/test_source_observation.py`: `7a40332b62edd0ab7a1c3eae7f5098278fe69e07`.
- Adversarial tests include revoked/cross-firm credentials, viewer write denial, wrong evidence, malformed/oversized capture, tampered source and record, persistence after restart, absence of external socket calls, audit append and read-only history.

## Release boundaries
- GitHub Issue #1 checked at start of increment: **open, unassigned, zero reviewer comments**. There is no independent security clearance for ten previously blocked originals.
- Frozen v1.4 source migration remains **32/42** with exact-hash controls intact. No blocked originals changed or uploaded.
- GitHub Linux CI and genuine browser pass **not established**. Real WebAuthn packages `webauthn` and `fido2` remain absent in current environment; genuine WebAuthn is not implemented.
- No operational 24/7 hosted AI, official-law verification, production deployment, spending or real client data. `main`, Koontcee and Diezel preserved.

## Next measurable acceptance
1. Obtain independent review findings on Issue #1; do not bypass any rejected file upload.
2. After authorized clearance, publish and check all 42 original hashes, then exact-SHA Linux CI and authenticated browser acceptance.
3. Build real maintained-library WebAuthn RP/origin-bound ceremonies in an approved dependency environment, with replay, attestation policy and credential-revocation tests.
4. Integrate an official legal-source retrieval and independent citation-treatment verification workflow with human review, using fictional fixtures and explicit sovereignty controls.
