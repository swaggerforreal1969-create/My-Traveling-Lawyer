# Independent reviewer — protected originals offline hash-verification handoff

**Classification: private, offline, authorized-reviewer use only.** This utility does not grant access to protected files, attest an independent review, approve any release, replace original source publication, or make the strict 42-file release gate pass.

## Minimal approved offline procedure

1. The source owner appoints a qualified independent security reviewer under [Security Issue #1](https://github.com/swaggerforreal1969-create/My-Traveling-Lawyer/issues/1), confirming independence and review scope. Authorize controlled local access to the **owner-retained** v1.4 original archive, not a GitHub upload or a reconstruction.
2. The reviewer independently authenticates the immutable `SOURCE_V14_SHA256.json` against an owner-retained trusted digest **through a separate approved channel**. This tool alone cannot authenticate a manifest or establish chain of custody.
3. On the reviewer's authorized offline computer, with the archive mounted read-only, run:
   ```sh
   python tools/offline_restricted_source_audit.py --archive-root /approved/private/v14 --manifest /approved/verified/SOURCE_V14_SHA256.json
   ```
   It reads the ten original files in place, checks their SHA-256 against the independent manifest, and prints *only* statuses, canonical file names and the manifest digest. It never copies, displays, uploads, modifies or imports the original source. Redirect stdout into the reviewer's **approved local evidence store** if retention is authorized.
4. For each original, the independent reviewer performs actual security analysis (authorization, HTTP boundaries, secrets, browser injection, custody and adversarial tests), documents findings and permitted remediation. A hash match **does not** mean security approval.
5. The reviewer signs or otherwise independently attests the audit report via an approved process, linked to reviewer identity, actual inspected sources, reviewed SHA, scope, findings and explicit decisions. This tool deliberately does not create that attestation.
6. The existing hosted 42-file gate remains unchanged and red until all 42 originals are verifiably present in an **authorized** source environment and their unchanged v1.4 hash checks pass. An offline report cannot replace or bypass the hosted release gate.

## Failure handling and restrictions

Missing files, symlinks, hashes that differ, path traversal or malformed manifests fail closed; CLI exits nonzero if any protected file is absent/changed. The printed JSON includes `reviewer_security_approval:false` and `hosted_42_file_release_gate_passed:false` unconditionally. Synthetic unit tests use invented, nonprotected files; **no frozen original was retrieved or copied**.

**No main merges, release, production activation, purchases, permission changes, public upload or external AI egress.** Real independent security review and separately administered rollback-resistant custody remain external dependencies.
