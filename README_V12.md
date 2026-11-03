# My Traveling Lawyer v1.2 (experimental)

Local Python application, fictional data only. Preserve earlier releases separately.

This update adds a demonstration signed-device step-up API, not full passkeys.

To reproduce focused tests from the project root: `python -m unittest discover -s tests -p 'test_device_challenge_v12.py' -q` and analogous patterns for `test_secure_engine.py` and `test_engine.py`. Requires Python with `cryptography` installed.

Read `ENGINEERING_CONTINUITY.md` for exact evidence, missing GitHub state, timeout investigation and release blockers.