from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
import hashlib
import json


REQUIRED_READ_PERMISSIONS = (
    "Perm_R_Balance",
    "Perm_R_Transactions",
    "Perm_R_Orders",
)
FORBIDDEN_WRITE_PERMISSIONS = {
    "Perm_W_Send",
    "Perm_W_Addresses",
    "Perm_W_Orders",
    "Perm_W_Withdrawals",
    "Perm_W_ClientDebit",
    "Perm_W_ClientCredit",
    "Perm_W_Beneficiaries",
}


def key_id_fingerprint(key_id: str) -> str:
    value = key_id.strip()
    if not value or value != key_id:
        raise ValueError("key id must be non-empty and normalized")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LunoPermissionProof:
    key_id_sha256: str
    permissions: tuple[str, ...]
    source_ref: str
    attested_at: str
    schema: str = "LUNO-OBSERVER-PERMISSION-PROOF-1"

    def validate(self, *, key_id: str) -> None:
        if self.schema != "LUNO-OBSERVER-PERMISSION-PROOF-1":
            raise ValueError("unsupported Luno permission proof schema")
        if self.key_id_sha256 != key_id_fingerprint(key_id):
            raise PermissionError("LUNO_PERMISSION_PROOF_KEY_MISMATCH")
        actual = set(self.permissions)
        required = set(REQUIRED_READ_PERMISSIONS)
        if actual != required:
            raise PermissionError("LUNO_PERMISSION_PROOF_MUST_MATCH_EXACT_READ_SET")
        if actual.intersection(FORBIDDEN_WRITE_PERMISSIONS) or any(p.startswith("Perm_W_") for p in actual):
            raise PermissionError("LUNO_PERMISSION_PROOF_CONTAINS_WRITE_AUTHORITY")
        if not self.source_ref or not self.source_ref.strip():
            raise ValueError("permission proof requires source_ref")
        observed = datetime.fromisoformat(self.attested_at.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError("attested_at must be timezone-aware")

    def digest(self) -> str:
        payload = {
            "schema": self.schema,
            "key_id_sha256": self.key_id_sha256,
            "permissions": list(self.permissions),
            "source_ref": self.source_ref,
            "attested_at": self.attested_at,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_permission_proof(raw: str, *, key_id: str) -> LunoPermissionProof:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid Luno permission proof JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("Luno permission proof must be an object")
    proof = LunoPermissionProof(
        schema=str(payload.get("schema", "")),
        key_id_sha256=str(payload.get("key_id_sha256", "")),
        permissions=tuple(str(item) for item in payload.get("permissions", ())),
        source_ref=str(payload.get("source_ref", "")),
        attested_at=str(payload.get("attested_at", "")),
    )
    proof.validate(key_id=key_id)
    return proof
