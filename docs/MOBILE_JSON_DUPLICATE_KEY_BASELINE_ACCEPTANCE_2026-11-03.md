# JSON duplicate-member fail-closed renderer and frozen v1.4 compatibility (2026-11-03)

## Start-state and controls
- Before editing, independent security Issue #1 was checked: **OPEN, unassigned, zero comments**. No approval for ten blocked original files. Original migration remains **32/42**.
- Latest prior published continuity SHA: `9b6269ef7d4ff17881d03b4cc7e37950b5864b76`; no matching passing GitHub CI or Chromium acceptance.
- Modified only the separately authored experimental renderer `src/json_mobile_document.py` and `tests/test_json_mobile_document.py`. Frozen originals, main, Koontcee and Diezel remain untouched. No original file uploads, deployment, purchases, external AI or real client data.

## Real defect corrected
- Python's standard `json.loads` silently accepts duplicate JSON object members, keeping the last value. This can create a parser mismatch on legal-verification flags or procedural counts even when the final schema looks safe.
- Added `object_pairs_hook=_unique_json_object` to fail closed on **duplicate member names at every JSON object nesting level**, before validation/rendering. All prior strict schema and no-verified-law policies remain in place.
- Added two adversarial regression tests: duplicate top-level `court_filing_approved`; duplicate nested `needs_first_observation` research-status entry. The tests affirm rejection even when duplicated values agree.

## Executed evidence
- `python -m unittest discover -s tests -v` in isolated updated renderer tree: **22/22 PASS**, clean exit 0.
- `python -m compileall -q src tests`: PASS.
- The frozen v1.4 local handoff ZIP was extracted to a **temporary test-only working copy**; original ZIP preserved unchanged. Only the two separately authored updated experimental renderer files were added to that copy.
- `python -m unittest discover -s tests -q` in that frozen-v1.4-plus-renderer copy: **314/314 PASS in 32.475 seconds**, exit code **0**.
- GitHub updated source/test blobs match the tested local Git hashes exactly:
  - `src/json_mobile_document.py`: `3c3d885a49b073354302b2cda3e36e5e2b5e7b99`
  - `tests/test_json_mobile_document.py`: `c9bd2b744a8af65a297b123e14cdaeea2fa51faa`

## What this does NOT verify
- The historic **544-test** assembled experimental suite is **not available as a complete checkout** in the present container. The putative full 564-test combined regression was **not executed**. The 314 count is specifically the frozen v1.4 test ZIP + this renderer (not the 544 baseline plus 22); never claim full integrated release acceptance from it.
- GitHub is private, and the container cannot resolve github.com for an ordinary git clone. Existing authorized GitHub connector can fetch files, but this is not a verified complete source checkout. Do not bypass the ten original restricted paths.
- No exact-SHA passing Linux CI run exists for this increment. Chromium previously failed `ERR_BLOCKED_BY_ADMINISTRATOR`; it was not rerun or bypassed here.
- Real maintained-library WebAuthn, independently authenticated official legal sources and confidential operational 24/7 AI remain unfinished.

## Next
1. Obtain independent reviewer disposition in Issue #1 before touching ten blocked original paths.
2. Assemble a complete current engineering test checkout through approved GitHub access and verify its exact blob manifest. Run actual full test suite once with clean exit status, including all previously published experimental modules.
3. Execute exact-SHA Linux and genuine Chromium browser acceptance on a runner expressly allowed to browse localhost; preserve pass/fail artifacts.
4. Continue substantial read-only confidential mobile integration and negative boundary tests without claiming verified legal status, public production service or outbound AI.
