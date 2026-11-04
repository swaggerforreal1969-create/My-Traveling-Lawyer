# My Traveling Lawyer — Independent Recovery and Release Evidence Handoff

**Status: experimental draft; production NO-GO.** No independent custodian connected, no reviewer appointed, no restricted-source reconstruction authorized.

## New historical read-only recovery interface

`CustodyClient.reconcile_historical_read_only(credential, reservation, event_digest, retained_latest, max_events=16)` requires two externally supplied trusted anchors: the client's exact predecessor pin and an independently retained latest pin. The authenticated injected provider implements `read_head()`, `read_head_at(seq)`, `read_event(seq)`. The verifier rechecks every signed intermediate head and committed event across at most 16 contiguous sequences, requires a stable current tip and exact signed reservation/event matching, and refuses ambiguity, replay, rolled-back history, corruption, signer substitution and credential failures.

**Important limit:** v1 signatures do NOT cover the admission nonce. Historical recovery therefore cannot independently attest nonce identity. The result explicitly sets `nonce_authenticated=False`, `independently_custodied=False`, `permits_write_replay=False`, `permits_fence_clearance=False`. The caller must not treat local SQLite or synthetic signed readback as external custody.

## Reproducible fictional acceptance

`python -m unittest discover -s tests -p 'test_historical_custody_readback.py' -q`

`python -m unittest discover -s tests -p 'test_atomic_custody_process.py' -q`

Required hosted workflow: `.github/workflows/experimental-regression.yml` exact published SHA, Tk/Xvfb, SIGKILL, and original source-path/manifest gate unchanged.

## Remaining external acceptance requirements

1. **Restricted source migration:** Obtain each of the original ten inaccessible files from its authorized custodian; verify original hashes with the unchanged 42-file manifest. Do NOT synthesize the missing files. At last verified inspection the gate was 32/42.
2. **Independent reviewer:** Assign and record a qualified reviewer independent of implementation; preserve security PR #27, offline audit PR #36 and Security Issue #1; issue written pass/fail findings and exact tested commit.
3. **Genuine custody provider:** Identify two independently administered custodians, validate authenticated transport, real asymmetric public-key pins, independent monotonic write-once/compare-and-swap retention, signer rotation/revocation, split-view detection, and independently authenticated readback. NO provisioning or egress is authorized.
4. **Nonce-bound receipts:** Before relying on nonce-specific finality in production, specify and review a versioned signed checkpoint envelope that cryptographically commits nonce or nonce digest as well as reservation, event, predecessor and signer identity. Do not silently reinterpret v1 signatures.
5. **Provider failure suite:** Execute lost acknowledgment, concurrent admission, disk crashes, rollback, revoked credential, signer compromise, stale pins, split views, provider outage, bounded latency, and no automatic replay/fence-clearance in approved independent environments.

## Operator release decision

Do not merge, deploy, enable external egress, purchase, alter permissions, use real client data, clear fences or retry uncertain writes automatically. **Production NO-GO** until all original-source integrity, third-party review and genuine custody requirements pass. 
