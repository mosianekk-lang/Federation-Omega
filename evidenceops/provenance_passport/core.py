"""Deterministic, dependency-free Provenance Passport builder and verifier.

The module handles only precomputed SHA-256 record hashes and non-sensitive
metadata. It does not read source evidence bytes or expose private corpus data.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_LEAF_PREFIX = b"EPP_LEAF_V1\x00"
_NODE_PREFIX = b"EPP_NODE_V1\x00"
_RECEIPT_PREFIX = b"EPP_RECEIPT_V1\x00"
_SCHEMA_VERSION = "evidenceops.provenance-passport/v1"


class PassportError(ValueError):
    """Raised when a manifest or passport fails deterministic validation."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PassportError(f"{field} must be a non-empty string")
    return value.strip()


def _require_sha256(value: Any, field: str) -> str:
    text = _require_string(value, field).lower()
    if not _HEX64.fullmatch(text):
        raise PassportError(f"{field} must be a lowercase 64-character SHA-256 hex digest")
    return text


def _normalise_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise PassportError("manifest must be an object")
    corpus_id = _require_string(manifest.get("corpus_id"), "corpus_id")
    records = manifest.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        raise PassportError("records must be a non-empty array")

    normalised: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(records):
        if not isinstance(raw, Mapping):
            raise PassportError(f"records[{index}] must be an object")
        record_id = _require_string(raw.get("record_id"), f"records[{index}].record_id")
        if record_id in seen:
            raise PassportError(f"duplicate record_id: {record_id}")
        seen.add(record_id)
        item: dict[str, Any] = {
            "record_id": record_id,
            "sha256": _require_sha256(raw.get("sha256"), f"records[{index}].sha256"),
        }
        if "metadata" in raw:
            metadata = raw["metadata"]
            if not isinstance(metadata, Mapping):
                raise PassportError(f"records[{index}].metadata must be an object")
            try:
                item["metadata"] = json.loads(_canonical_bytes(metadata).decode("utf-8"))
            except (TypeError, ValueError) as exc:
                raise PassportError(f"records[{index}].metadata must be JSON-compatible") from exc
        normalised.append(item)

    normalised.sort(key=lambda record: record["record_id"])
    return {"corpus_id": corpus_id, "records": normalised}


def _leaf_digest(record: Mapping[str, Any]) -> str:
    return _sha256(_LEAF_PREFIX + _canonical_bytes(record))


def _parent_digest(left_hex: str, right_hex: str) -> str:
    return _sha256(_NODE_PREFIX + bytes.fromhex(left_hex) + bytes.fromhex(right_hex))


def _merkle_levels(leaves: Sequence[str]) -> list[list[str]]:
    if not leaves:
        raise PassportError("at least one leaf is required")
    levels = [list(leaves)]
    current = list(leaves)
    while len(current) > 1:
        if len(current) % 2:
            current = current + [current[-1]]
        current = [
            _parent_digest(current[i], current[i + 1])
            for i in range(0, len(current), 2)
        ]
        levels.append(current)
    return levels


def _proof_for_index(levels: Sequence[Sequence[str]], index: int) -> list[dict[str, str]]:
    proof: list[dict[str, str]] = []
    cursor = index
    for level in levels[:-1]:
        padded = list(level)
        if len(padded) % 2:
            padded.append(padded[-1])
        if cursor % 2 == 0:
            sibling_index = cursor + 1
            side = "right"
        else:
            sibling_index = cursor - 1
            side = "left"
        proof.append({"side": side, "sha256": padded[sibling_index]})
        cursor //= 2
    return proof


def _passport_receipt(payload: Mapping[str, Any]) -> str:
    return _sha256(_RECEIPT_PREFIX + _canonical_bytes(payload))


