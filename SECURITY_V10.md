# Security boundary v1.0 — fictional-data prototype

## Delivered
- Server-side 300-second sliding idle timeout evaluated for every credential validation, independently of browser timers. Existing credentials migrate to a last-seen timestamp. 12-hour absolute token expiry and explicit revocation remain.
- Ed25519 signed audit-head witnesses. `src.audit_witness.sign_head()` signs an audit `seq`/hash and `verify_core_against_pin()` checks the pinned signature and its ancestor against the verified local chain. Private signing key and signed head must be stored **outside** the app database and verified through a trusted public key obtained out of band.
- Ten focused adversarial tests: inactivity, future clock anomaly, persistence, credential rotation, signed ancestor, wrong key, forged signature, rollback, row tampering.

## Not delivered
- No WebAuthn/passkeys or identity-provider enrollment. Bearer tokens remain demonstration credentials. A production passkey design requires origin-bound challenge issuance, attestation policy, credential counter handling, recovery and phishing-resistant enrollment.
- Witness utility is not wired to independent custody and does not establish rollback resistance by itself. A malicious operator may delete both database and local witness; verified off-host persistence is mandatory.
- No production encryption at rest, hardware keys, penetration test, or data classification audit.
- Browser real-device acceptance remains separate from test suites. A localhost security policy may block Chromium.
- No hosted AI provider or uptime guarantee. Never input real client records.

## Next mandatory gate
Complete authentic browser workflow acceptance in a permitted environment, implement real OIDC/WebAuthn identity and verified independent witness storage, and conduct an independent security review before data use.