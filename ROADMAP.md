# Product roadmap and release gates

## M1 — Experimental core (this package)
- [x] Matter creation, notes, tasks, deadlines, time entries
- [x] Atomic SQLite transactions and replay-safe idempotency keys
- [x] Timezone-aware timestamps and versioned task completion
- [x] Local-only mobile-responsive demo interface
- [x] Internal audit-chain integrity checks
- [x] 19 automated domain tests passing
- [ ] Independent audit custody / authentication (not yet)

## M2 — Trusted identity boundary
Authentication, firm and matter-scoped authorization, permission-denial tests, encrypted persistence, audit custody and recovery; no real data until security review.

## M3 — Daily travel workflow
Encrypted offline access, calendar integrations, voice capture with permissions, secure file attachments and document scanning, secure sync and conflict recovery.

## M4 — Legal intelligence with verified sources
Jurisdiction-aware rules, law and citation provenance, no fabricated authorities, expired-source flags, explicit attorney review, documented AI data boundaries.

## M5 — Firm pilots and commercialization
Legal ethics and privacy assessment by jurisdictions, pen test, accessibility evaluation, integration tests, real attorney field studies, billing model and vendor contracts.

## Acceptance policy
No client data, public release, AI-driven legal filing, production deployments, real billing or external integrations without deliberate approval and validated release gates.

### v0.3 experimental engineering increment
- Completed: separate testable firm/matter authorization core and adversarial authorization unit tests.
- Not completed: integration into mobile UI, authenticated HTTP entrypoint, protected persisted confidential data, encrypted offline sync, external audit custody or CI publication.
- Release gate: no real client data, no server deployment, no production access.

## v0.4 milestone: authenticated API integration
- [x] Single authenticated default HTTP entrypoint; historical unsecured server moved out of normal entrypoint.
- [x] Mobile browser interface with ephemeral test-token login, matter list/create and matter note list/create.
- [x] SecureCore grants enforced by API; viewer read-only, cross-firm isolation, revocation, forged tokens, stale grant and origin/Host rejection covered by tests.
- [x] Persistent SQLite reopening check following token revocation.
- [ ] Make admin provisioning a secure identity integration rather than test-only CLI.
- [ ] Design audited real-user authentication, expiry/MFA and independent custody before processing real legal data.
- [ ] Add broader concurrency and failure-injection tests, independent code review, browser e2e and threat model.

## v0.5 milestone and progress tracking (2026-11-02)
Scoring is an **engineering estimate against the full roadmap**, not an objective measure of deployability or a guarantee of schedule. Scores will advance only after explicit acceptance evidence.

| Area | Current estimate | Acceptance still required |
| --- | ---: | --- |
| M1 experimental core | 90% | Stable and documented acceptance, reproducible installation |
| M2 trusted security | 45% | MFA/IdP, encryption at rest, independent custody, secure recovery, pen test |
| M3 mobile travel workflow | 20% | Secure offline mode, scanning, calendar sync, cross-device recovery |
| M4 verified legal intelligence | 0% | Authoritative legal sources, citations and review gates |
| M5 pilot and launch | 0% | External reviews, attorneys testing, compliance and commercialization |

**Simple average: 31%.** This intentionally gives equal weight to the five milestones; it does not mean the software is 31% safe for law firm use.

v0.5 features: 12-hour test credential expiration (including migration of earlier credentials), authenticated rotation that revokes the old token in the same database transaction, hash-linked local audit records with verification, authenticated due-date/task creation, per-user and per-firm scoped courtroom briefing, and UI integration. Deadline values are user-supplied and not calculated under court rules. Local audit hashes are not independent or rollback-resistant. Credential rotation is not independent lost-credential recovery.

**Evidence:** 89 Python unittest executions passed (includes inherited duplicated integration cases), Node JS syntax passed. Browser smoke attempt was **blocked by local browser policy** (`net::ERR_BLOCKED_BY_ADMINISTRATOR`); no browser end-to-end acceptance should be claimed. No CI, cloud service, external audit, TLS, production access, or GitHub commit was created or verified.

## v0.6 checkpoint
Local test-only credential recovery is a CLI procedure using pre-issued one-time recovery codes, not a user-facing internet workflow. All user credentials and codes are invalidated upon successful recovery. New task completion uses optimistic concurrency and authenticated matter permissions, integrated with the browser dashboard. 102/102 local automated tests passed; JavaScript syntax checked. Browser end-to-end test was attempted, but the Playwright Chromium executable was unavailable. Retain v0.5 immutable artifact; v0.6 is a separate ZIP. Do not use real client data.

## v0.7 24/7 AI requirement (new first-class product capability)

* Always-visible attorney AI assistant in mobile UX.
* Local no-provider safety response and explicit provider outage state, no false uptime promises.
* Authenticated and authorized read-only assistant route, per-question opt-in to send fictional prompts.
* Approved, server-side-configured HTTPS external provider; exact host allowlist;
  no redirect and no client matter context transmission by default.
* Next: verify production provider and data processing policy, source-grounded legal research,
  consent/redaction, immutable prompt access logs, latency/availability SLOs and incident handling.
* No autonomous filing, contacting clients, editing records or legal advice without lawyer approval.

## Confidentiality release blockers
Managed device encryption, phishing-resistant MFA, stronger authentication and session lifecycle, secure browser test on actual devices, vendor agreements/no-training guarantees, jurisdictional ethics counsel, physical privacy guidance, independent audit custody, secure backup and red-team review.

## v0.9 priority after lab gate
Implement true passwordless/passkey reauthentication, server-enforced idle/session timeout, encrypted data with protected keys and secure backup, signed independent audit checkpoints, mobile accessibility testing, and private AI provider assessment. Keep the live 24/7 assistant as a release requirement; never describe the local canned fallback as a real staffed or live generative AI service.