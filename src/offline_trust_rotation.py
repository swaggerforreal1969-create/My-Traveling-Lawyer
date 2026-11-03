"""Offline trust-pin rotation preflight. No network, no key import, no pin writes.

A caller must independently retain both the current checkpoint and the signer
trust root. A proposed rotation is UNTRUSTED until BOTH old- and new-key
signatures and a separately authorized operator approval are verified.
No automatic trust-on-first-use, auto-pin advancement or network configuration.
This deliberately does NOT constitute an independent security approval.
"""
from dataclasses import dataclass
import json
from .secure_engine import Denied
from .independent_checkpoint_boundary import PinnedCheckpoint, _hex, _identity


@dataclass(frozen=True)
class RotationObservation:
    new_pin: PinnedCheckpoint
    approved_for_manual_review: bool = True
    independent_custody_confirmed: bool = False


class OfflinePinRotationPreflight:
    def __init__(self, *, current_pin, verify_old_key, verify_new_key,
                 independent_approval):
        if (not isinstance(current_pin,PinnedCheckpoint)
                or type(current_pin.sequence) is not int
                or current_pin.sequence < 0
                or not _hex(current_pin.digest)
                or not _identity(current_pin.signer_id)
                or not callable(verify_old_key)
                or not callable(verify_new_key)
                or not callable(independent_approval)):
            raise Denied("Pinned trust-root policy not configured")
        self.current_pin = current_pin
        self.verify_old_key = verify_old_key
        self.verify_new_key = verify_new_key
        self.independent_approval = independent_approval

    def inspect(self, *, manifest, now, operator_authorized):
        """Return only a proposal for independent manual custody review.

        Manifest is signed by existing pinned key AND proposed successor key.
        Caller-supplied clock must be trusted; this API does not verify time
        provenance or establish independence of the separate approval.
        """
        if operator_authorized is not True:
            raise Denied("Operator authorization required for rotation")
        if type(now) is not int or now < 1:
            raise Denied("Trusted current epoch required")
        if type(manifest) is not dict or set(manifest) != {
            "version","previous_sequence","previous_digest",
            "previous_signer","next_sequence","next_digest",
            "next_signer","valid_after","valid_before",
            "rotation_id","old_signature","new_signature"}:
            raise Denied("Rotation manifest format rejected")
        if (type(manifest["version"]) is not int or manifest["version"] != 1
                or type(manifest["previous_sequence"]) is not int
                or type(manifest["next_sequence"]) is not int
                or manifest["previous_sequence"] != self.current_pin.sequence
                or manifest["previous_digest"] != self.current_pin.digest
                or manifest["previous_signer"] != self.current_pin.signer_id
                or manifest["next_sequence"] != self.current_pin.sequence
                or not _hex(manifest["next_digest"])
                or not _identity(manifest["next_signer"])
                or manifest["next_signer"] == self.current_pin.signer_id
                or not _hex(manifest["rotation_id"])
                or type(manifest["valid_after"]) is not int
                or type(manifest["valid_before"]) is not int
                or not manifest["valid_after"] <= now <= manifest["valid_before"]
                or manifest["valid_before"]-manifest["valid_after"] > 86400
                or not all(isinstance(manifest[k],str)
                           and 1 <= len(manifest[k]) <= 512
                           for k in ("old_signature","new_signature"))):
            raise Denied("Rotation predecessor, successor or validity invalid")
        data={k:v for k,v in manifest.items()
              if k not in ("old_signature","new_signature")}
        canonical=json.dumps(data,sort_keys=True,
                             separators=(",",":"),ensure_ascii=True).encode("ascii")
        try:
            old_ok=self.verify_old_key(
                self.current_pin.signer_id,canonical,manifest["old_signature"])
            new_ok=self.verify_new_key(
                manifest["next_signer"],canonical,manifest["new_signature"])
            approved=self.independent_approval(
                manifest["rotation_id"],canonical)
        except Exception as exc:
            raise Denied("Trust rotation verification unavailable") from exc
        if old_ok is not True or new_ok is not True or approved is not True:
            raise Denied("Trust rotation not independently authorized")
        return RotationObservation(PinnedCheckpoint(
            manifest["next_sequence"],manifest["next_digest"],
            manifest["next_signer"]))
