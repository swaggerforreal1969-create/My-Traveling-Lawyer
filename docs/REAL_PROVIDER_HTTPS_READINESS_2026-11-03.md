# Real-provider HTTPS readiness — disabled contract

**Status:** contract implemented; no service configured, no external request executed, no human security approval, no independent custody acceptance.

`src/pinned_https_custody_adapter.py` provides an optional, disabled-by-default callable for the existing `AuthenticatedCustodyTransport`. Activation requires an explicitly approved HTTPS endpoint, a previously independently verified **leaf DER certificate SHA-256** pin, and `enabled=True`. A separately trusted authority must supply these and independently confirm operational custody. The connector uses standard-library TLS certificate/hostname validation, a bounded timeout, a fixed 443 port, three fixed operations, no redirects, no automatic retries, small JSON request/response bounds, duplicate JSON key rejection and generic failure errors. It does not persist credentials or print provider responses. It does not enable itself in the GUI or checkpoint provider.

The leaf certificate pin is **not** a checkpoint signing key or a full public-key pin. Certificate rotation needs manual authorization and this is not a substitute for separately administered witness identity, external signature verification, caller-held immutable history pins or independent readback. Real mutual TLS or OAuth revocation integration needs a provider-approved adapter review. Any ambiguous acknowledgment leaves the attorney write fence pending.

`tests/test_pinned_https_custody_adapter.py` uses mock HTTPS connections only; it cannot establish real TLS deployment behavior. Future real-provider acceptance must be deliberately enabled with a separately authorized host and must test independent administration, actual certificate chains, credential and signer revocation, crash boundaries, delayed responses, rollback, equivocation, exact history pins, conditional admission and denied writes after uncertainty. Never introduce real client/case details in tests.

Source migration remains 32/42. The ten frozen original files and unchanged 42-file gate remain protected. Security Issue #1 requires a named independent reviewer. No main merge or production activation.
