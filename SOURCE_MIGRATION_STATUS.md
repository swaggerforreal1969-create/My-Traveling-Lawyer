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

## 2026-11-03 migration increment
- Ten original v1.4 documents have been published and verified individually: CONFIDENTIALITY_DESIGN.md, DEVICE_STEPUP_V12.md, PROGRESS.md, README_V12.md, RELEASE_V13.md, RELEASE_V14.md, ROADMAP.md, SECURITY_BOUNDARIES_V09.md, SECURITY_V10.md, SECURITY_V11.md.
- Main and unrelated repositories were not changed.
- Source Python/JavaScript and tests remain incomplete on GitHub; CI has no verified successful status.
- Archive SHA-256 (local): d31e068154b735424d5eae0d2fb2da7faa9627c223f57ca0e455d23a3e44.
- New local full-suite attempts timed out at 30s and 18s, respectively; historical 292/292 local pass is retained but NOT reproduced this cycle. Last visible verbose test before 18s timeout: test_secure_engine.AuthorizationTests.test_persistent_authorization.
- Next required acceptance: transfer sanitized source/tests to this isolated branch, verify exact manifest and Linux CI. No real WebAuthn or production 24/7 AI is claimed.

## 2026-11-03 verified transfer bridge checkpoint
- Safely staged original source through temporary private file transfer and connected GitHub tool; did not bypass connector safety checks.
- Original application archive has **42 distinct regular files**. Of those, **32 are now represented** on the engineering branch (README.md updated on engineering branch only).
- **Ten source files still missing:** My-Travelling-Lawyer-OPEN-ME.html, src/secure_index.html, src/index.html, src/app.js, src/__init__.py, src/secure_app.js, src/secure_server.py, tests/test_milestone_v06.py, tests/test_engine.py, tests/test_custody_v11.py.
- Some source uploads returned safety blocks. Do not retry in altered/encoded form to bypass these checks. Missing authenticated HTTP server and UI prevent full release acceptance.
- Local regression run **292/292 passed in 25.751 seconds**, using original preserved source; this is not Linux GitHub CI.
- Independently compared eight GitHub blob SHAs against Git blob hashes computed from the archive: src/engine.py, src/secure_engine.py, src/assistant_service.py, src/audit_witness.py, src/device_challenge.py, src/server.py, tests/test_secure_engine.py, tests/test_research_v14.py — **8/8 exact matches**.
- GitHub branch comparison with main: 35 changed files, 36 commits ahead at last pre-checkpoint inspection. Main is unmodified.
- GitHub combined commit status showed no reported successful CI checks. CI must fail closed until complete source is uploaded.
- Next task: resolve blocked files via authorized, security-reviewed publication, then verify all 42 blobs and complete GitHub Linux/Chromium gate. No WebAuthn or hosted 24/7 AI is claimed.
