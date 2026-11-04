# My Traveling Lawyer — externally anchored Ed25519 authority-policy handoff

**Release classification: NO-GO.** This is a read-only offline policy verification contract, not an independent custody deployment or an independently trusted time source.

## Implemented
`src/v2_signed_authority_policy.py` verifies a versioned Ed25519 signed signer-authorization policy. Accepting a policy requires separately retained *two* pieces of pinned trust evidence: (1) the exact 32-byte authority public key and SHA-256 fingerprint, plus authorization validity and revocation status; (2) the exact approved policy generation and canonical SHA-256 digest. It refuses unsigned or substituted authority keys, unapproved policy revisions/rotation, altered validity/revocation terms, stale generations and wrong custody signer identity. If accepted it returns a pinned Ed25519 verifier compatible with the existing v2 nonce-bound historical receipt client. No built-in clock, key discovery, policy auto-update or write API.

## Exact external inputs still required
- **Authorized restricted-source custodian:** restore ten original files through an authorized verified provenance process, matching immutable 42-file manifest. Current published tree is 32/42; do not fabricate originals.
- **Independent security reviewer:** appointment, actual source SHA, provider threat model, Ed25519 signature and authorization-policy review, nonce/fork/rollback/crash test evidence, source-gate pass, signed approval or rejection. PR #27 and #36, Security Issue #1 retained.
- **Custody authority A and B:** independently managed Ed25519 roots and custody signers, independently retained non-rollbackable policy generation/digest and history checkpoint head, authenticated credential transport and revocation, witnessed cross-provider non-equivocation, atomic CAS admission, exact signed nonce readback after crash and uncertain acknowledgments.
- **Trusted time and revocation:** a reviewer-approved authenticated time and policy-revocation authority; a caller-supplied integer does not prove freshness. If the authority can rewrite both the pin and the signed policy, local cryptography alone cannot detect rollback.
- **Conformance:** real provider receipts/run IDs and measured latency for concurrent admission, lost-ACK read-only recovery, pre/postcommit SIGKILL, invalid signer/rotation/expiration, coordinated local rollback, cross-observer split view, credential revocation, and operator-facing GUI responsiveness.

## Offline commands
`python -m unittest discover -s tests -p 'test_v2_signed_authority_policy.py' -q`
`python -m unittest discover -s tests -p 'test_v2_asymmetric_trust.py' -q`
`python -m unittest discover -s tests -p 'test_v2_crash_process.py' -q`

No main merge, external egress, deployment, real client data, purchases, permission changes, original reconstruction, automatic write retry, trust advancement or fence clearance. Production remains **NO-GO** pending original source integrity, appointed reviewer and independent external custody.
