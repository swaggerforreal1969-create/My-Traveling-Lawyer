# My Traveling Lawyer — preserved engineering continuity
Date: 2026-11-03
Branch: engineering/v1.4-preserved-handoff
Source of truth for local handoff: my-traveling-lawyer-v1.4-local-handoff.zip (preserved conversation artifact; NOT yet committed in full).

## Proven historical baseline
- v1.3 full regression: 244/244 passed in 16.767 seconds (prior run).
- v1.3 HTTP tests: 52 in 4.845 seconds after reducing ThreadingHTTPServer shutdown poll from 0.5s to 0.01s.
- v1.4 adds authenticated matter-restricted research evidence notebook; 48 focused HTTP tests passed.
- v1.4 full regression timed out; do not claim it passes.
- v1.4 source path locally: src/research_evidence.py; routes GET/POST /api/matters/{id}/research in src/secure_server.py.
- Research excerpts are user-supplied, unverified, hash-digested for local integrity; not legal authenticity.
- Standards-based WebAuthn/passkey: NOT implemented. Experimental Ed25519 step-up is not WebAuthn.
- Browser acceptance: NOT verified. 24/7 hosted AI: NOT configured.
- Sovereign Confidential Mode, firm/matter ACLs, and fictional-template outbound AI boundary are required.
- Real client data must not be used. Do not deploy, merge or change permissions.

## Repository reconciliation
- Connected private repository: swaggerforreal1969-create/My-Traveling-Lawyer.
- Main is an initialization-only README at 5a4216d1b23d1eeb2059851a8be657c86f972edf.
- Branch engineering/v1.4-preserved-handoff was created from that SHA.
- This continuity entry does NOT mean the v1.4 code archive has been fully uploaded or verified as GitHub source.

## Next work
1. Publish sanitized full local archive on this engineering branch; verify exact HEAD, source tree and CI.
2. Diagnose v1.4 full-suite regression timeout in isolation, without assuming HTTP fix applies to all tests.
3. Implement maintained WebAuthn RP/origin-bound registration/assertion verification with genuine browser acceptance, then secure sessions.
4. Add verifiable research source retrieval with attorney approval; independent audit custody; monitoring for 24/7 AI.

Planning only: M1 90%, M2 62%, M3 40%, M4 20%, M5 0%; overall stated ~42% (milestone arithmetic unweighted average 42.4%). Not production readiness.

## Acceptance engineering increment — 2026-11-03
- Branch preserves 32/42 archived application files; 10 missing paths and digests documented in BLOCKED_SOURCE_ACCEPTANCE_2026-11-03.md. Migration incomplete.
- SOURCE_V14_SHA256.json records all 42 original SHA-256 hashes. tools/verify_source_manifest.py rejects missing, symlinked, modified, and traversing paths. tests/test_source_manifest_gate.py: 6/6 local tests passed. Fresh original extraction: 42/42 integrity matched; deliberate tamper rejected.
- CI workflow runs the immutable hash check before full Linux regression and installs cryptography. It cannot pass until all files are present and exact hashes reconcile.
- Chromium launched through Playwright, but navigation was blocked by ERR_BLOCKED_BY_ADMINISTRATOR. No genuine browser acceptance claimed.
- No successful GitHub CI observed; WebAuthn verifier and hosted 24/7 AI are not yet available.
- Temporary Library transfer copies removed. Main, original archive, and unrelated engines preserved.
- Next: security-approved publication of 10 missing originals, complete exact-SHA Linux/browser gate, then genuine passkeys and attorney workflows.
