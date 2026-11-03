# Private attorney multi-matter portfolio — functional experimental milestone

**Status:** local-only experimental user workflow, not production or a legal-deadline verifier.

A fictional attorney with multiple authorized matters can open a **minimal read-only workload summary** in the real keyboard-driven local operator: press `P` at the matter-selection prompt. The summary shows only positional matter numbers, open user-entered task counts, second-human review counts (editor only), and whether each matter is in reader/editor mode. It does **not** display client names, case titles, task descriptions, research excerpts, URLs, record IDs or credentials.

The new `PrivateAttorneyOperator.portfolio()` reuses the existing complete authorized matter/readiness workflow, checks every matter in one local process lock, then rechecks the index before publishing the snapshot. An invalid or revoked matter rejects the entire batch rather than returning a partial multi-client report. The snapshot is an observation only, not a write authorization, deadline determination or durable multi-process lease. A separate user with no accessible matters sees zero counts. Cross-firm or revoked credentials cannot reveal data from inaccessible matters.

`src/private_matter_portfolio.py` includes strict schema, flags and count validation before serializing plain text. No HTML/JS or external calls are made. `tests/test_private_matter_portfolio.py` exercises the real fictional SecureCore, cross-firm isolation, viewer permissions, revoked credentials, changed matter index, malformed or forged counts, no-write semantics, and actual CLI `P` interaction.

All existing original-source and strict 42-file source/hash gates remain unchanged. No independent custody, security signoff, real-client support, filing approval, deployments or permission changes are implied.
