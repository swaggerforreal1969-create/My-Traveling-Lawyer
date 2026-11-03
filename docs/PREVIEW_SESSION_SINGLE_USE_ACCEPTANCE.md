# Single-use, matter-bound private preview sessions — experimental acceptance

## Implementation
- src/preview_session.py adds PreviewSessionBroker, a standalone local adapter around the real MobilePreviewGateway.
- A 256-bit random, single-use ticket is issued only after authenticating the existing demo bearer credential and authorizing that credential to the requested firm/matter.
- The ticket is scoped to credential hash, user, firm, matter, expiry and consumed state; the SQLite table stores only SHA-256 hashes, never plaintext tickets or bearer tokens.
- Ticket TTL is bounded to 1–120 seconds (default 60); expiry uses real UTC time.
- Consumption checks active bearer credentials and matter ACL again, then atomically marks the ticket consumed before rendering. A failed render burns the ticket. Concurrent and post-restart replays fail closed.
- Ticket possession alone does NOT authorize access. No HTTP listener, network provider, real client data, or WebAuthn implementation was added.
- Note: This SQLite-based demonstration is not an independent, distributed, rollback-resistant session service. Store backup/restore and shared deployments need separate treatment.

## Verified local test evidence
- tests/test_preview_session.py: **15/15 passed** in 0.704 seconds.
- Complete local suite assembled from preserved original v1.4 and the previously published actual real-chain, authority-review, matter-brief, mobile renderer and gateway modules, plus the new broker: **353/353 passed** in 13.316 seconds.
- Python compileall for src and tests passed.
- The new code handles same-ticket concurrency (only one succeeds), replay, restart persistence, expired tickets, revoked credentials, wrong credential, wrong matter, cross-firm access, viewer access without write, bad input, rejection on render failure, token secrecy in stored records, and no outbound socket connection.
- GitHub source blob confirmed against local git hash-object:
  - src/preview_session.py: a0b4d800f2694bb22f587d76f2784b1d4d847a96
  - tests/test_preview_session.py: a3908e28ed11b351ae8fb65a662995e95863ecfb

## Immutable source boundary / incomplete acceptance
- Issue #1: open, unassigned, zero reviewer comments at inspection, **no independent security approval**. Do not bypass platform safety checks.
- Frozen original v1.4 migration remains **32/42**, with ten unpublished files and immutable SHA-256 gate intact.
- GitHub Linux CI success, real HTTP/browser acceptance, real WebAuthn and 24/7 hosted AI are **not verified**; this pass is local and in-process only.
- Human research-review flags are assertions, not verified legal citations.
- No modifications to main, preserved original v1.4 files, Koontcee, Diezel, production permissions or billing.

## Next
1. Named independent reviewer assesses Issue #1; after approval publish blocked originals unchanged or create distinct remediated version, then complete all source hashes and exact-SHA Linux CI.
2. Run genuine browser and HTTP session/denial acceptance in an approved environment.
3. Add real maintained-library WebAuthn registration/assertion ceremony and verified official legal research, using fictional fixtures.
4. Build operational 24/7 AI monitoring with explicit Sovereign Confidential Mode control; no client data until authorized.
