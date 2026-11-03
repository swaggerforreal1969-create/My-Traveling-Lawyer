# Two-person manual legal-source review — experimental acceptance (2026-11-03)

## Implemented
- `src/second_source_review.py` implements `SecondSourceReview` for **two distinct authorized local user accounts** examining the same offline source observation.
- Reuses real `SecureCore` matter authorization, `ResearchEvidence`, and `SourceObservation`, not a fake authentication stub.
- The writer of the original source observation cannot act as second reviewer. An active owner/editor from the authorized matter can provide exactly one countersignature per observation. Viewers may read validated history but may not approve.
- Decisions: `corroborated_manually`, `needs_further_review`, `rejected`; bounded notes required. Each new record binds the existing observation fingerprint, original and second actor IDs, source, matter, time and decision, and appends an audit event.
- Read and write operations validate underlying source-observation integrity; modified research, observation or countersignature fails closed. Decisions remain available after SQLite restart.
- **No independent external legal-source authentication**, court website fetch, case treatment verification, real client data, AI egress, deployment or spending.
- Two user accounts are a *procedural separation-of-duties measure*, not independent cryptographic custody or evidence that a source is legally authoritative.

## Test evidence
- Initial focused run failed all 15 tests due to stale expected matter version in new fictional fixture; no production source defect. Fixed expected grant version.
- Corrected new module suite: **15/15 passed in 1.527s**.
- Complete assembled local source baseline and all previously developed isolated modules: **439/439 passed in 18.246s** with `python -m unittest discover -s tests -q`.
- `python -m compileall -q src tests` passed.
- GitHub blob hashes confirmed exact matches with local `git hash-object`:
  - `src/second_source_review.py`: `9599de15c2eddaee9844c47ed837d329a92b4c73`
  - `tests/test_second_source_review.py`: `451de91236fe7c5f9086d13f8e7daece192252ae`
- Tests cover second-person success and review disclaimers, self-review denial, viewer write denial, cross-firm access, revoked user, duplicate signing, wrong observation/evidence, tampered underlying research, altered observation, altered countersignature history, read-only viewer access, restart persistence and malformed review input.

## Unchanged release controls and next milestone
- Issue #1 checked: **open, unassigned, zero reviewer comments**. Ten original v1.4 files remain blocked and untouched; migration **32/42**.
- GitHub Linux CI and authentic HTTP/browser acceptance remain unverified; the 439-test result is **local** evidence only.
- Maintained `webauthn` / `fido2` dependencies unavailable in current runtime. Do not mislabel custom challenges as WebAuthn.
- Frozen originals, `main`, Koontcee, Diezel and production permissions preserved.
- Next: obtain independent reviewer decision, finish approved 42-file migration and exact-SHA Linux/browser gate. In parallel pursue genuine maintained-library WebAuthn and independently sourced legal authenticity/treatment checks in a permitted network/dependency environment.
