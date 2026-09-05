"""ChatGov Ω3.6 performance controls harvested from prior CFBE experiments.

The controls are intentionally local/source-level. They improve recovery and
context economics for hosts that bind them; they do not claim distributed
provider durability or hidden ChatGPT context control.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


SNAPSHOT_REQUIRED = {
    "snapshot_id", "producer_id", "mission_id", "generation", "created_at",
    "expires_at", "source_epochs", "coverage", "state",
}


class RecoverySnapshotError(ValueError):
    pass


def _validate_snapshot_body(payload: Mapping[str, Any]) -> None:
    missing = sorted(SNAPSHOT_REQUIRED - set(payload))
    if missing:
        raise RecoverySnapshotError(f"RECOVERY_SNAPSHOT_MISSING:{','.join(missing)}")
    if payload["state"] not in {"VERIFIED", "PARTIAL_CHECKPOINTED", "BLOCKED"}:
        raise RecoverySnapshotError("RECOVERY_SNAPSHOT_STATE_INVALID")
    if not isinstance(payload["generation"], int) or payload["generation"] < 1:
        raise RecoverySnapshotError("RECOVERY_SNAPSHOT_GENERATION_INVALID")
    coverage = payload["coverage"]
    if not isinstance(coverage, Mapping) or not coverage or not all(isinstance(v, bool) for v in coverage.values()):
        raise RecoverySnapshotError("RECOVERY_SNAPSHOT_COVERAGE_INVALID")
    if float(payload["expires_at"]) <= float(payload["created_at"]):
        raise RecoverySnapshotError("RECOVERY_SNAPSHOT_FRESHNESS_WINDOW_INVALID")


def sign_recovery_snapshot(payload: Mapping[str, Any], *, key: bytes, key_id: str) -> dict[str, Any]:
    if not key or not key_id.strip():
        raise RecoverySnapshotError("RECOVERY_SNAPSHOT_SIGNER_REQUIRED")
    body = copy.deepcopy(dict(payload))
    body.pop("signature", None)
    body.pop("digest", None)
    _validate_snapshot_body(body)
    digest = sha256_hex(body)
    signature = hmac.new(key, canonical_json(body), hashlib.sha256).hexdigest()
    body["digest"] = digest
    body["signature"] = {"algorithm": "HMAC-SHA256", "key_id": key_id, "value": signature}
    return body


def verify_recovery_snapshot(
    snapshot: Mapping[str, Any], *, key: bytes, now: float | None = None,
    required_coverage: Sequence[str] = (), expected_generation: int | None = None,
) -> dict[str, Any]:
    body = copy.deepcopy(dict(snapshot))
    signature = body.pop("signature", None)
    claimed_digest = body.pop("digest", None)
    _validate_snapshot_body(body)
    issues: list[str] = []
    if not isinstance(signature, Mapping) or signature.get("algorithm") != "HMAC-SHA256":
        issues.append("SIGNATURE_METADATA_INVALID")
    else:
        expected = hmac.new(key, canonical_json(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(signature.get("value", "")), expected):
            issues.append("SIGNATURE_INVALID")
    if claimed_digest != sha256_hex(body):
        issues.append("DIGEST_INVALID")
    clock = time.time() if now is None else float(now)
    if clock >= float(body["expires_at"]):
        issues.append("SNAPSHOT_STALE")
    if expected_generation is not None and body["generation"] != expected_generation:
        issues.append("GENERATION_MISMATCH")
    for key_name in sorted(set(map(str, required_coverage))):
        if body["coverage"].get(key_name) is not True:
            issues.append(f"COVERAGE_MISSING:{key_name}")
    return {
        "decision": "ACCEPT" if not issues else "REJECT",
        "issues": issues,
        "snapshot_id": body["snapshot_id"],
        "proof_state": body["state"],
        "generation": body["generation"],
    }


class LedgerConflict(RuntimeError):
    pass


class FenceRejected(RuntimeError):
    pass


class FencedLedgerHead:
    """O(1) task head plus hash-linked append ledger with CAS/fencing."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS cfbe_receipts(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    slot TEXT NOT NULL,
                    fence INTEGER NOT NULL,
                    prior_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    receipt_hash TEXT NOT NULL,
                    UNIQUE(task_id,generation,slot)
                );
                CREATE TABLE IF NOT EXISTS cfbe_heads(
                    task_id TEXT PRIMARY KEY,
                    generation INTEGER NOT NULL,
                    fence INTEGER NOT NULL,
                    sequence INTEGER NOT NULL,
                    receipt_hash TEXT NOT NULL
                );
                """
            )

    def head(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM cfbe_heads WHERE task_id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def append(
        self, *, task_id: str, generation: int, slot: str, fence: int,
        payload: Mapping[str, Any], expected_head_hash: str | None = None,
    ) -> dict[str, Any]:
        if not task_id.strip() or not slot.strip() or generation < 1 or fence < 1:
            raise ValueError("LEDGER_APPEND_IDENTITY_INVALID")
        payload_json = canonical_json(payload).decode("utf-8")
        payload_hash = sha256_hex(payload)
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            duplicate = db.execute(
                "SELECT * FROM cfbe_receipts WHERE task_id=? AND generation=? AND slot=?",
                (task_id, generation, slot),
            ).fetchone()
            if duplicate:
                if duplicate["payload_hash"] != payload_hash or int(duplicate["fence"]) != fence:
                    raise LedgerConflict("DIVERGENT_DUPLICATE_RECEIPT")
                db.execute("COMMIT")
                out = dict(duplicate)
                out["idempotent_replay"] = True
                return out
            head = db.execute("SELECT * FROM cfbe_heads WHERE task_id=?", (task_id,)).fetchone()
            prior_hash = str(head["receipt_hash"]) if head else "GENESIS"
            if head and fence < int(head["fence"]):
                raise FenceRejected("STALE_FENCE")
            if head and generation < int(head["generation"]):
                raise FenceRejected("STALE_GENERATION")
            if expected_head_hash is not None and expected_head_hash != prior_hash:
                raise FenceRejected("CAS_HEAD_MISMATCH")
            receipt_hash = sha256_hex({
                "task_id": task_id,
                "generation": generation,
                "slot": slot,
                "fence": fence,
                "prior_hash": prior_hash,
                "payload_hash": payload_hash,
            })
            cur = db.execute(
                "INSERT INTO cfbe_receipts(task_id,generation,slot,fence,prior_hash,payload_json,payload_hash,receipt_hash) VALUES(?,?,?,?,?,?,?,?)",
                (task_id, generation, slot, fence, prior_hash, payload_json, payload_hash, receipt_hash),
            )
            sequence = int(cur.lastrowid)
            db.execute(
                "INSERT INTO cfbe_heads(task_id,generation,fence,sequence,receipt_hash) VALUES(?,?,?,?,?) "
                "ON CONFLICT(task_id) DO UPDATE SET generation=excluded.generation,fence=excluded.fence,sequence=excluded.sequence,receipt_hash=excluded.receipt_hash",
                (task_id, generation, fence, sequence, receipt_hash),
            )
            db.execute("COMMIT")
            return {
                "sequence": sequence, "task_id": task_id, "generation": generation,
                "slot": slot, "fence": fence, "prior_hash": prior_hash,
                "payload_hash": payload_hash, "receipt_hash": receipt_hash,
                "idempotent_replay": False,
            }
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def verify_chain(self, task_id: str) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM cfbe_receipts WHERE task_id=? ORDER BY sequence", (task_id,)).fetchall()
        prior = "GENESIS"
        issues: list[str] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            if row["payload_hash"] != sha256_hex(payload):
                issues.append(f"PAYLOAD_HASH:{row['sequence']}")
            expected = sha256_hex({
                "task_id": row["task_id"], "generation": row["generation"],
                "slot": row["slot"], "fence": row["fence"], "prior_hash": prior,
                "payload_hash": row["payload_hash"],
            })
            if row["prior_hash"] != prior or row["receipt_hash"] != expected:
                issues.append(f"CHAIN:{row['sequence']}")
            prior = str(row["receipt_hash"])
        return {"decision": "VERIFIED" if not issues else "REJECTED", "count": len(rows), "issues": issues, "head_hash": prior}


REQUIRED_CAPSULE_SECTIONS = ("objective", "requirements", "constraints", "source_epochs", "routes", "open_gates")
OPTIONAL_CAPSULE_SECTIONS = ("recent_failures", "next_actions", "notes")


class HardContextCapsuleError(ValueError):
    pass


def build_hard_context_capsule(source: Mapping[str, Any], *, max_bytes: int = 4000) -> dict[str, Any]:
    if max_bytes < 256:
        raise HardContextCapsuleError("CONTEXT_CAPSULE_BUDGET_TOO_SMALL")
    missing = [key for key in REQUIRED_CAPSULE_SECTIONS if key not in source]
    if missing:
        raise HardContextCapsuleError(f"CONTEXT_CAPSULE_MISSING:{','.join(missing)}")
    capsule: dict[str, Any] = {key: source[key] for key in REQUIRED_CAPSULE_SECTIONS}
    omitted = sorted(set(source) - set(REQUIRED_CAPSULE_SECTIONS + OPTIONAL_CAPSULE_SECTIONS))
    included_optional: list[str] = []
    for key in OPTIONAL_CAPSULE_SECTIONS:
        if key in source:
            capsule[key] = source[key]
            included_optional.append(key)

    def finalize() -> dict[str, Any]:
        value = dict(capsule)
        value["omitted"] = sorted(set(omitted))
        value["schema"] = "CHATGOV-HARD-CONTEXT-CAPSULE-1"
        value["digest"] = sha256_hex({k: v for k, v in value.items() if k not in {"digest", "bytes"}})
        value["bytes"] = 0
        for _ in range(3):
            value["bytes"] = len(canonical_json(value))
        return value

    result = finalize()
    while result["bytes"] > max_bytes and included_optional:
        key = included_optional.pop()
        capsule.pop(key, None)
        omitted.append(key)
        result = finalize()
    if result["bytes"] > max_bytes:
        raise HardContextCapsuleError(f"REQUIRED_CONTEXT_EXCEEDS_BUDGET:{result['bytes']}>{max_bytes}")
    return result


def assess_stream(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Executor-side stream admission before raw payload enters the hot context."""
    issues: list[str] = []
    payload = int(packet.get("payload_tokens", 0))
    max_payload = min(int(packet.get("max_payload_tokens", 4000)), 4000)
    if payload > max_payload:
        issues.append("PAYLOAD_OVERFLOW")
    if int(packet.get("retry_count", 0)) > int(packet.get("retry_budget", 1)):
        issues.append("RETRY_STORM")
    if int(packet.get("concurrency", 1)) > int(packet.get("max_concurrency", 4)):
        issues.append("CONCURRENCY_OVERFLOW")
    if float(packet.get("elapsed_minutes", 0.0)) > float(packet.get("max_elapsed_minutes", 18.0)):
        issues.append("TIMEBOX_EXCEEDED")
    if packet.get("raw_payload_serialized") is True:
        issues.append("RAW_PAYLOAD_SERIALIZED")
    if packet.get("contains_secret") is True:
        issues.append("SECRET_EXPOSURE")
    if packet.get("unchanged_failed_route_retried") is True:
        issues.append("UNCHANGED_ROUTE_RETRY")
    if int(packet.get("owner_visible_progress_events", 0)) > int(packet.get("owner_progress_budget", 2)):
        issues.append("OWNER_ATTENTION_OVERFLOW")
    return {
        "decision": "ADMIT" if not issues else "QUARANTINE",
        "issues": issues,
        "checkpoint_required": bool(issues),
        "maximum_segment_tokens": max_payload,
    }


__all__ = [
    "FenceRejected", "FencedLedgerHead", "HardContextCapsuleError", "LedgerConflict",
    "RecoverySnapshotError", "assess_stream", "build_hard_context_capsule",
    "canonical_json", "sha256_hex", "sign_recovery_snapshot", "verify_recovery_snapshot",
]
