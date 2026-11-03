# Sovereign Confidential Mode — v0.9 evidence and limitations

## Implemented
- POST /api/lock requires a valid bearer credential and revokes it in the server database; subsequent requests fail authorization. Explicit UI Lock covers the screen and clears the in-tab token.
- Idle browser timer attempts a server lock after five minutes; hidden/blurred windows retain the v0.8 visual cover. Browser timers are not an authoritative security control, and failed/offline revocation cannot be guaranteed. Production needs short-lived, device-bound, centrally revocable sessions and reauthentication.
- External AI is opt-in and requires synthetic/public classification AND a fixed approved template ID. Only the hardcoded fictional template prompt reaches the external provider; arbitrary user-entered text is never included in outbound AI payload.
- Confidential questions are rejected for external dispatch even when consent is enabled; no case data is automatically attached.
- Loopback-only demonstration server and strict response browser headers remain.

## Not implemented / mandatory release gates
- No true authentication assurance, passkey/MFA, enterprise device posture, trusted execution or OS keychain integration.
- No encryption at rest or end-to-end encrypted messaging. Use vetted authenticated encryption with platform-managed keys, unique nonces, rotation, loss-of-device response, backup encryption, and separation of duties. Do not invent custom cryptography.
- SQLite hash-linked audit is locally tamper-evident only against naive edits; an administrator who can edit the entire database may rewrite the chain. External signed checkpoints/independent custody with anti-rollback are required.
- The v0.8 unrestricted read-only AI interface has become template-only for outbound prompts. Fully private, useful freeform AI requires a rigorously reviewed processing environment and controls for provider terms, data retention and privilege.
- No service hosting, real 24/7 uptime, certified source-grounded legal research, production security assessment, real client data approval, or independent legal ethics review.
- Browser automation attempt blocked by ERR_BLOCKED_BY_ADMINISTRATOR on loopback, not accepted as browser-pass evidence.

## Threat assumptions
Physical overhearing, screen photography, malicious operating system, compromised device or extensions, and a camera pointed at the screen remain beyond an ordinary web app's guarantee. In public, prefer silent text, privacy filter and no privileged speaking; use private rooms for sensitive matters.
