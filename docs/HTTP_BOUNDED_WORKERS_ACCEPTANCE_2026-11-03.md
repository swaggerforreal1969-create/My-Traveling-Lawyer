# Experimental localhost readiness HTTP capacity and idle timeout — 2026-11-03

## Verified context and permission boundary
- Independent-review Issue #1 was checked before editing: **OPEN, unassigned, zero comments**. No independent disposition authorizes ten blocked v1.4 original files; original-source migration remains **32/42**.
- Starting exact checkpoint: `039a6fd602d088301d84733a74af8f2c7a882f2d`. No GitHub Actions run or passing combined status was associated with it.
- Modified ONLY separately authored experimental `src/readiness_loopback_http.py` and `tests/test_readiness_loopback_http.py` on `engineering/v1.4-preserved-handoff`. Frozen original files, `main`, Koontcee, Diezel, permission controls, external AI egress, production deployment and purchases unchanged.

## Functional improvement
- The localhost-only HTTP server now uses `BoundedSemaphore` to cap simultaneously serviced connections (default eight, bounded configuration 1–16). Excess sockets are closed **before header parsing or ticket consumption**, instead of allocating unlimited worker threads.
- Every accepted socket receives an idle-read timeout (default two seconds, configurable only within 0.5–5 seconds). A stalled, partial-header client cannot retain a worker indefinitely.
- The connection permit is released in a `finally` handler even after request exceptions; initial thread-dispatch errors also release permits. No public listening address, ticket issuance endpoint or persistent credentials were added.
- Three adversarial real-socket tests: saturating a one-slot server with partial headers denies excess requests without using a valid preview ticket; closing the idle client restores capacity and permits a subsequent authenticated preview; timeout automatically releases the slot; unsafe capacity/timeout configuration fails closed.
- Tests use fictional account and matter records exclusively. This is an **experimental loopback server**, not production-ready ingress or a remote mobile service. A Python-level timeout does not prove protection against all slow-client or kernel-level resource exhaustion techniques.

## Executed acceptance
- `python -m unittest tests.test_readiness_loopback_http -q` → **31/31 PASS in 18.821 seconds**.
- First complete regression attempt had no final result within the container execution wrapper and was treated as **incomplete**, not a pass.
- Follow-up verbose complete regression log printed `Ran 515 tests in 39.245s\nOK` and completed its process. **515/515 PASS** against the locally assembled v1.4 original source and previously published isolated components.
- `python -m compileall -q src tests` → PASS.
- Committed file blobs match locally tested `git hash-object` values:
  - `src/readiness_loopback_http.py`: `be8cfd20c82422fe96e68f212e7eceacf02f7b46`.
  - `tests/test_readiness_loopback_http.py`: `df8662cde97e7e99f82a5deb4902d02dbbced652`.

## Outstanding acceptance — not passed
- Existing genuine Chromium/Playwright browser navigation was previously blocked by `ERR_BLOCKED_BY_ADMINISTRATOR`. No authorization to bypass and **no newly passing Chromium test**.
- No exact-SHA passing GitHub Linux CI. The original source integrity gate is intentionally incomplete at 32/42.
- Genuine maintained-library WebAuthn, independently authenticated official legal sources, external independent custody, and operational 24/7 confidential AI remain unfinished.

## Next practical engineering milestone
- Obtain a named independent reviewer and decision on Issue #1. Do not alter, split, or bypass the ten blocked original paths.
- Once authorized, complete all 42 original-file fingerprints, execute full exact-SHA GitHub Linux gate and genuine same-commit mobile Chromium acceptance on an allowed runner, retaining browser failure/screenshot evidence.
- Continue isolated real attorney workflow integration and adversarial testing while review remains open.
