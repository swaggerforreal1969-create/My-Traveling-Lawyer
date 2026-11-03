# Private Mobile Matter View — isolated experimental increment

## Function
- `src/mobile_matter_view.py` renders the existing `mtl.matter.preparation.v1` schema as offline, responsive, read-only HTML.
- `tests/test_mobile_matter_view.py` has 14 deterministic, fictional-data tests.
- Privately disclosed sections (matter details, notes, open tasks, risk notices and source assessments) are collapsed on initial display using native HTML `details` tags.
- All user-controlled text is HTML-escaped, all source URLs are inert text (not links), and the generated document contains no script, forms, images, external styles, or network requests.
- A restrictive meta CSP limits scripts, connections, images, forms and remote resources.
- Unexpected schema, missing false legal-verification or outbound-AI flags, unknown human review status, excessively large collections/fields, and malformed records fail closed.
- The code is **only a renderer**. The caller must first obtain a matter snapshot using existing authenticated `MatterBrief.prepare(token, matter_id)`. The renderer alone is not an authentication system.

## Test evidence — 2026-11-03
- Focused module tests: **14/14 passed**; local Python compilation passed.
- Fresh preserved v1.4 archive + the new renderer and tests: `python -m unittest discover -s tests -q` → **306/306 passed in 11.920 seconds**.
- Source Git blob SHA-1: `1e9584d19aed554c5c91fd5c90ad522993383a75`.
- Tests Git blob SHA-1: `2c8ba0aa51ea43e5be16c8f5ac597fc1f437a934`.
- Both GitHub blobs fetched back and confirmed exact hash matches to locally tested code.
- This local full-suite evidence **does not include the previously published isolated authority review/matter brief test modules** in its test count; those previously passed separate local acceptance. The real GitHub source tree is incomplete and has no passing Linux CI verification.

## Security limitations and acceptance
- Collapsed HTML details are **visual privacy convenience, NOT encryption, screenshot prevention or OS-level privacy control**. The entire rendered HTML contains the data; saved HTML must be protected as sensitive.
- No real client data, automatic legal authority validation or court deadline calculations.
- No browser acceptance verified; browser environment previously blocked navigation.
- The generated HTML cannot be described as live 24/7 AI, WebAuthn, or an operational hosted service.
- Independent review Issue #1 remains open, unassigned and without comments. Frozen original v1.4 migration remains 32/42 files; ten blocked originals were not modified or uploaded.
- No changes to main, production or other engines.

## Next
1. Have independent reviewer approve or prescribe remediation for Issue #1; do not bypass blocked uploads.
2. Complete 42/42 original source publication and integrity verification, then exact-SHA Linux and real browser CI.
3. Wire the new renderer to an authenticated local-only preview path behind privacy/session enforcement; add real responsive browser tests.
4. Continue standards-based WebAuthn, source-verifiable research and confidential live 24/7 AI readiness without real-client data.
