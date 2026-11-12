# Private Store MSIX packaging — not a signed release

We chose **Store-submitted MSIX**, not an unsigned EXE and not a Store-listed MSI/EXE. Microsoft signs approved MSIX submissions. The Store is not a way to sign a standalone ZIP or EXE, and **no one is authorized to publish or distribute this experimental lawyer app yet**.

**Implemented:** `tools/windows_fictional_gui.py` launches two obvious fictional practice actions. `tools/make_store_msix.py` builds an **UNSIGNED, local-only** MSIX candidate from a real PyInstaller onedir build using an **exact Partner Center app name, Publisher identity, version**, and Windows SDK `makeappx.exe`. It refuses to invent a publisher or overwrite an existing MSIX, and adds no network or client data. Packaging smoke tests are `tests/test_store_msix_preparation.py`.

**Developer execution prerequisites:** approved Windows x64 build system, Python 3.11 and vetted PyInstaller, Windows SDK MakeAppx; authorized developer has reserved an MSIX product name in Partner Center, and copied its exact Package Identity Name and Publisher DN. No Store credentials are saved in the repo. On that system, a developer first builds the onedir app (existing `tools/build_signed_windows.ps1 -BuildOnly -TrustedCertificateThumbprint UNUSED` invokes PyInstaller), then calls:

```powershell
py -3.11 tools/make_store_msix.py --package-name EXACT_PARTNER_CENTER_NAME --publisher "CN=EXACT_PARTNER_CENTER_ID" --publisher-display-name "Owner's approved company" --version 0.1.0.0
```

This only builds a **locally unsigned** candidate. Do **not** install, send, sideload, sign with self-signed trust exceptions, disable Smart App Control, or submit to Store without owner approval and security review. Store certification and a genuine **Smart App Control ON** test are required before any attorney delivery.

**Open gates:** Partner Center account/product identity not verified; Windows build tools / independent packaging run not verified; no actual MSIX built or submitted; trusted Store signing 0; Smart App Control ON 0; independent attorney feedback 0; human security clearance 0; published original-source 32/42. No cost authorized. Any Microsoft Store publisher account registration requirements must be confirmed before any action.

Protected PR #110: `c0b94e0eae172f3ea1deeb34800797b13edbcc8e`, native Windows job `131361151167` 58/58 PASS, 12/12 pilot, 9/9 backup; branch only is `release/windows-signed-practice-candidate-20261112`. Production NO-GO.
