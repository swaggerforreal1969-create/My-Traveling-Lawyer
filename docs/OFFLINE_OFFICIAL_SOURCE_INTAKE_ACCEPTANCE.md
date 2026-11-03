# Offline allowlisted legal-source intake — adversarial acceptance (2026-11-03)

## Implemented
- `src/official_source_intake.py` provides `OfficialSourceIntake` for an authenticated, matter-scoped recording of **supplied bytes** and an operator's manual review note.
- Explicit per-instance hostname allowlist and HTTPS URL checks. Rejects unsafe schemes, URL userinfo, nonstandard ports, IP literal allowlist entries, attacker suffixes, malformed URLs and excessive size. Matching a configured host is **not proof of genuine court origin**.
- Stores document SHA-256, byte count, selected URL, operator, source evidence digest, UTC capture time and record fingerprint in an append-only local SQLite table with the existing audit event.
- Read-only history requires original firm/matter permissions and detects altered metadata or source bindings. No document bytes returned in history. All returned status fields deny software confirmation of source authenticity or current legal authority.
- No network fetch, legal citation treatment check, jurisdiction determination, outbound AI, real client data, purchase or deployment.

## Executed tests and repaired defect
- Initial focused run: **15/16 passed**. A defect in IP-address rejection was observed; the ValueError handler inadvertently swallowed the explicit rejection of an IP literal.
- Fixed with a Python try/except/else branch, preserving fail-closed behavior. Re-ran **16/16 focused tests passed in 0.801 seconds**.
- Local full unified regression with original v1.4 and experimental components: **418/418 tests passed in 15.325 seconds**. Python compileall passed.
- New committed source blobs fetched back and **matched local `git hash-object` exactly**:
  - src/official_source_intake.py `7f05193ffa1fef3bf0f532529bff0f04d655a2c1`
  - tests/test_official_source_intake.py `2f31f706a8dd3c47011dae31da9039988bf5c2b5`
- Adversarial cases: viewer write denial, cross-firm/revoked token, wrong evidence, changed research or observation, phishing suffix, insecure HTTP, URL userinfo, nonstandard ports, IP literals, oversized document, no automatic socket network call and persistence across restart.

## Acceptance limits
- Independent review Issue #1 checked: open, unassigned, zero comments. No independent authorization to publish the ten original blocked files.
- Original v1.4 migration remains 32/42. The existing immutable source gate intentionally blocks GitHub Linux CI until approved publication.
- No exact-SHA GitHub CI success, genuine browser acceptance or WebAuthn/passkey implementation. Maintained `webauthn` and `fido2` dependencies are unavailable here. Custom signed device challenges are not WebAuthn.
- A configured host and user-supplied document bytes do **not** establish the document actually came from that server. SHA-256 only protects local consistency, not independent trusted custody. Official authenticity, controlling authority and subsequent treatment require independent source verification.
- `main`, frozen v1.4 archive, Koontcee, Diezel and production permissions unchanged.

## Next milestone
1. Obtain named independent reviewer disposition in Issue #1, then publish ten frozen originals only through authorized platform-approved path.
2. Verify 42/42 exact source hashes and run exact-SHA GitHub Linux and genuine authenticated browser gates.
3. Integrate official server-side legal source retrieval with proper trust/SSRF controls, actual TLS provenance evidence and attorney confirmation, in an authorized networked environment.
4. Install maintained WebAuthn verifier and test authentic RP/origin-bound ceremonies, then integrate passkey-gated mobile access and operational 24/7 AI with separate explicit confidentiality approvals.