def build_passport(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic passport with inclusion proofs for every record."""
    clean = _normalise_manifest(manifest)
    leaf_hashes = [_leaf_digest(record) for record in clean["records"]]
    levels = _merkle_levels(leaf_hashes)
    entries = []
    for index, (record, leaf_hash) in enumerate(zip(clean["records"], leaf_hashes)):
        entries.append(
            {
                "record": record,
                "leaf_sha256": leaf_hash,
                "proof": _proof_for_index(levels, index),
            }
        )

    body: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "corpus_id": clean["corpus_id"],
        "record_count": len(entries),
        "merkle_root": levels[-1][0],
        "records": entries,
        "algorithm": {
            "hash": "sha256",
            "record_order": "record_id_ascending",
            "odd_node_rule": "duplicate_last",
            "domain_separation": "EPP_LEAF_V1/EPP_NODE_V1/EPP_RECEIPT_V1",
        },
    }
    body["receipt_sha256"] = _passport_receipt(body)
    return body


def build_passports(manifests: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    passports = [build_passport(manifest) for manifest in manifests]
    ids = [passport["corpus_id"] for passport in passports]
    if len(ids) != len(set(ids)):
        raise PassportError("duplicate corpus_id across manifests")
    return passports


def _verify_proof(leaf_hash: str, proof: Sequence[Mapping[str, Any]], root: str) -> bool:
    current = leaf_hash
    for index, step in enumerate(proof):
        if not isinstance(step, Mapping):
            raise PassportError(f"proof[{index}] must be an object")
        side = step.get("side")
        sibling = _require_sha256(step.get("sha256"), f"proof[{index}].sha256")
        if side == "left":
            current = _parent_digest(sibling, current)
        elif side == "right":
            current = _parent_digest(current, sibling)
        else:
            raise PassportError(f"proof[{index}].side must be left or right")
    return current == root


def verify_passport(passport: Mapping[str, Any]) -> dict[str, Any]:
    """Verify schema, receipt, ordering, root and every inclusion proof."""
    if not isinstance(passport, Mapping):
        raise PassportError("passport must be an object")
    if passport.get("schema_version") != _SCHEMA_VERSION:
        raise PassportError("unsupported schema_version")
    corpus_id = _require_string(passport.get("corpus_id"), "corpus_id")
    root = _require_sha256(passport.get("merkle_root"), "merkle_root")
    receipt = _require_sha256(passport.get("receipt_sha256"), "receipt_sha256")
    records = passport.get("records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)) or not records:
        raise PassportError("passport records must be a non-empty array")
    if passport.get("record_count") != len(records):
        raise PassportError("record_count mismatch")

    receipt_body = deepcopy(dict(passport))
    receipt_body.pop("receipt_sha256", None)
    if _passport_receipt(receipt_body) != receipt:
        raise PassportError("passport receipt mismatch")

    presented_leaf_hashes: list[str] = []
    ids: list[str] = []
    for index, entry in enumerate(records):
        if not isinstance(entry, Mapping):
            raise PassportError(f"records[{index}] must be an object")
        record = entry.get("record")
        clean_record = _normalise_manifest({"corpus_id": corpus_id, "records": [record]})["records"][0]
        ids.append(clean_record["record_id"])
        expected_leaf = _leaf_digest(clean_record)
        presented_leaf = _require_sha256(entry.get("leaf_sha256"), f"records[{index}].leaf_sha256")
        if expected_leaf != presented_leaf:
            raise PassportError(f"records[{index}] leaf mismatch")
        proof = entry.get("proof")
        if not isinstance(proof, Sequence) or isinstance(proof, (str, bytes)):
            raise PassportError(f"records[{index}].proof must be an array")
        if not _verify_proof(presented_leaf, proof, root):
            raise PassportError(f"records[{index}] inclusion proof failed")
        presented_leaf_hashes.append(presented_leaf)

    if ids != sorted(ids):
        raise PassportError("records are not sorted by record_id")
    if len(ids) != len(set(ids)):
        raise PassportError("duplicate record_id in passport")
    recomputed_root = _merkle_levels(presented_leaf_hashes)[-1][0]
    if recomputed_root != root:
        raise PassportError("merkle_root mismatch")

    return {
        "ok": True,
        "corpus_id": corpus_id,
        "record_count": len(records),
        "merkle_root": root,
        "receipt_sha256": receipt,
    }


def verify_passports(passports: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    results = [verify_passport(passport) for passport in passports]
    ids = [result["corpus_id"] for result in results]
    if len(ids) != len(set(ids)):
        raise PassportError("duplicate corpus_id across passports")
    return {
        "ok": True,
        "corpus_count": len(results),
        "record_count": sum(result["record_count"] for result in results),
        "results": results,
    }
