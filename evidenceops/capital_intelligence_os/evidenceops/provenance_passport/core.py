"""Reusable EvidenceOps Provenance Passport primitives.

The implementation is dependency-free and intentionally separates:
1. structural validation,
2. Merkle integrity verification,
3. optional receipt verification, and
4. source-byte verification, which requires access to the source files.

A valid passport proves internal consistency of its declared hashes and proofs.
It does not, by itself, prove that the declared hashes match inaccessible source bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PASSPORT_SCHEMA_V1 = "EVIDENCEOPS_PROVENANCE_PASSPORT_V1"
PASSPORT_SCHEMA_V2 = "EVIDENCEOPS_PROVENANCE_PASSPORT_V2"
MERKLE_ALGORITHM = (
    "SHA256(raw_left_hash_bytes || raw_right_hash_bytes); duplicate final odd node"
)


class PassportValidationError(ValueError):
    """Raised when a passport cannot be built or parsed safely."""


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    passport_id: str
    leaf_count: int
    merkle_root: str
    proofs_checked: int
    receipt_status: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "passport_id": self.passport_id,
            "leaf_count": self.leaf_count,
            "merkle_root": self.merkle_root,
            "proofs_checked": self.proofs_checked,
            "receipt_status": self.receipt_status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_record_sha256(record: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(record))


def _require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise PassportValidationError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def merkle_root(leaves: Sequence[str]) -> str:
    """Compute a deterministic Merkle root from ordered SHA-256 hex leaves."""
    if not leaves:
        raise PassportValidationError("at least one Merkle leaf is required")
    level = [bytes.fromhex(_require_sha256(value, "leaf")) for value in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256(level[index] + level[index + 1]).digest()
            for index in range(0, len(level), 2)
        ]
    return level[0].hex()


def inclusion_proof(leaves: Sequence[str], leaf_index: int) -> list[dict[str, str]]:
    """Build an inclusion proof for one ordered leaf."""
    if not 0 <= leaf_index < len(leaves):
        raise PassportValidationError("leaf_index is outside the leaf list")
    level = [bytes.fromhex(_require_sha256(value, "leaf")) for value in leaves]
    index = leaf_index
    proof: list[dict[str, str]] = []
    while len(level) > 1:
        original_length = len(level)
        if original_length % 2:
            level.append(level[-1])
        sibling_index = index - 1 if index % 2 else index + 1
        sibling_position = "left" if sibling_index < index else "right"
        proof.append(
            {
                "position": sibling_position,
                "sha256": level[sibling_index].hex(),
            }
        )
        level = [
            hashlib.sha256(level[offset] + level[offset + 1]).digest()
            for offset in range(0, len(level), 2)
        ]
        index //= 2
    return proof


def verify_inclusion_proof(
    leaf: str,
    proof: Sequence[Mapping[str, Any]],
    expected_root: str,
) -> bool:
    """Verify a Merkle inclusion proof without requiring the full corpus."""
    current = bytes.fromhex(_require_sha256(leaf, "leaf"))
    expected = _require_sha256(expected_root, "expected_root")
    for step_index, step in enumerate(proof):
        if not isinstance(step, Mapping):
            raise PassportValidationError(f"proof step {step_index} must be an object")
        position = step.get("position")
        sibling = bytes.fromhex(
            _require_sha256(step.get("sha256"), f"proof step {step_index} sha256")
        )
        if position == "left":
            current = hashlib.sha256(sibling + current).digest()
        elif position == "right":
            current = hashlib.sha256(current + sibling).digest()
        else:
            raise PassportValidationError(
                f"proof step {step_index} position must be 'left' or 'right'"
            )
    return current.hex() == expected


def _receipt_payload(passport: Mapping[str, Any]) -> dict[str, Any]:
    payload = copy_mapping(passport)
    payload.pop("receipt", None)
    payload.pop("passport_receipt_sha256", None)
    return payload


def copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-copy JSON-compatible mappings without accepting custom objects."""
    return json.loads(json.dumps(value, ensure_ascii=False))


def attach_receipt(passport: Mapping[str, Any]) -> dict[str, Any]:
    """Attach a verifiable V2 canonical JSON receipt."""
    result = copy_mapping(passport)
    result.pop("receipt", None)
    result.pop("passport_receipt_sha256", None)
    digest = sha256_hex(canonical_json_bytes(result))
    result["receipt"] = {
        "algorithm": "SHA-256",
        "scope": "canonical_json_without_receipt",
        "sha256": digest,
    }
    return result


