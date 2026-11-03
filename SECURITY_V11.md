# My Traveling Lawyer — v1.1 custody verification (experimental)

## Functional increment

- A configured, externally supplied Ed25519 audit checkpoint is checked at server startup and before **every** API call. The verification fails closed when the checkpoint/key is missing, unreadable, forged, mismatched or rolled back, or the database hash chain has been modified.
- The local audit verifier now explicitly rejects missing sequence numbers, including missing interior rows. This plugs a class of deletion that might otherwise survive local hash verification.
- The trusted key and witness are loaded from operator-provided paths; they are not generated, pinned, or silently replaced by the server. `MTL_TRUSTED_CUSTODY_PIN` and `MTL_TRUSTED_CUSTODY_PUBLIC_KEY` must be provided together. The application starts without them only in **experimental** mode. Production should require them, plus a trusted remote custody protocol.

## Limitations and threat model

- The local files are merely **operator-supplied verification inputs**. Independence is not achieved just by placing them in a second directory or copying them into a ZIP. To resist rollback by a compromised app administrator, pin and trusted verification key must be managed outside that administrator's access, with protected immutable history and enforced monotonic head updates.
- A pinned historical ancestor detects rollback, truncation below the pin, and changes affecting the pin. It does **not** detect every malicious change appended after a pinned ancestor; a fresh signed checkpoint must be issued through independent custody on a trustworthy cadence.
- End-to-end browser acceptance was attempted with Playwright/Chromium but the container blocked `127.0.0.1` with `ERR_BLOCKED_BY_ADMINISTRATOR`. No browser-pass claim is made.
- Passkeys/WebAuthn, phishing-resistant registration, full identity lifecycle, data encryption at rest, independent custody provisioning, production hardening and 24/7 hosted AI remain unimplemented. Fictional data only.

## Trusted-input configuration (for authorized experiments only)

Set `MTL_TRUSTED_CUSTODY_PIN` to an absolute path to a separately provisioned signed checkpoint JSON, and `MTL_TRUSTED_CUSTODY_PUBLIC_KEY` to a trusted Ed25519 public key in base64 text. Start the local application normally. Both inputs are required whenever one is present. The startup validation rejects mismatches, and the API checks the pin again on every request. **Do not put the signing private key in the application folder.**

## Validation

`python -m unittest discover -s tests -p test_custody_v11.py -q`

`python -m unittest discover -s tests -q`

The tests cover signed pins, appended records, missing pins, wrong keys, forged witnesses, rollbacks, missing audit rows, tampering, misconfiguration, and denial of an active API request after trusted-input removal.
