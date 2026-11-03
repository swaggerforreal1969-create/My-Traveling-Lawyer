# Device Step-Up v1.2 - Experimental Only

New endpoints (all require existing demonstration Authorization bearer):
- `POST /api/device/register` with `public_key`: 32-byte raw Ed25519 key base64url; returns key_id.
- `POST /api/device/challenge` with `key_id`: returns random challenge, purpose and 90-second expiry.
- `POST /api/device/verify` with `key_id`, `challenge` and `signature`: verifies Ed25519 signature over UTF-8 `mtl-device-stepup-v1\n` + challenge. Returns `verified:true, step_up_only:true`.

Challenges are tied to a user and device key and can be used once. Old challenges survive process restart, but cannot be replayed. Verified proof does not issue a login session, escalate permissions, or enable sensitive actions. Proof is logged to the audit chain.

This is *not* WebAuthn, a production passkey flow, phishing-resistant authentication or secure onboarding. The exact RP ID, origin, browser authenticator verification, and genuine user-presence/user-verification semantics remain future work. No client data permitted.