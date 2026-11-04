# My Traveling Lawyer — V2 signed nonce custody service acceptance (NO-GO)

This is an **offline provider-neutral contract**, NOT a connected custody service or authorization to transmit data, provision infrastructure, or deploy.

## Versioned signed commitment

A v2 admission receipt must commit in a canonical, verified signature over:

`schema=mtl.custody.nonce-bound.v2`, `sequence`, `previous`, `nonce_digest`, `reservation_digest`, `event_digest`, `signer_id`.

The signer MUST be independently controlled, verified against an independently held public-key identity, and authorized to commit exactly one operation only after successful compare-and-swap against the separately retained monotonic predecessor. v1 uses distinct storage and cannot be reinterpreted as nonce-authenticated.

## Production-compatible provider operations (no resources provisioned)

1. `admit_once(intent, expected_pin, credential, explicit_authorization)`: at-most-once atomic nonce+reservation+checkpoint update, exact expected version/digest under one transaction. Acknowledgment is always untrusted. Never automatically retry on an uncertain outcome.
2. `read_committed_head(sequence, authenticated_reader)`: exact-sequence readback with signed canonical nonce+reservation+event commitment, separately from admission; require authorization and credential revocation checks.
3. `read_latest(authenticated_reader)`: independently stored tip and proof of monotonic predecessor continuity. Reject forks, rollback, stale signer identities, and withheld history.
4. `reconcile_exact_nonce(nonce, reservation, event, predecessor, trusted_latest)`: read-only bounded history verification. Do not trust local SQLite, signer responses, or an untrusted expected pin to establish external custody.
5. `revoke(signing_identity, authorization)`: independently witnessed revocation must immediately stop future admission and respect signed historic trust boundaries. Unilateral silent rotation prohibited.
6. `inspect_failure_receipt(identity)`: read-only proof for pre-commit termination, post-commit lost acknowledgment, repeated nonce, signature substitution, conflicting writer admission and provider outage.

## Mandatory acceptance evidence

- Genuine independently administered signing identities, asymmetric keys and immutable external trust pins. HMAC fixtures, local files, and synthetic provider processes do not qualify.
- Authenticated transport, independently controlled admission/readback, strict timeout and unambiguous failure handling.
- Independent reviewer tests real credentials, cross-tenant denial, revocation, key rotation, crash/fork/rollback and simultaneous client conflicts.
- Explicit actual provider run ID, SHA, signed receipts, latency, signing configuration, approval decisions and incident response.
- Original immutable 42-file source/hash gate must pass, including ten restricted originals. No reconstruction or bypass.
- No automatic replay, trust advancement, write-fence clearance, deployment, main merge or client data.

## Offline executable acceptance

`python -m unittest discover -s tests -p 'test_nonce_bound_custody.py' -q`

`python -m unittest discover -s tests -p 'test_v2_crash_process.py' -q`

The new v2 subprocess suite uses **real SIGKILL processes with fictional credentials and SQLite**. It demonstrates local crash atomicity, not external finality. Production NO-GO.
