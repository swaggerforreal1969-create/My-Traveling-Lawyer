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