def build_record_passport(
    *,
    records: Sequence[Mapping[str, Any]],
    passport_id: str,
    source: Mapping[str, Any],
    classification: str = "PRIVATE_EVIDENCE_METADATA",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a passport whose leaves are canonical hashes of ordered records."""
    if not passport_id or not isinstance(passport_id, str):
        raise PassportValidationError("passport_id is required")
    if not records:
        raise PassportValidationError("records cannot be empty")
    record_copies = [copy_mapping(record) for record in records]
    leaves = [canonical_record_sha256(record) for record in record_copies]
    root = merkle_root(leaves)
    entries = []
    for index, (record, leaf) in enumerate(zip(record_copies, leaves)):
        record_id = (
            record.get("record_id")
            or record.get("Manifest ID")
            or record.get("id")
            or f"record-{index + 1:04d}"
        )
        entries.append(
            {
                "record_index": index,
                "record_id": str(record_id),
                "sha256": leaf,
                "merkle_leaf": leaf,
                "inclusion_proof": inclusion_proof(leaves, index),
            }
        )
    passport = {
        "passport_schema": PASSPORT_SCHEMA_V2,
        "passport_id": passport_id,
        "generated_at": generated_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "classification": classification,
        "source": copy_mapping(source),
        "integrity": {
            "hash_algorithm": "SHA-256",
            "merkle_algorithm": MERKLE_ALGORITHM,
            "leaf_definition": "SHA-256 of canonical ordered source record JSON",
            "leaf_order": "Source record order",
            "leaf_count": len(entries),
            "merkle_root": root,
            "proof_verification": "BUILT_AND_VERIFIED",
        },
        "files": entries,
        "limitations": [
            "This passport proves consistency of the captured canonical record hashes.",
            "It does not independently re-download or re-hash referenced source-file bytes.",
            "Source-system access and authorisation must be verified separately.",
        ],
    }
    result = attach_receipt(passport)
    validation = validate_passport(result)
    if not validation.valid:
        raise PassportValidationError(
            "newly built passport failed self-validation: "
            + "; ".join(validation.errors)
        )
    return result


def validate_passport(passport: Mapping[str, Any]) -> ValidationResult:
    """Validate schema, ordered leaves, Merkle root, proofs and V2 receipt."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(passport, Mapping):
        raise PassportValidationError("passport must be a JSON object")

    passport_id = str(passport.get("passport_id") or "")
    if not passport_id:
        errors.append("passport_id is missing")

    schema = passport.get("passport_schema")
    if schema not in {PASSPORT_SCHEMA_V1, PASSPORT_SCHEMA_V2}:
        errors.append(f"unsupported passport_schema: {schema!r}")

    integrity = passport.get("integrity")
    if not isinstance(integrity, Mapping):
        errors.append("integrity object is missing")
        integrity = {}

    files = passport.get("files")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty array")
        files = []

    declared_count = integrity.get("leaf_count")
    if declared_count != len(files):
        errors.append(
            f"leaf_count mismatch: declared {declared_count!r}, actual {len(files)}"
        )

    declared_root = integrity.get("merkle_root")
    leaves: list[str] = []
    proofs_checked = 0
    for index, item in enumerate(files):
        if not isinstance(item, Mapping):
            errors.append(f"files[{index}] must be an object")
            continue
        try:
            leaf = _require_sha256(item.get("sha256"), f"files[{index}].sha256")
            merkle_leaf = _require_sha256(
                item.get("merkle_leaf", leaf), f"files[{index}].merkle_leaf"
            )
        except PassportValidationError as exc:
            errors.append(str(exc))
            continue
        if merkle_leaf != leaf:
            errors.append(f"files[{index}] merkle_leaf differs from sha256")
        leaves.append(leaf)

    computed_root = ""
    if leaves and len(leaves) == len(files):
        try:
            computed_root = merkle_root(leaves)
            declared_root_checked = _require_sha256(declared_root, "integrity.merkle_root")
            if computed_root != declared_root_checked:
                errors.append(
                    f"Merkle root mismatch: declared {declared_root_checked}, "
                    f"computed {computed_root}"
                )
            for index, item in enumerate(files):
                proof = item.get("inclusion_proof")
                if not isinstance(proof, list):
                    errors.append(f"files[{index}].inclusion_proof must be an array")
                    continue
                try:
                    passed = verify_inclusion_proof(
                        leaves[index], proof, declared_root_checked
                    )
                except PassportValidationError as exc:
                    errors.append(f"files[{index}] proof error: {exc}")
                    continue
                proofs_checked += 1
                if not passed:
                    errors.append(f"files[{index}] inclusion proof failed")
        except PassportValidationError as exc:
            errors.append(str(exc))

    receipt_status = "ABSENT"
    receipt = passport.get("receipt")
    if isinstance(receipt, Mapping):
        algorithm = receipt.get("algorithm")
        scope = receipt.get("scope")
        digest = receipt.get("sha256")
        if algorithm != "SHA-256" or scope != "canonical_json_without_receipt":
            errors.append("receipt algorithm or scope is unsupported")
            receipt_status = "INVALID"
        else:
            try:
                declared_digest = _require_sha256(digest, "receipt.sha256")
                computed_digest = sha256_hex(
                    canonical_json_bytes(_receipt_payload(passport))
                )
                if declared_digest == computed_digest:
                    receipt_status = "VERIFIED"
                else:
                    receipt_status = "INVALID"
                    errors.append(
                        f"receipt mismatch: declared {declared_digest}, "
                        f"computed {computed_digest}"
                    )
            except PassportValidationError as exc:
                receipt_status = "INVALID"
                errors.append(str(exc))
    elif "passport_receipt_sha256" in passport:
        receipt_status = "LEGACY_EXTERNAL_UNCHECKED"
        warnings.append(
            "legacy passport_receipt_sha256 has no declared canonicalisation scope; "
            "Merkle integrity was checked but the legacy receipt was not recomputed"
        )

    if not computed_root and isinstance(declared_root, str):
        computed_root = declared_root

    return ValidationResult(
        valid=not errors,
        passport_id=passport_id,
        leaf_count=len(files),
        merkle_root=computed_root,
        proofs_checked=proofs_checked,
        receipt_status=receipt_status,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_many(passports: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    results = [validate_passport(passport).as_dict() for passport in passports]
    return {
        "valid": all(result["valid"] for result in results),
        "passport_count": len(results),
        "valid_count": sum(1 for result in results if result["valid"]),
        "results": results,
    }
