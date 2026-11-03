# Confidential mobile response cache-policy fail-closed acceptance — 2026-11-03

## Reviewed boundary and starting point
- Independent security Issue #1 inspected **first**: OPEN, unassigned, 0 comments; no authorization for the ten blocked original v1.4 paths. Original source migration stays **32/42**.
- Starting engineering SHA: `4272d6998eba9be967272ee56c1ca4ce8e4e4296`. No successful matching GitHub CI run was found.
- No modifications to frozen originals, main, Koontcee, Diezel, public deployment, permissions or external AI. All test data fictional.

## Real privacy defect repaired
- `src/json_mobile_document.py` previously checked whether a cache-control header **contained the substring** `no-store`. This would accept the invalid directive `not-no-store`, which does not enforce confidentiality.
- The updated renderer requires a real comma-delimited, case-insensitive, stand-alone `no-store` directive and permits only the known safe set `no-store`, `no-cache`, `must-revalidate`, `private`; it fails closed on conflicting, unknown or cache-enabling directives such as `public`, `max-age`, and `s-maxage`.
- The new tests prove misleading substrings and conflicting directives are denied, and the real ReadinessJSON-style private no-store policy remains accepted. Other JSON duplicate-key, legal-status, strict schema and HTML no-script defenses are preserved.

## Executed acceptance
- Focused isolated renderer `python -m unittest discover -s tests -q`: **25/25 PASS**, exit code 0 (3 additional tests).
- Recovered previously authorized frozen v1.4 test copy with only the newly authored renderer source/test files updated; `python -m unittest discover -s tests -q`: **317/317 PASS in 23.483 seconds**, exit code **0**.
- `python -m compileall -q src tests`: PASS, exit 0.
- Published exact blob hashes:
  - `src/json_mobile_document.py`: `287be91e70ac841dec4748696f2468b8acb9a2e8`
  - `tests/test_json_mobile_document.py`: `85fae96ba1084ed30b0766a3e2601303aa85537e`
- Both files successfully updated on isolated engineering branch and GitHub returned blob identities matching the locally tested bytes.

## Not yet accepted
- The complete older 544-test experimental checkout plus current renderer is **not reconstructed or run**. Do not label the expected >566-test count a passed integrated regression. The 317-run tests frozen v1.4 plus the updated renderer only.
- GitHub exact-commit Linux CI and genuine Chromium HTML/JSON acceptance: **not passed**. Earlier local Chromium returned `ERR_BLOCKED_BY_ADMINISTRATOR`; no bypass was attempted.
- Independent security review decision and all original 42 hashes still pending at 32/42. Maintained-library WebAuthn, independently verified current official laws, independent custody, and operational private 24/7 AI are unfinished.

## Next
1. Obtain named reviewer decision on Issue #1. Do not bypass ten restricted originals.
2. Recover the complete experimental checkout using approved GitHub access, verify a full file/blob manifest, and run the *actual* combined regression with exit code 0.
3. Establish authorized exact-SHA Linux CI and genuine Chromium acceptance, including JSON no-store, duplicate-key, HTML privacy, revoked credential and replay denial.
4. Continue implementing genuinely useful bounded confidential attorney functionality without user data, deployment, spending or external AI egress.
