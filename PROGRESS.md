# v1.1 provisional engineering status

Milestones remain unchanged pending authentic browser acceptance, deployed independent custody, and production identity controls: M1 core 90%, M2 identity/security 62%, M3 mobile 40%, M4 AI/legal research 20%, M5 pilot/launch 0%. Rounded mean 42%. These are planning estimates, not certification.

New: missing audit-sequence rejection and fail-closed configured external Ed25519 witness verification on API startup and every API call. No independent trust service has been provisioned. 24/7 hosted AI remains unavailable. See SECURITY_V11.md for limits and exact test evidence.

Verified final v1.1 gate: `python -m unittest discover -s tests -q` -> 217/217 passed in 71.565 seconds, exit 0. Focused custody v1.1 -> 11/11 passed. Baseline v1.0 rerun -> 206/206 in 70.862 seconds. Python compilation and JavaScript syntax pass. Chromium/Playwright attempt failed with `ERR_BLOCKED_BY_ADMINISTRATOR`; no authenticated browser acceptance claimed. No live AI provider, off-host custody or passkeys provisioned.
