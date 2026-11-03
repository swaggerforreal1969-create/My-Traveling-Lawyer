# Real custody provider release acceptance contract (disabled)

Status: **NOT CONNECTED / NOT APPROVED**. This is an executable readiness boundary, not live independent custody. No external egress or credentials are activated by this milestone.

## Required operational authorization

A qualified independent security reviewer must be appointed under GitHub Issue #1, with approved access to the ten protected originals. Separately, a designated external custody operator must supply an approved FQDN, authenticated and revoked credential procedures, a verified TLS certificate chain, a pre-pinned SHA256 leaf certificate digest, a separately pinned checkpoint signing public key and independently retained monotonic predecessor head. An authorized owner must explicitly approve any real connection, tests, and trust rotation. This repository contains no such credentials, addresses or acceptance approval.

## Testable provider obligations

1. Deny all writes without independently authenticated current actor rights; enforce signer/credential revocation and cross-tenant isolation.
2. Atomically admit a unique reservation and nonce with exact predecessor CAS, monotonic sequence and committed signed event, or fail without partial state; do not treat an ACK as commit proof.
3. Provide independently authenticated read_head and read_event from actual committed history. Require externally retained trust root and sequence before advancing pins.
4. Respond with strict UTF-8 JSON and exact framing. Reject redirects, ambiguous header values, wrong certificate, unsafe content-encoding, malformed endpoint, inconsistent length, nonfinite JSON and oversized bodies.
5. On timeout, crash, conflicting admission or missing ACK, refrain from retrying writes. Execute human-triggered, read-only independent reconciliation; preserve the local reservation fence until authorized proof exists.
6. Demonstrate cross-process, concurrent-operator, service-restoration, signer-rotation, key revocation, history rollback and full-database substitution acceptance with actual provider evidence, not fixtures.

The disabled HTTPS adapter enforces a caller-approved FQDN, PKI hostname validation, independently configured exact leaf certificate pin, single-request operations and strict response framing. Tests under `tests/test_pinned_https_custody_adapter.py` are **no-network mocks** and cannot validate actual DNS/PKI behavior, independent administration, or real-service revocation.

## Outstanding release gates

- Independent reviewer: unassigned; review not started.
- 10 restricted original paths: preserved, missing from hosted source tree; 42-file gate 32/42.
- Production custody operator and authenticated provider: none connected.
- Exact-SHA complete release gate and manual human accessibility/security signoff: not accepted.

Do not change `main`, deploy, provision, purchase, modify permissions or enable external network access based on this file.
