# v1.4 source reconciliation and safety-review boundary — 2026-11-03

## Immutable source acceptance (verified)
Preserved source baseline: original v1.4 archive containing 42 application paths.
On the isolated engineering branch: **32 of the 42 original paths are present and ALL 32 match their archived Git blob SHA-1 byte-for-byte**.
This reconciles:
- 12 original top-level documents (including README.md and ENGINEERING_CONTINUITY.md)
- 10 original application Python scripts (including the assistant, signed-device and audit modules)
- 10 original regression test modules

An earlier transfer via extracted text stripped one final newline from 10 documents; the missing newline was repaired and each final blob hash reverified. The working continuity record was preserved separately at docs/ENGINEERING_CONTINUITY_LIVE_2026-11-03.md. Never edit the manifest-controlled originals again.

## Still missing: 10 of 42
See BLOCKED_SOURCE_ACCEPTANCE_2026-11-03.md for exact path list and original SHA-256 fingerprints. Their GitHub upload was previously blocked; no bypass/alternate encoding was used.
- The standalone HTML demo has six innerHTML assignments; some escaped dynamic text, and identifier interpolation also requires source/provenance review.
- First-pass static scan of ten missing files found no direct eval(, exec( or document.write call.
- This is not security approval, penetration testing, or a determination that files are safe to publish.
- Obtain independent security/policy approval before attempting publication of blocked files; do not rely on a tool refusal as a diagnosis of a specific vulnerability.

## Test and CI evidence
- Fresh original local regression: 292/292 tests passed in 19.037 seconds (2026-11-03).
- Local integrity verifier: 42/42 archived bytes accepted; deliberate modification rejected; 6/6 separate verifier unit tests passed in prior increment.
- GitHub Linux CI: success NOT verified. 42-path fail-closed workflow will intentionally reject missing source.
- Browser acceptance: NOT verified due restricted Chromium navigation.
- Genuine WebAuthn, attorney-verified legal retrieval, and operational 24/7 hosted AI are NOT implemented.

## Next acceptance actions
1. Obtain independent security review approval of the remaining ten original files, with findings documented. Do not bypass blocked uploads.
2. Publish only through an authorized, approved channel on this existing engineering branch.
3. Verify all 42 original hashes against GitHub blobs and the immutable SHA-256 manifest; preserve edited continuity outside manifest paths.
4. Run exact-SHA Linux CI and real browser acceptance in a permitted environment.
5. Advance operational attorney features only after the source gate. Never use real client data or deploy without authorization.
