# Complete fictional offline backup and restore — Windows startup
Users can now click **Back Up Practice Case** to choose an existing fictional database, unused archive name, and masked *owner* code. No archive overwrite; cancel does nothing. The source's existing audited backup service checks authorization, cross-matter scope, pending writes, secret exclusion and record integrity. Archives are plaintext and are strictly fictional-only.

**Restore Practice Backup** picks a saved fictional archive, unused database destination, and requires explicit confirmation. It calls the existing `restore_fictional_pilot`, which checks record integrity and imports no old credentials. The UI displays newly issued codes in a modal window once, not in logs or files. Existing destination is denied before restore. Failure never claims success. Users must keep codes private. No real client data or production use.

This is a customer-facing UI connection to previously implemented recovery functions, not an independently tested full end-to-end real GUI recovery cycle. Focused Windows unit tests cover cancellation, no overwrite, confirmation, errors, code display and service delegation. This does not constitute a signed or Smart App Control accepted release.

Protected PR #110 unchanged; isolated branch `diesel/mtl-customer-backup-ui-20261112`. Windows trusted signing, exact frozen build of latest source, independent security and human use remain separate NO-GO gates.
