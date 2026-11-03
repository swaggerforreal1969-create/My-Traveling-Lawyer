# Migration gate — 2026-11-03

## Verified locally
- Original preserved v1.4 ZIP extracted without errors.
- Sanitized source inventory: **42 regular files**, **160,764 bytes**, **25 Python files**, **13 test files**.
- Full local `python -m unittest discover -s tests -q`: **292 passed in 23.018 seconds** in a separate fresh extraction.
- This result is **local only**; it is not a Linux GitHub Actions result.

## Current GitHub branch status
- Branch: `engineering/v1.4-preserved-handoff`
- `main` remains initialization-only and has not been merged.
- `ENGINEERING_CONTINUITY.md`, `src/research_evidence.py`, and fail-closed CI workflow are present.
- **Full 42-file source tree not yet committed**; do not mark migration complete or enable production.
- GitHub Actions needs the missing required source before its regression job can pass; no successful CI has been verified.

## Blocker and immediate objective
The available GitHub connector accepts file content, but cannot access local ZIP bytes directly. The execution container cannot resolve github.com, so it cannot git push. A supported cross-environment file transfer or manual authenticated upload is needed to publish the remaining source. Never copy a PAT or private credentials into chat or source.

## Product safety
- Signed-device step-up is NOT standards-based WebAuthn.
- Research notebook stores unverified source excerpts; no live legal authority verification.
- 24/7 live AI hosting, independent security review, browser acceptance and real-client-data authorization remain open.
- Preserve all originals and other projects; use fictional data only.
