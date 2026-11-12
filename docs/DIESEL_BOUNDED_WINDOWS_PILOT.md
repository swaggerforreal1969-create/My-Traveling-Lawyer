# Diesel bounded Windows pilot — one-shot acceptance

## Purpose
Run an isolated, nonproduction native Windows build and three-button smoke acceptance without requiring another user PC session. This is a deterministic, finite CI test pilot, **not** an always-on self-coding agent.

## Frozen baseline
- Protected PR #110 SHA: `c0b94e0eae172f3ea1deeb34800797b13edbcc8e` (do not change).
- Windows candidate before pilot: `b072ef2742192fe3c97d8b15e73eee00e8bc5c34`.
- Existing accepted customer GUI tests: 58/58 from prior checkpoint (reuse; do not rerun).
- Distinct, private pilot branch: `engineering/diesel-contained-windows-pilot-20261112`.

## One-shot gates
1. Push on exact isolated branch triggers a single workflow; **no cron schedule or auto-push**.
2. Read-only scoped source/Store-preparation acceptance: 3+3 tests.
3. Actual Tk button callbacks invoked (Create → save dialog cancelled; Open → open dialog cancelled; Close → root destroyed) with strict 10-second watchdog and no fictional record written.
4. Build frozen Windows x64 executable using a fixed PyInstaller version, verify import closure, hash EXE, require unsigned status to be reported accurately.
5. Launch frozen EXE as a real Windows process with a native GUI window.
6. Retain only a sanitized proof JSON in GitHub. No unsigned app is uploaded or distributed from this pilot.
7. Up to 3 *test attempts* for transient GUI failures. **No automatic code modifications, no repeating failed CI, no external calls.**

## Safety hard stops
- Missing GUI import, failed test, unexpected signature, missing EXE, failed startup → DENIED, **STOP**.
- Smart App Control acceptance, Store/CA signing, independent review, real customer operations remain UNRESOLVED.
- No protected merges, privileged actions, credentials, payments, restricted source, real client data, or deployment.

## Acceptance
Pilot success means exactly one bounded GitHub Actions run with all gates PASS and attributable exact-SHA evidence. It does *not* mean autonomous developer capabilities exist. Future recurring execution requires a separate explicit approval after reviewing this pilot.
