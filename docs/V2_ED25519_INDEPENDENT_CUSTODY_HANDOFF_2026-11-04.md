# My Traveling Lawyer — Asymmetric V2 Custody Security Handoff

**Status: experimental. PRODUCTION NO-GO.** Current implementation uses an injected, manually pinned Ed25519 public key and fictional, RAM-only private keys in tests. No production signer, external service, provider approval, reviewer signoff, or external key infrastructure was connected.

## Implemented verification and reproducibility

- `src/v2_asymmetric_trust.py`: exact 32-byte Ed25519 public key, SHA-256 key fingerprint pin, authorized signer ID, externally supplied validity interval and evaluation time, explicit revocation and strict canonical hex signature.
- `src/v2_custody_transport.py`: signed nonce/reservation/event/head-chain validation with strictly read-only recovery. Existing v1 client and receipt format unchanged.
- `tests/test_v2_asymmetric_trust.py`: fictional Ed25519 test keys generated exclusively in memory; independently supplied public key and signer label, wrong-key and wrong-fingerprint rejection, expired/not-yet-valid/revoked pins, changed signer/nonce/head, credential loss and stable signed readback.
- `tests/test_v2_crash_process.py`: separately exercised real SIGKILL pre/postcommit crash, lost acknowledgement, competing writers, revoked credentials and local rollback.
- Hosted workflow: `.github/workflows/experimental-regression.yml` runs focused acceptance and original 42-file source/hash checks unchanged.

## Requirements for independent review and external custody acceptance

**Authorized restricted-source custodian:** Supply original authentic copies of the ten unavailable items. Validate their immutable hashes against the existing 42-file manifest, without recreating, rewriting, or weakening the gate.

**Appointed independent security reviewer:** Inspect source, test output, frozen release controls and exact SHA. Determine whether the public key root and signer IDs are independently managed, whether time and revocation status come from independently authenticated authority, and whether signed evidence is non-equivocating. File separate pass/fail report; PRs #27/#36 and Issue #1 remain the tracking baseline.

**Independent custody operators:** Present real operator identities, separately controlled Ed25519 signing keys and securely distributed public-key fingerprints; authenticated transport certificates, revocation, service-independent monotonic CAS/checkpoints, read-only exact receipt-history APIs, and independently retained predecessor/head pins. Supply signed real-provider test receipts and external audit/run IDs. Do not use HMAC fixtures, local SQLite or Python process separation as custody proof.

**Adversarial provider acceptance:** Lost acknowledgment with exact signed nonce readback; crash before/after commit; competing writers; rollback/fork/split view; stale predecessor; revoked credential, expired signer and unauthorized rotation; false algorithm and key substitution; independently retained checkpoints; bounded p50/p95 and fault durations; GUI responsiveness. No automatic replay or fence clearance.

**Permission constraints:** No service provisioning or egress, real client data, purchases, permission changes, main merge, deployment, write replay, or restricted-source reconstruction. Until original-source integrity, actual independent review and external custody pass, production remains NO-GO.
