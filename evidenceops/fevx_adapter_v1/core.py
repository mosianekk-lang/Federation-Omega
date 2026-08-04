from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ADAPTER_VERSION = "1.0.0"
INPUT_SCHEMA = "EVIDENCEOPS_FEVX_INPUT_V1"
OUTPUT_SCHEMA = "EVIDENCEOPS_FEVX_DERIVED_OUTPUT_V1"
PROOF_SCHEMA = "EVIDENCEOPS_FEVX_PROOF_V1"

HELD_ACTIONS = {
    "SEND_EMAIL", "SEND_MESSAGE", "EXTERNAL_SEND", "LEGAL_FILE",
    "LEGAL_FILING", "PUBLISH", "PUBLIC_PUBLISH", "MAKE_PAYMENT",
    "ISSUE_INVOICE", "ACCEPT_CONTRACT", "DELETE", "DESTRUCTIVE_MUTATION",
    "DISCLOSE_SENSITIVE_DATA", "PRODUCTION_DEPLOY", "WRITE_VERIFIED_FACT",
    "MUTATE_SOURCE", "CROSS_CASE_READ", "CROSS_CASE_WRITE",
}

FORBIDDEN_TRUE_KEYS = {
    "external_effect", "external_send", "legal_filing", "financial_action",
    "payment", "public_publish", "destructive_action", "source_write",
    "source_mutation", "fact_write", "verified_fact_write",
    "cross_case_access", "cross_case_write", "production_deployment",
    "sensitive_data_disclosure",
}

VOLATILE_KEYS = {
    "created_at", "recorded_at", "updated_at", "timestamp", "run_id",
    "proof_id", "event_hash", "previous_hash", "checkpoint_id",
    "sequence", "idempotent",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def digest(value: Any) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def clone(value: Any) -> Any:
    return copy.deepcopy(value)


def semantic(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: semantic(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [semantic(item) for item in value]
    return value


def semantic_digest(value: Any) -> str:
    return digest(semantic(value))


def walk(value: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, (*path, str(index)))


def all_values_for_key(value: Any, key_name: str) -> list[Any]:
    rows: list[Any] = []
    for path, item in walk(value):
        if path and path[-1] == key_name:
            rows.append(item)
    return rows


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def ensure_hex_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def stable_identifier(prefix: str, *values: Any, length: int = 24) -> str:
    return f"{prefix}-{digest(list(values))[:length]}"
