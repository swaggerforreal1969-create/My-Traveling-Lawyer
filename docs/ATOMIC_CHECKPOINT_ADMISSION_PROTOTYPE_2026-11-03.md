# Checkpoint admission prototype — nonproduction handoff

**Classification: SYNTHETIC LOCAL PROVIDER ONLY.** No external service, independent trusted operator, production identity, key custody or network connection exists here. No real attorney/client data allowed.

This milestone builds `src/checkpoint_admission_prototype.py`, a local SQLite demonstration of the provider-side transactional contract used by `src/independent_checkpoint_boundary.py`. A human/organization must still authorize a *real separately administered* append-only checkpoint provider, authenticated transport, independent trust-root pinning and retention.

## Transactional contract

- Caller submits a 256-bit reservation version, a unique 256-bit nonce, an event digest, an exactly pinned predecessor and a credential.
- Authentication callback executes under a single SQLite `BEGIN IMMEDIATE` with signer-revocation check, unique nonce and unique reservation check, exact predecessor matching and monotonic sequence assignment. Failures roll back the whole transaction.
- Signer callback signs the canonical head fields. The signed head and its matching committed event are persisted atomically; only then is an **untrusted** acknowledgment returned.
- A lost acknowledgment never authorizes replay. A separately pinned reader uses `CheckpointReadbackBoundary.verify` to check authenticated head + committed history readback.
- Revoking the signer prevents further admissions; trust-root rotation requires separately authorized re-pinning. A fixture signature is not independent evidence.
- SQLite journal and genesis are local, mutable and subject to coordinated rollback, database deletion, substitution and storage-operator equivocation. An independently held pin may detect some rollbacks but this implementation does not satisfy independent custody or distributed fault tolerance.

## Adversarial acceptance

`tests/test_checkpoint_admission_prototype.py` exercises atomic commitment, duplicate/replayed nonces, conflicting reservations, stale predecessor, current caller reauthentication, signer revocation and signer failure, uncertain acknowledgment, forged signatures, mismatched readback, two concurrent operators, successor checkpoint and whole-history rollback with independently retained vs rolled-back pins.

## Required production work (not authorized or performed)

1. Replace the local SQLite fixture with a separately administered transactional witness service, and supply independently retained, externally pinned state. No trust-on-first-use downgrade.
2. Implement real authenticated transport, credential/role revocation, signing key lifecycle, secure external provisioning, retention and auditable authority handoff.
3. Bind the actual attorney write path to a committed external reservation protocol only after complete design and security review; do not adopt the prototype service as permission to write.
4. Test process termination, lost acknowledgments, mid-transaction aborts, signer rotation/revocation, stale pins, duplicated credentials, cross-tenant leakage and full database/service rollback.
5. Obtain a named independent security review covering all ten protected original paths and release requirements in `docs/INDEPENDENT_SECURITY_AUDIT_HANDOFF_2026-11-03.md`. The required 42-file gate remains unchanged and currently 32/42.

**Never report synthetic fixture success as production independent-custody approval.**
