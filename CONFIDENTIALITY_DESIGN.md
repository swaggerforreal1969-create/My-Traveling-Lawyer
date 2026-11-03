# Confidentiality-by-default — v0.8 experimental controls

## Threats and mitigations
- Eavesdropping: silent-only default; audio devices not requested; warn user that private physical setting is mandatory. No device can guarantee nearby microphones absent.
- Shoulder surfing: explicit privacy cover and automatic cover on tab background or focus loss. Cosmetic only; not OS-level screen capture prevention.
- AI disclosure: confidential mode default; server rejects remote provider requests with confidential classification, even if consent is checked. Only explicitly classified synthetic/public prompts can be sent with per-request opt-in. Classification is supplied by user; NOT DLP or reliable secret detection.
- Browser capture: restrictive Permissions-Policy and no-store response headers; cannot prevent OS screenshots, hostile extensions, or compromised devices.
- Stolen device: require actual production device enrollment, phishing-resistant MFA, managed-device disk encryption, revocation, remote wipe and short sessions; NOT IMPLEMENTED.
- Back end compromise: local SQLite is not encrypted; independent custody and secure backup not implemented.
- Vendor leak: vendor controls, no-training/no-retention agreements, jurisdiction/consent review and legal review needed before any confidential integration.
- Calls: no automatic recording or transcription; local jurisdiction's recording-consent rules require review.

## Fail-closed policy
Any request with sensitivity confidential + external_consent true must return 400 and never call provider. No default transfer of matter data. External AI remains disabled without explicit per-question opt-in and provider allowlist.

## Limits
Visual cover is not cryptographic security and does not block screen recording or memory inspection. No real client data.