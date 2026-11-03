# Private mobile preview gateway — experimental acceptance

## Implementation
- `src/mobile_preview_gateway.py` composes the existing `MatterBrief.prepare(token, matter_id)` authorization boundary with the offline HTML renderer `render_mobile_brief()`, returning a structured **in-process** response with defensive security headers. No HTTP listener, route, server, WebAuthn, or deployment was added.
- Refuses missing/invalid token shapes, invalid matter identifiers, naive timestamps, mismatched matter IDs, non-string/empty/oversized HTML, and propagates denied credentials without rendering.
- Configures `Cache-Control: no-store, no-cache, must-revalidate, private`, `X-Frame-Options: DENY`, no-referrer policy, `nosniff`, a restrictive Content-Security-Policy, and correct byte-oriented `Content-Length`.
- Does not store the bearer token, call a provider, send a network request, or claim verified legal authority/deadlines. The renderer still requires an **authorized matter briefing**; this adapter is not, by itself, production authentication.

## Evidence
- Local isolated focused gateway tests: **16/16 passed**, `python -m unittest discover -s tests -q`.
- Fresh v1.4 ZIP regression plus offline renderer and gateway tests: **322/322 passed in 11.102 seconds**.
- The 322-test suite includes v1.4 (292), mobile renderer (14), and gateway (16). A **test-only stub** was used to satisfy the MatterBrief module import; the gateway unit tests use an injected fake briefing with simulated authorization. Therefore this does **not** verify the full real matter-brief + authority-review integrated chain, which previously passed separate tests.
- Both new GitHub blobs matched locally tested byte hashes: `src/mobile_preview_gateway.py` = `dd482f092485322e1df169f2db341664c390e232`, `tests/test_mobile_preview_gateway.py` = `fb6dc4f9cb293ee36e285ccd133ac5aa853284a2`.
- GitHub Actions Linux CI: not passed/verified; the 42-file fail-closed migration gate remains active.
- No authentic browser acceptance. No production authentication, hosting, AI, real legal-source verification or retained client information.

## Safety and continuity
- Independent review Issue #1 is still **open, unassigned, zero comments** at the start of this cycle.
- Original source migration stays **32 of 42 original v1.4 files**, all existing original blobs previously verified exact.
- Ten blocked original files, main, Koontcee, Diezel and the frozen archives were not modified.
- Do not publish modified versions of blocked originals or bypass platform safety checks.

## Next engineering acceptance
1. Independent security reviewer for Issue #1 must approve or request repairs to the ten unpublished original files; no self-granted approval.
2. Complete 42/42 source hashes and exact-SHA Linux CI, using a single integrated source tree including authority_review, matter_brief, mobile renderer and gateway.
3. Test actual authenticated session denial, real HTTP response and browser privacy with fictional data in an authorized environment.
4. Separately implement maintained-library WebAuthn registration/assertion and authoritative legal research provenance; 24/7 hosted AI remains mandatory but not operational.
