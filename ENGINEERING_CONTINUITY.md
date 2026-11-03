# My Traveling Lawyer engineering continuity — v1.3 (2026-11-03)

## Local checkpoint
- Original v1.2 archived without modification: `/mnt/data/my-traveling-lawyer-v1.2-github-ready.zip`.
- Worktree based on v1.2. Separate from Diezel and Koontcee; no main branch or production change.
- HTTP regression timeout root cause: `ThreadingHTTPServer.serve_forever` used its inherited 0.5s shutdown polling interval; repeated setup/teardown increased aggregate wall time. APIServer now sets the default poll interval to 0.01s. Existing HTTP integration suite: 52 tests, 4.845 seconds measured after correction.
- Demo device-key revocation added: POST `/api/device/revoke` requires a valid current bearer credential matching the key owner; invalidates the key and deletes outstanding challenges in the same DB transaction, records an audit event. Cross-firm and stale-key revocation denied. The revocation API has an end-to-end HTTP regression test.
- Full final suite: `python -m unittest discover -s tests -q` => 244 tests passed in 16.767 seconds. Python compilation and package integrity to be recorded separately.
- Browser acceptance: NOT PASSED. Playwright package installed, but Chromium executable unavailable in this runtime. Earlier environment denied localhost.
- Production WebAuthn/passkey enrollment/login: NOT IMPLEMENTED. `device_challenge.py` remains experimental Ed25519 step-up, not WebAuthn. Do not mistake it for browser-origin-bound passkeys.
- 24/7 external AI: NOT HOSTED. Confidential case prompts remain blocked for external AI. Fictional data only.

## GitHub status
- Connected GitHub repository searches returned no accessible private `My-Traveling-Lawyer` repository.
- No branch, commit SHA, CI evidence, or successful source publication. Next dependency: create private `My-Traveling-Lawyer` in the connected GitHub account and grant connector access, then publish sanitized source on `engineering/continuity-v1-3` and verify branch SHA.
- Do not alter any frozen originals or other repositories.

## Next engineering priority
- Integrate a **maintained** WebAuthn verification library and a complete registration/authentication ceremony: trusted HTTPS origin/RP ID, challenge expiry, credential ID and signature validation, user verification, one-time replay defense, counters/backup behavior, and session issuance after verified assertion. Enforce staff/matter permissions and authentication recovery carefully.
- Obtain permitted genuine browser acceptance on a trusted environment. Configure independent audit checkpoint custody, encryption at rest and hosting before real client data. 
- Five subjective milestone estimates unchanged: M1 90%, M2 62%, M3 40%, M4 20%, M5 0%; reported overall planning estimate 42%. This is not an audited completion percentage.


## v1.4 local continuation (2026-11-03)
- GitHub repository searches again returned no connected private My-Traveling-Lawyer repository; no branch/commit/CI.
- Added authenticated per-matter research evidence notebook in src/research_evidence.py and GET/POST /api/matters/{id}/research. Role-scoped; HTTPS URL validation; source excerpts user-supplied and explicitly unverified; no outbound retrieval or AI transfer.
- Focused research test module: 48 tests passing, including inherited HTTP tests. Full suite execution timed out during this turn and is NOT verified for v1.4.
- Standards-based WebAuthn remains unimplemented. Neither webauthn nor fido2 packages are available locally. Do not claim passkey login or browser acceptance.
- Sovereign Confidential Mode and opt-in fictional-template AI preserved. No production deployment.