# My Traveling Lawyer — AI source access index (restricted-source safe)

**Owner goal:** A durable, easily discoverable entry point for ChatGPT, GitHub-connected engineering agents, Python tooling, and other separately authorized AI assistants. This index is **metadata only**. It confers no permission to access, export, publish, or execute restricted source.

## Canonical locations

| Asset | Where to find it | Authorization / status |
|---|---|---|
| Original V1.4 frozen ZIP | Owner's **ChatGPT Library** at `/my-traveling-lawyer-v1.4-local-handoff.zip` (Library file ID `file_0000000084f08212a1f2631a9fcdca62` in the original ChatGPT environment) | Original ZIP **not stored in GitHub**; ChatGPT Library access is account/connector specific |
| Original manifest | Repository `SOURCE_V14_SHA256.json` and source ZIP's corresponding original file identities | 42 expected file SHA-256 values; checkpoint may still only expose 32 original files |
| Modern published engineering checkout | Private repository `swaggerforreal1969-create/My-Traveling-Lawyer`, isolated checkpoint `b45dbc9eb3d75ac287d2ac371ba4170c15ca90a4` | Do not assume a local folder path on any machine |
| Release/customer backlog | Private GitHub Issue #111; draft PR #110; supporting private evidence notes | NO-GO; requires independent security and separate restricted-source authorization |
| This index | `docs/AI_SOURCE_ACCESS_INDEX.md` on isolated branch `engineering/mtl-ai-source-index-20261114` | Metadata-only, safe to read for separately authorized agents |

## Source identity and recovery integrity

* Frozen ZIP SHA-256: `d31e068154b735424d5eae0d2fb2da7faa9627c223f57ca0e4550e45d23a3e44`.
* Prior private recovery report: all **42/42** original V1.4 paths matched `SOURCE_V14_SHA256.json`.
* Ten original paths withheld from the referenced GitHub checkout: `My-Travelling-Lawyer-OPEN-ME.html`, `src/__init__.py`, `src/app.js`, `src/index.html`, `src/secure_app.js`, `src/secure_index.html`, `src/secure_server.py`, `tests/test_custody_v11.py`, `tests/test_engine.py`, `tests/test_milestone_v06.py`.
* Authentic `src/secure_server.py` SHA-256: `644a8674a3e3d7e1e54187f2ea4e2aab259344332b800a9c03d788c8eff71e35`.

## How an AI assistant should access it

1. If authorized for this private GitHub repo, read this index, `SOURCE_V14_SHA256.json`, Issue #111 and current PR/CI evidence **first**; do not guess Windows filesystem paths or restart ZIP hunts.
2. The ten original restricted files are **not available from the GitHub checkout**. For actual bytes, the user must explicitly connect or supply an approved private source through that AI's authenticated file/connector interface. ChatGPT Library file IDs do not grant another provider access.
3. In a private, access-controlled and temporary integration workspace, verify the complete ZIP hash, ZIP CRC, and all 42 per-file hashes before using code. Preserve the frozen archive unchanged; never overwrite originals. Use only fictional test data.
4. Keep all restricted source bytes, private ZIPs, credentials, extracted snippets, logs containing secrets and restricted build artifacts **outside GitHub commits, issues, PRs, GitHub Actions artifacts and externally accessible storage** absent explicit independent authorization.
5. Protect `src/secure_server.py` behind the independent security review and modern cross-process authorization checks (notably HTTP-REVOCATION-001). An isolated private PASS is not a production verdict.
6. Sharing source with another AI requires **separate explicit permission, appropriate contractual/privacy review and an approved access-controlled connector or upload**, scoped minimally. Never grant anonymous/public link access.
7. Any AI assistant unable to access the private archive should report `RESTRICTED_SOURCE_ACCESS_UNAVAILABLE` and the necessary connection step. Do not fabricate substitutes or claim its tests passed.

## Known engineering evidence, not release authorization

* Previous private, isolated regression report: 1,187 tests run, 1,185 passed, 2 skipped; **not** an official hosted exact-source release gate.
* Windows frozen packaged app: Actions run `43452937155` at `b45dbc9eb3d75ac287d2ac371ba4170c15ca90a4`: backup/restore and second-process durable readback verified, unsigned executable; Smart App Control/customer-PC acceptance unresolved.
* Independent qualified human security approval: **UNRESOLVED**. Protected merge/deployment: **NOT AUTHORIZED**. Source-publication gate: **32/42** in referenced published checkpoint; never waive it or infer a private recovery is equivalent to publication clearance.

## Persistence and limits

This GitHub index is a durable metadata locator available to agents **with authorized private repository access**. It does **not** synchronize ChatGPT Library, Windows disks, Google Drive, Claude, Grok, or other AI platforms automatically. There is no verified permanent synced Windows path, universal cross-AI access grant, encrypted independent backup, or automated retrieval integration unless separately established and tested.
