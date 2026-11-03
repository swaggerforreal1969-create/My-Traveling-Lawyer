# External checkpoint readback boundary — experimental integration contract

## Classification

**Engineering interface only. No independent custody provider is connected, no external network egress and no release approval.** The deterministic tests use a clearly identified synthetic HMAC test fixture, **not** an approved witness signer. The production integration must provide an independently administered and authenticated checkpoint service and an externally pinned trust root.

The read-only verifier at `src/independent_checkpoint_boundary.py` deliberately cannot write, clear the local fence, authorize users, attest legal authenticity, or provision resources. `VerifiedReadback.independently_custodied` is always `False`; a passing fixture cannot turn it true.

## External dependencies (unavailable; do not fabricate)

1. An independent administrator controls the service and its key custody; the client is given an authentic public key and an independently retained predecessor sequence/digest pin.
2. An atomic admission API will be required before any real write. The provider must bind a unique reservation digest to the committed event, predecessor checkpoint, signer and monotonic sequence in one durable transaction. It must expose a non-replaying read-only event and head API with independently verifiable signatures.
3. Source implementations must authenticate transport and callers, support revocation, defend against equivocation, reject forged/signing-key downgrades, and provide live committed-history readback beyond the writer's assertion.
4. Key rotation or pin advancement is a separate independently authorized workflow; no unreviewed automatic trust-on-first-use or resync.
5. On provider timeout, ambiguous acknowledgment or unavailable readback: retain the local pending fence. Never repeat uncertain writes or claim the receipt is proof of committed history.

## Current strict verifier

Constructor requires `PinnedCheckpoint(sequence, digest, signer_id)`, `provider.read_head()`, `provider.read_event(sequence)`, and `verify_signature(signer_id, canonical_signed_bytes, signature)`. The signature callback must be implemented using the externally pinned, approved public key: **there is no default implementation**.

`verify(reservation=<exact 64-character local version>, event_digest=<explicit 64-character hash>, proposal=<optional untrusted acknowledgment>)` validates one contiguous step beyond the caller's independently pinned predecessor, exact signer, authenticated head fields, specific reservation digest and event digest, committed readback state and matching optional acknowledgment. It rejects any omitted or extra fields, noncontiguous sequence, invalid signature, head/readback disagreement, lost acknowledgment conflicts, rotation and skipped history. It returns an observational value only. The method does not advance the independently held pin; the caller cannot treat this as a complete monotonic custody subsystem.

## Nonclaims and release blockers

- The readback provider in tests is *not independent*: the fixture holds the fake signing secret and event history in the same test process.
- No write-admission connector, live witness, key-distribution mechanism, signature provenance, provider revocation proof, independent checkpoint persistence or production audit was implemented.
- No guarantee against coordinated storage rollback or service-level equivocation exists without operational separation, independently pinned history and external security review.
- Source gate **32/42** and protected original files remain unchanged. Security Issue #1 requires a named reviewer, approved original-file audit and documented signoff.
- Passing the synthetic test is a prerequisite for a real integration, never a release authorization.
