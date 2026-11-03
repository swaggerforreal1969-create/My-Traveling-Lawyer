# Tk native attorney workload panel — isolated acceptance

**Experimental local UI only. No verified law, real-client support, independent custody or production approval.**

The native Tk attorney operator now has a **Workload (read only)** button and **Alt+P** keyboard shortcut. The button invokes the real `PrivateMatterPortfolio` implementation through `PrivateAttorneyOperator.portfolio_summary`, not a fixture. Its compact, keyboard-focusable and copy-safe text panel shows authorized per-matter positions, task counts, permitted human-review counts and reader/editor classifications. No client name, matter title, source content, token, URL or raw internal identifier appears.

Before the new portfolio read, the Tk app clears previously visible matter, task and review selections and any prior portfolio text. The controller invalidates actionable selection IDs and reauthorizes the full matter portfolio. A revoked credential, altered matter index, unexpected response or stale state leaves the panel empty and write controls disabled. Uncertain review identity remains retained for separately authorized manual recovery and must never be dropped or automatically replayed. The user can refresh the matter list to return to ordinary case selection.

`tests/test_native_tk_operator.py` runs real Tk widgets under the existing Xvfb acceptance step. It now verifies workload display and private redaction, denial after revocation, Alt+P focus, existing task and human-review controls, buttons at small window sizes and the screenshot workflow. Synthetic-only visual artifacts do not constitute a human accessibility or security audit.

No protected originals were modified; unchanged 42-file source/hash gate must remain red until approved original-source restoration. No main merges, deployments, purchases, permissions, external AI egress or real client data.
