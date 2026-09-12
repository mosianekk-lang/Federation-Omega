"""Producer-signed, freshness-bound recovery snapshots."""

from __future__ import annotations

import copy
import hashlib
import hmac
import time
from typing import Any, Mapping

from .canonical import canonical_json, sha256_hex

REQUIRED = {
    "snapshot_id",
    "producer_id",
    "mission_id",
    "generation",
    "created_at",
    "expires_at",
    "source_epochs",
    "coverage",
    "state",
}


class SnapshotError(ValueError):
    pass


def _validate_payload(payload: Mapping[str, Any]) -> None:
    missing = sorted(REQUIRED - set(payload))
    if missing:
        raise SnapshotError(f"missing fields: {','.join(missing)}")
    if payload["state"] not in {"VERIFIED", "PARTIAL_CHECKPOINTED", "BLOCKED"}:
        raise SnapshotError("invalid proof state")
    if not isinstance(payload["generation"], int) or payload["generation"] < 1:
        raise SnapshotError("generation must be a positive integer")
    if not isinstance(payload["coverage"], Mapping) or not payload["coverage"]:
        raise SnapshotError("coverage must be a non-empty object")
    if not all(isinstance(v, bool) for v in payload["coverage"].values()):
        raise SnapshotError("coverage values must be Boolean")
    if float(payload["expires_at"]) <= float(payload["created_at"]):
        raise SnapshotError("expires_at must be after created_at")


def sign_snapshot(payload: Mapping[str, Any], key: bytes, key_id: str) -> dict[str, Any]:
    if not key:
        raise SnapshotError("empty signing key")
    _validate_payload(payload)
    body = copy.deepcopy(dict(payload))
    body.pop("signature", None)
    body.pop("digest", None)
    digest = sha256_hex(body)
    signature = hmac.new(key, canonical_json(body), hashlib.sha256).hexdigest()
    body["digest"] = digest
    body["signature"] = {"algorithm": "HMAC-SHA256", "key_id": key_id, "value": signature}
    return body


def verify_snapshot(
    snapshot: Mapping[str, Any],
    key: bytes,
    *,
    now: float | None = None,
    required_coverage: set[str] | None = None,
    expected_generation: int | None = None,
) -> dict[str, Any]:
    body = copy.deepcopy(dict(snapshot))
    signature = body.pop("signature", None)
    claimed_digest = body.pop("digest", None)
    _validate_payload(body)
    issues: list[str] = []
    if not isinstance(signature, Mapping) or signature.get("algorithm") != "HMAC-SHA256":
        issues.append("SIGNATURE_METADATA_INVALID")
    else:
        expected = hmac.new(key, canonical_json(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(signature.get("value", "")), expected):
            issues.append("SIGNATURE_INVALID")
    if claimed_digest != sha256_hex(body):
        issues.append("DIGEST_INVALID")
    clock = time.time() if now is None else now
    if clock > float(body["expires_at"]):
        issues.append("SNAPSHOT_STALE")
    if expected_generation is not None and body["generation"] != expected_generation:
        issues.append("GENERATION_MISMATCH")
    for item in sorted(required_coverage or set()):
        if body["coverage"].get(item) is not True:
            issues.append(f"COVERAGE_MISSING:{item}")
    return {
        "decision": "ACCEPT" if not issues else "REJECT",
        "issues": issues,
        "snapshot_id": body["snapshot_id"],
        "proof_state": body["state"],
    }
