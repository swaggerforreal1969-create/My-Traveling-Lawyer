# Official-source intake read-time integrity repair — 2026-11-03

## Defect and fix
A forensic review found that `OfficialSourceIntake.list_records()` authenticated the stored source digest's identity but did **not** recompute the digest from the current `research_evidence.title`, `url` and `excerpt`. If an attacker changed an excerpt without also updating its stored digest, the earlier intake record could still be presented as intact. This was inconsistent with the write-time source integrity check.

The isolated experimental module `src/official_source_intake.py` now recomputes the expected SHA-256 for current research source text on **every read**, failing closed when it differs. The history also continues rejecting an evidence record replaced with a new, self-consistent digest, because the prior observation binds the earlier digest. No frozen original v1.4 files were modified.

## Actual executed evidence
- Existing baseline focused suite: 16/16 passed before patch.
- Six added adversarial tests cover altered excerpt, title, URL, stored digest, replacement with a freshly matching digest, and unchanged source history.
- Corrected focused suite: **22/22 passed in 1.329s**.
- Full assembled local original v1.4 + isolated experimental suite: **424/424 passed in 17.701s** using `python -m unittest discover -s tests -q`.
- Source/test GitHub blobs match exact locally tested `git hash-object` values:
  - `src/official_source_intake.py`: `11093e744d1325d138773d81f62cc3542887f760`
  - `tests/test_official_source_intake.py`: `69b29c796eadff96cc6d273f7fd8901c0aa6fa2a`.
- This is **local** regression evidence, not a successful GitHub Linux CI acceptance or real browser run.

## Safety and outstanding release gates
- Issue #1 was checked before work: open, unassigned and zero reviewer comments. No independent security review approval.
- Original frozen source migration remains **32/42**, and ten blocked originals remain untouched.
- Genuine maintained-library WebAuthn unavailable in this execution environment (`webauthn`, `fido2` absent). Do not substitute custom signatures for passkey verification.
- Recorded bytes, allowlisted hosts and local SHA-256 checks do **not** prove court-site origin, legally binding authority, subsequent treatment or independent rollback-resistant custody.
- No real client data, network source retrieval, AI egress, deployment, spending or changes to `main`, Koontcee or Diezel.

## Next milestone
1. Obtain independent reviewer disposition on Issue #1 before any attempt to publish ten blocked originals.
2. After approved publication verify all 42 original hashes and a successful exact-SHA Linux and browser gate.
3. In a permitted dependency environment implement maintained-library WebAuthn RP/origin, challenge replay and credential revocation checks.
4. Develop an independently witnessed or cryptographically signed source provenance workflow with *trusted* origin evidence, then source treatment checks with attorney confirmation.
