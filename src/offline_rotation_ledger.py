"""Offline, local-only durable reservation ledger for proposed trust rotations.

This ledger prevents cooperating processes from presenting the same rotation ID
twice or mutually exclusive rotations at one predecessor. It does NOT update
trust roots, attest independent custody, authenticate real humans or protect
against coordinated database rollback/deletion. A damaged or missing ledger
must fail closed rather than resetting history.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3

from .secure_engine import Denied
from .independent_checkpoint_boundary import _hex, PinnedCheckpoint
from .offline_trust_rotation import OfflinePinRotationPreflight, RotationObservation


@dataclass(frozen=True)
class ReservedRotation:
    observation: RotationObservation
    manifest_digest: str
    status: str = "reserved_for_independent_manual_review"


class OfflineRotationLedger:
    def __init__(self, path, *, create=False):
        self.path = Path(path)
        if not self.path.is_file():
            if not create:
                raise Denied("Missing trust rotation ledger; recovery requires incident review")
            if self.path.exists():
                raise Denied("Invalid trust rotation ledger location")
        try:
            with self._database() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("""CREATE TABLE IF NOT EXISTS rotation_ledger (
                    rotation_id TEXT PRIMARY KEY,
                    predecessor_digest TEXT NOT NULL UNIQUE,
                    predecessor_sequence INTEGER NOT NULL,
                    predecessor_signer TEXT NOT NULL,
                    manifest_digest TEXT NOT NULL UNIQUE,
                    successor_digest TEXT NOT NULL,
                    successor_signer TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state='proposed'))""")
                db.execute("COMMIT")
        except (sqlite3.Error, OSError) as exc:
            raise Denied("Trust rotation ledger unavailable") from exc

    def _database(self):
        conn = sqlite3.connect(str(self.path), isolation_level=None, timeout=5)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    def reserve_once(self, *, policy, manifest, now, operator_authorized):
        """Verify signatures and independent approval, then reserve exactly once.

        A local atomic reservation only blocks accidental/competing proposals.
        It is NOT durable independent approval or permission to rotate any key.
        """
        if not isinstance(policy, OfflinePinRotationPreflight):
            raise Denied("Approved rotation policy required")
        if type(manifest) is not dict:
            raise Denied("Rotation manifest required")
        try:
            with self._database() as db:
                db.execute("BEGIN IMMEDIATE")
                observation = policy.inspect(
                    manifest=manifest, now=now,
                    operator_authorized=operator_authorized)
                # The complete signed manifest is included, so two signer sets
                # cannot silently acquire the same operation identity.
                canonical = json.dumps(
                    manifest, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=True).encode("ascii")
                digest = hashlib.sha256(canonical).hexdigest()
                if not _hex(manifest["rotation_id"]):
                    raise Denied("Invalid rotation identity")
                if db.execute(
                    "SELECT 1 FROM rotation_ledger WHERE rotation_id=? "
                    "OR predecessor_digest=? OR manifest_digest=?",
                    (manifest["rotation_id"], policy.current_pin.digest,
                     digest)).fetchone():
                    raise Denied("Replay or conflicting trust rotation")
                db.execute(
                    """INSERT INTO rotation_ledger
                    (rotation_id,predecessor_digest,predecessor_sequence,
                     predecessor_signer,manifest_digest,successor_digest,
                     successor_signer,state) VALUES (?,?,?,?,?,?,?,'proposed')""",
                    (manifest["rotation_id"], policy.current_pin.digest,
                     policy.current_pin.sequence,policy.current_pin.signer_id,
                     digest,observation.new_pin.digest,
                     observation.new_pin.signer_id))
                db.execute("COMMIT")
                return ReservedRotation(observation,digest)
        except Denied:
            raise
        except (sqlite3.Error, OSError, TypeError, ValueError) as exc:
            raise Denied("Trust rotation reservation unavailable") from exc

    def inspect_reserved(self, rotation_id):
        """Read-only local evidence, NEVER trust-root authorization."""
        if not _hex(rotation_id) or not self.path.is_file():
            raise Denied("Trust rotation ledger identity unavailable")
        try:
            with self._database() as db:
                result = db.execute(
                    """SELECT predecessor_sequence,predecessor_digest,
                       predecessor_signer,successor_digest,successor_signer,
                       manifest_digest,state FROM rotation_ledger
                       WHERE rotation_id=?""", (rotation_id,)).fetchone()
                if result is None:
                    raise Denied("Rotation reservation not found")
                return {
                    "previous": PinnedCheckpoint(result[0], result[1], result[2]),
                    "successor": PinnedCheckpoint(result[0], result[3], result[4]),
                    "manifest_digest":result[5],
                    "state":result[6]}
        except Denied:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise Denied("Trust rotation ledger unreadable") from exc
