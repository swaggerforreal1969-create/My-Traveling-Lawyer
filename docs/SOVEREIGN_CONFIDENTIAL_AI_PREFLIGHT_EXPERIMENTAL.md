# Sovereign Confidential AI preflight — experimental acceptance, 2026-11-03

## Delivered functionality
- `src/ai_outbound_boundary.py` introduces `ConfidentialAIRequest`, an isolated local authorization and fictional-template release boundary.
- An existing active owner/editor demo credential and authorized matter are mandatory. Viewers/cross-firm credentials fail closed.
- The caller must explicitly supply `explicit_opt_in=True`; only two hard-coded public fictional demonstration templates can be prepared. No user-entered prompt, notes, matter title, legal-source excerpt, or confidential material is read into the prepared AI packet.
- Each grant is a random 256-bit secret, stored only as SHA-256; it is bound to the user's credential digest, firm, matter and selected template.
- A valid grant lasts 1–120 seconds, is atomically consumed once, and cannot be replayed after restart. An inappropriate template or matter cannot consume another template/matter's grant.
- The returned packet includes exact prompt SHA-256 and explicitly states `network_sent=false`, `provider_configured=false`, `fictional_only=true`, `contains_matter_data=false`, `legal_advice=false`.
- **No network transport, third-party API, automated legal advice, live AI provider, production credential, or real client data** is implemented. This is a preflight boundary, not operational 24/7 AI service or proof of provider confidentiality.
- This isolated demo SQLite state is not rollback-resistant distributed consent custody; actual product consent UX and independently trusted durable witness are not yet implemented.

## Tests and evidence
- New `tests/test_ai_outbound_boundary.py`: **17/17 focused tests passed** in 0.940 seconds, including explicit opt-in, template allowlist, matter secrecy, replay, revoked identity, cross-firm/viewer denial, expiration, concurrency, restart and socket-connect isolation.
- Unified local original v1.4 + previously published authority-review, matter-brief, mobile view, gateway, real-chain and preview-session tests + the new boundary: **370/370 local regression tests passed in 19.044 seconds**.
- Local Python compileall passed.
- Both new GitHub blobs were fetched after publication and matched locally tested source exactly:
  - src/ai_outbound_boundary.py Git blob `82e4e2d35d50aeee7ed76ad41d527ffc8a87300f`.
  - tests/test_ai_outbound_boundary.py Git blob `e0985ec7611c1b64cf89d42e8a6dec63b6ac9a77`.
- **No successful GitHub Linux CI or authenticated browser run claimed**; existing fail-closed 42-file source gate remains incomplete.

## Preserved boundaries and remaining acceptance
- Issue #1: open, unassigned, no reviewer comments at cycle start, hence **no independent security clearance**.
- Original v1.4 migration stays **32/42**; the ten blocked originals were neither modified nor published.
- `main`, Koontcee, Diezel, production permissions, and frozen archives preserved.
- Genuine maintained-library WebAuthn passkeys, independently verified official legal research, live AI provider integration, availability/recovery monitoring and production security review are unfinished.
- The test environment does not currently include the `webauthn` or `fido2` Python package; do not mislabel custom bearer tokens as WebAuthn.

## Next
1. Obtain independent reviewer disposition for Issue #1 without bypassing denied uploads.
2. After approval, reconcile all 42 original source hashes, verify exact-SHA Linux CI and genuine browser acceptance.
3. Bind this explicit consent gate into an authorized provider adapter, ensure no client data or unknown user text egress, and add independent network/incident tests.
4. Implement maintained-library WebAuthn ceremonies and official legal-authority provenance verification with human sign-off.
