# HTTP request ambiguity fail-closed hardening — 2026-11-03

## Context and issue gate
At milestone start Issue #1 was OPEN, unassigned with ZERO comments. No independent approval exists for the ten originally blocked v1.4 files. Frozen original source migration remains 32/42. We changed only previously published, separately authored experimental HTTP handler and its test module on engineering/v1.4-preserved-handoff; no changes to main, Koontcee, Diezel, frozen archives, blocked uploads, provider integrations, permissions or production deployment.

## Functional security increment
The authenticated local-loopback readiness HTTP adapter previously used `self.headers.get()` to select Host, bearer token and preview ticket. Duplicate HTTP header fields can be interpreted inconsistently by different parsing layers, potentially creating a request-confusion risk. The revised `_headers_unambiguous()` checks all parsed fields before evaluating matter access or consuming a one-time ticket.
- Rejects **duplicate header field names case-insensitively**, including Host, Authorization and X-Preview-Ticket, plus arbitrary duplicate names.
- Rejects forwarded/proxy routing fields (`Forwarded`, `Proxy-Authorization`, `Proxy-Connection`, `X-Forwarded-Host`, `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Original-URL`, `X-Rewrite-URL`) and `Expect`.
- Caps total header count at 32, individual header names at 64 characters and values at 2048, with ASCII control-byte rejection. This remains an **experimental localhost** server, not hardened production ingress.
- All ambiguous requests return 403 with empty body; tests establish that such denial does **not burn** an otherwise legitimate preview ticket.

## Executed acceptance evidence
- New real-socket adversarial tests: **6** (duplicate Authorization, ticket and Host, proxy/forwarding fields, arbitrary duplicate field and header-count flood).
- `python -m unittest tests.test_readiness_loopback_http -q` → **22/22 PASS**, 12.126 seconds.
- `python -m unittest discover -s tests -q` → **506/506 PASS**, 33.841 seconds. The command wrapper signaled timeout **after** unittest printed the successful summary; treat that environmental wrapper condition separately from the actual test-result output.
- Separate `python -m compileall -q src tests` → PASS.
- Exact locally tested Git blobs successfully published:
  - `src/readiness_loopback_http.py` → `e1a083da0eb9a92b7e916b6dd3437f9faa636a60`
  - `tests/test_readiness_loopback_http.py` → `269bc60a46e7545c2bd764aaa6919ae17a9975f3`

## Blocked/unfinished gates
- Authentic Chromium browser navigation was previously attempted using committed `tests/acceptance_chromium_readiness.py`, but returned `ERR_BLOCKED_BY_ADMINISTRATOR`. **Do not claim browser PASS**; no administrator restriction was bypassed. This increment did not execute a new passing browser acceptance.
- GitHub exact-SHA Linux CI remains unverified; original source integrity gate remains incomplete at 32/42 until approved.
- Genuine WebAuthn maintained-library registration/assertion, independently verified official legal sources and operational 24/7 AI are not implemented.
- This is local fictional-only testing; no client data, spending or external AI egress.

## Next milestone
Obtain independent reviewer disposition in Issue #1. With approval, complete all original 42 hash checks, run exact-SHA Linux CI and authorized same-commit Chromium. Until then, prioritize real fail-closed functionality, test HTTP request smuggling/keep-alive behavior in an approved environment, and preserve each negative gate as evidence.
