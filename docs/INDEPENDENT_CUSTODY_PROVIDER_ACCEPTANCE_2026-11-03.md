# My Traveling Lawyer — Independent Custody Provider Acceptance Contract (offline planning only)

**Status: NOT APPROVED.** This document is a production acceptance checklist, not evidence that any independent provider, signing key, external ledger, reviewer, or transport is connected.

## Provider-independent security boundary

The application may only accept an externally controlled provider for production after an appointed independent security reviewer records evidence for **all** of the following:

1. **Administrative independence.** Each signer and the corresponding predecessor-pin store are under independently accountable, segregated control. Distinct labels, Python objects, accounts in one administrative domain, and fixture HMACs do not establish independence.
2. **Real cryptography.** An approved asymmetric signing algorithm and independently provisioned public-key trust anchors. No test secrets or in-process generated keys qualify. Signatures cover exact schema, source signer identity, two witness identities, monotonically increasing sequence, both predecessor head hashes, exact operation-reservation digest, event digest, and final commit status.
3. **Transport.** Authenticated, server-identity-validated transport with bounded timeouts, explicit credential lifecycle, revocation tests, and resistance to replay and cross-tenant credential confusion. The application has no authorized external egress yet.
4. **Atomic monotonic admission.** One operation/nonce admitted at most once, with compare-and-swap against an independently committed predecessor sequence+digest; crash before commit leaves no finality, crash after commit permits read-only exact replay detection. Conflicting simultaneous admissions cannot both finalize.
5. **Read-only independent readback.** Separate authenticated history and pin readers return committed records and checkpoint heads independently of the write acknowledgment. A lost acknowledgment must never trigger automatic resubmission.
6. **Non-equivocation.** Independent observers cross-check every signer-specific normalized signed head at each generation. Withheld, rolled-back, forked, or inconsistent heads fail closed and produce an incident-review requirement.
7. **Key rotation.** Rotation requires explicit approved dual-signer transition evidence, independent operator identity verification, and new trusted-pin authorization. Silent or unilateral signer replacement is rejected.
8. **Failure operations.** Measured service timeouts, network partitions, corrupted responses, revoked credentials, concurrent writers, provider outage, partial commits and process termination all fail closed; local fences are never automatically cleared.
9. **Independent custody and rollback protection.** Two outside custodians demonstrate retained monotonic predecessor checkpoints that cannot be rewritten by application administrators or by a compromise of the local SQLite database and sidecar. A locally supplied expected pin is not a substitute.
10. **Reviewer signoff and immutable evidence.** An appointed independent reviewer records actual provider identities, signed test receipts, bounded production-compatible acceptance run IDs, exact tested source SHA, deployment security configuration and limitations.

## Executable offline acceptance currently available

- `src/independent_checkpoint_boundary.py`: predecessor-pinned signed checkpoint readback
- `src/dual_witness_history.py`: two differently configured pinned signers
- `src/cross_observer_history.py`: two-observer signed-head agreement
- `src/read_only_pin_quorum.py`: stable dual signed predecessor sources; no automatic trust changes
- `src/authenticated_pin_source.py`: strictly signed, independently configured source identity
- `src/multi_generation_finality.py`: bounded contiguous, read-only generations without pin persistence
- `tests/test_multi_generation_finality.py`: controlled fictional test fixtures and independent subprocess restarts

**Not accepted:** Actual external service, transport authentication in operation, real independent signer administration, externally retained rollback-resistant storage, production key rotation, independent reviewer appointment, 42/42 immutable original-source gate. No main merge, deployment, permission changes, real client data, external egress, write replay, or fence clearance are authorized.
