# Verified local v1.4 source inventory (2026-11-03)

Archive: `my-traveling-lawyer-v1.4-local-handoff.zip`.
Locally recovered project has 42 regular files (not counting ZIP directory entries or test-generated caches). 
The **local** full suite completed: `python -m unittest discover -s tests -q` -> 292 tests passed in 30.704 seconds.

## Missing source to upload to this branch
- src/__init__.py
- src/app.js
- src/assistant_service.py
- src/audit_witness.py
- src/device_challenge.py
- src/engine.py
- src/index.html
- src/legacy_server_DISABLED.py
- src/secure_app.js
- src/secure_engine.py
- src/secure_index.html
- src/secure_server.py
- src/server.py
- tests/test_assistant_v07.py
- tests/test_confidentiality_v08.py
- tests/test_custody_v11.py
- tests/test_device_challenge_v12.py
- tests/test_device_revocation_http_v13.py
- tests/test_device_revocation_v13.py
- tests/test_engine.py
- tests/test_lock_and_minimization_v09.py
- tests/test_milestone_v06.py
- tests/test_research_v14.py
- tests/test_secure_engine.py
- tests/test_secure_http.py
- tests/test_security_v10.py
- provision_demo.py
- recover_demo.py
- My-Travelling-Lawyer-OPEN-ME.html
- CONFIDENTIALITY_DESIGN.md
- DEVICE_STEPUP_V12.md
- PROGRESS.md
- README_V12.md
- RELEASE_V13.md
- RELEASE_V14.md
- ROADMAP.md
- SECURITY_BOUNDARIES_V09.md
- SECURITY_V10.md
- SECURITY_V11.md

## Already on engineering branch
- ENGINEERING_CONTINUITY.md (repository copy; local archive version differs)
- src/research_evidence.py (repository copy; verify byte identity before counting as migrated)
- .github/workflows/experimental-regression.yml (new CI gate, expected to fail closed until full source is present)
- SOURCE_MIGRATION_STATUS.md (this file)
- README.md is on main (placeholder); the application README is still pending migration.

## Strict release rule
Never treat local 292/292 passing as a GitHub CI pass.
Never claim complete source migration, real WebAuthn, verified legal citations, or live 24/7 hosting.
No secrets or real client material in git.
