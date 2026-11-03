# Offline trust rotation: exact proposal reservation and limitations

**Status: experimental local-only acceptance. Not independently approved.**

This milestone adds `src/offline_rotation_ledger.py` as a *local* SQLite reservation layer around the existing dual-signature, operator-gated `OfflinePinRotationPreflight`. It does not rotate any keys, update trusted checkpoints, contact a network endpoint, or authorize release.

## Controls

- Each candidate manifest must first pass the old-signature, new-signature, current pinned predecessor, time window and operator-approval callbacks.
- A single `BEGIN IMMEDIATE` transaction reserves the signed manifest digest, unique 256-bit rotation ID and unique predecessor digest, with `synchronous=FULL`. Conflicting or replayed rotation proposals cannot both be recorded by cooperating local processes.
- Missing/corrupt pre-existing storage rejects ordinary reopening, without silent re-creation. `create=True` is an explicit **test bootstrap** capability: it is not proof against malicious deletion followed by unauthorized reinitialization.
- Successful reservation returns a proposal for *independent manual review*; it cannot advance the signer pin. There is no auto-clear/retry/production activation.
- Rejected validation does not consume the reservation identity. Valid proposals cannot overwrite a previously recorded conflicting proposal.

## Adversarial coverage

`tests/test_offline_rotation_ledger.py` tests replay after restart, changed signer proposals, two simultaneous threads, two spawned processes, wrong predecessor, absent operator approval, damaged/missing local ledger and the absence of an automatic apply/clear path. These demonstrate cooperative local concurrency only. They **do not** demonstrate independently durable, rollback-resistant history.

## External dependencies

Real production acceptance requires a named independent security reviewer under Issue #1, authorized inspection of ten protected originals (source gate 32/42), independently operated nonrollback custody and key administration, independently held history pins, actual trusted-time and revocation validation, a dual-operator release decision and full exact-source-SHA gates. No reviewer, external authority or security signoff is implied by this prototype.

The test-only ledger is **not wired to the attorney write path**. All existing write fencing and read-only recovery requirements remain unchanged. No `main` merge, deployment, purchase, permission change, external egress or production activation.
