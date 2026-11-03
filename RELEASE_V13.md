# v1.3 local security and reliability increment

- Reduced HTTP-suite test overhead without disabling any test.
- Added revocation for experimental device verification keys and associated challenges.
- Added focused tests and complete HTTP endpoint validation for revocation.
- Kept all existing confidentiality and AI controls; no user secrets included.
- Work is **local only** and not published to GitHub. No real passkey login, hosted AI, encrypted client records or production deployment exists.
- See ENGINEERING_CONTINUITY.md for reproducible verification and blockers.