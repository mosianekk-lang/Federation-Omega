from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


SIGNED_FIELDS = (
    "schema",
    "task_id",
    "correlation_id",
    "task_type",
    "state",
    "started_at",
    "completed_at",
    "source_sha",
    "task_sha256",
    "result_sha256",
    "runner_sha256",
    "safety_sha256",
    "truth_boundary_sha256",
    "journal_head_sha256",
    "public_key_spki_b64",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def b64url_decode(value: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise ValueError("BASE64URL_VALUE_REQUIRED")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return value


def verify_journal(path: Path) -> list[str]:
    if not path.is_file():
        raise ValueError("JOURNAL_FILE_REQUIRED")
    previous = "0" * 64
    expected_sequence = 1
    hashes_seen: list[str] = []
    required = {
        "sequence",
        "previous_hash",
        "kind",
        "task_id",
        "task_sha256",
        "observed_at",
        "data",
        "entry_hash",
    }
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        entry = json.loads(raw)
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError("JOURNAL_ENTRY_SHAPE_INVALID")
        if entry["sequence"] != expected_sequence:
            raise ValueError("JOURNAL_SEQUENCE_INVALID")
        if entry["previous_hash"] != previous:
            raise ValueError("JOURNAL_PREDECESSOR_INVALID")
        digest = entry["entry_hash"]
        unsigned = dict(entry)
        unsigned.pop("entry_hash")
        if sha256_hex(canonical_bytes(unsigned)) != digest:
            raise ValueError("JOURNAL_DIGEST_INVALID")
        hashes_seen.append(digest)
        previous = digest
        expected_sequence += 1
    return hashes_seen


def verify_receipt(
    receipt: dict[str, Any],
    *,
    expected_source_sha: str | None = None,
    task: dict[str, Any] | None = None,
    journal_hashes: list[str] | None = None,
) -> dict[str, Any]:
    required = set(SIGNED_FIELDS) | {
        "runner",
        "result",
        "safety",
        "signed_payload_b64",
        "signature_der_b64",
        "truth_boundary",
    }
    if set(receipt) != required:
        raise ValueError("RECEIPT_SHAPE_INVALID")
    if receipt["schema"] != "FUSE-WINDOWS-NATIVE-RESULT-ATTESTATION-V1":
        raise ValueError("RECEIPT_SCHEMA_INVALID")
    if receipt["state"] != "COMPLETED_VERIFIED_NATIVE":
        raise ValueError("RECEIPT_STATE_INVALID")
    if sha256_hex(canonical_bytes(receipt["result"])) != receipt["result_sha256"]:
        raise ValueError("RESULT_HASH_MISMATCH")
    if sha256_hex(canonical_bytes(receipt["runner"])) != receipt["runner_sha256"]:
        raise ValueError("RUNNER_HASH_MISMATCH")
    if sha256_hex(canonical_bytes(receipt["safety"])) != receipt["safety_sha256"]:
        raise ValueError("SAFETY_HASH_MISMATCH")
    if sha256_hex(receipt["truth_boundary"].encode("utf-8")) != receipt["truth_boundary_sha256"]:
        raise ValueError("TRUTH_BOUNDARY_HASH_MISMATCH")
    if expected_source_sha and receipt["source_sha"].lower() != expected_source_sha.lower():
        raise ValueError("SOURCE_SHA_MISMATCH")
    if task is not None and sha256_hex(canonical_bytes(task)) != receipt["task_sha256"]:
        raise ValueError("TASK_HASH_MISMATCH")
    if journal_hashes is not None and receipt["journal_head_sha256"] not in journal_hashes:
        raise ValueError("RECEIPT_JOURNAL_HEAD_MISSING")

    signed_payload = b64url_decode(receipt["signed_payload_b64"])
    signed = json.loads(signed_payload)
    if not isinstance(signed, dict) or set(signed) != set(SIGNED_FIELDS):
        raise ValueError("SIGNED_PAYLOAD_SHAPE_INVALID")
    expected_signed = {field: receipt[field] for field in SIGNED_FIELDS}
    if signed != expected_signed:
        raise ValueError("SIGNED_PAYLOAD_FIELD_MISMATCH")
    if canonical_bytes(signed) != signed_payload:
        raise ValueError("SIGNED_PAYLOAD_NOT_CANONICAL")

    public_key = serialization.load_der_public_key(b64url_decode(receipt["public_key_spki_b64"]))
    if not isinstance(public_key, ec.EllipticCurvePublicKey) or not isinstance(public_key.curve, ec.SECP256R1):
        raise ValueError("P256_PUBLIC_KEY_REQUIRED")
    signature = b64url_decode(receipt["signature_der_b64"])
    try:
        public_key.verify(signature, signed_payload, ec.ECDSA(hashes.SHA256()))
    except Exception as exc:
        raise ValueError("RECEIPT_SIGNATURE_INVALID") from exc

    safety = receipt["safety"]
    for key in (
        "persistent_current_user_cng",
        "accepted_before_execute",
        "journal_hash_chain",
        "read_only_effect_ceiling",
    ):
        if safety.get(key) is not True:
            raise ValueError("SAFETY_POSITIVE_ASSERTION_MISSING:" + key)
    for key in ("network_usage", "shell_process_usage", "provider_mutation", "secret_access", "external_effect"):
        if safety.get(key) is not False:
            raise ValueError("SAFETY_NEGATIVE_ASSERTION_FAILED:" + key)

    return {
        "state": "VERIFIED",
        "task_id": receipt["task_id"],
        "task_type": receipt["task_type"],
        "source_sha": receipt["source_sha"],
        "task_sha256": receipt["task_sha256"],
        "result_sha256": receipt["result_sha256"],
        "journal_head_sha256": receipt["journal_head_sha256"],
        "public_key_sha256": sha256_hex(b64url_decode(receipt["public_key_spki_b64"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--source-sha")
    parser.add_argument("--task")
    parser.add_argument("--journal")
    args = parser.parse_args()
    receipt = load_json(Path(args.receipt))
    task = load_json(Path(args.task)) if args.task else None
    journal_hashes = verify_journal(Path(args.journal)) if args.journal else None
    result = verify_receipt(
        receipt,
        expected_source_sha=args.source_sha,
        task=task,
        journal_hashes=journal_hashes,
    )
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
