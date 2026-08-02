"""Privacy-minimizing validators for metadata-only heartbeat traffic."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import PrivacyError

SENSITIVE_KEY_PARTS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "signing_key",
        "password",
        "passwd",
        "credential",
        "credentials",
        "authorization",
        "bearer",
        "cookie",
        "session",
        "secret",
        "token",
    }
)

RAW_CONTENT_KEYS = frozenset(
    {
        "prompt",
        "chat",
        "chat_body",
        "message",
        "message_body",
        "body",
        "content",
        "evidence",
        "document",
        "legal_content",
        "legal_text",
        "transcript",
        "attachment",
        "file_id",
        "folder_id",
        "document_id",
        "drive_id",
        "email",
        "phone",
        "name",
        "address",
        "person",
        "personal_data",
    }
)

EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL = re.compile(r"(?i)\b(?:https?|ftp)://")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){10,15}(?!\d)")
WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:\\")
UNIX_PERSONAL_PATH = re.compile(r"/(?:home|users|root)/")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
LONG_PROVIDER_ID = re.compile(r"[A-Za-z0-9_-]{20,}")
SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_.:-]{2,63}")
SAFE_HASH = re.compile(r"(?:sha256|hmac-sha256):[0-9a-f]{64}")
SAFE_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
NODE_CODE = re.compile(r"NODE-[A-Z0-9]{1,32}(?:-[0-9]{1,8})?")
OWNER_CODE = re.compile(r"OWNER-[A-F0-9]{8}")
MATTER_CODE = re.compile(r"MATTER-[A-F0-9]{8}")
MISSION_CODE = re.compile(r"MISSION-[A-F0-9]{8}")
CAPABILITY_CODE = re.compile(r"(?:CAP|CAPABILITY)-[A-Z0-9]{1,40}")
KEY_CODE = re.compile(r"KEY-NODE-[A-Z0-9]{1,32}(?:-[0-9]{1,8})?")
TRANSACTION_CODE = re.compile(r"TXN-(?:[A-Z0-9]{1,32}-)?[0-9]{4}")
MANIFEST_CODE = re.compile(r"RESPAWN-[A-Z0-9]{1,32}")
STOP_REASON_CODE = re.compile(r"STOP-[A-Z0-9]{1,32}")

SOURCE_CODES = frozenset({"LOCAL_BIBLE", "LOCAL_REPO", "FORMATION_STATE"})
CAPABILITY_CODES = frozenset(
    {"LOCAL_BIBLE_READBACK", "LOCAL_REPO_STATE", "FORMATION_STATE_READBACK"}
)
STATE_CODES = frozenset(
    {
        "ACCEPTED", "ADVANCED", "AUTHORIZED", "BLOCKED_WITH_ROUTE", "CANCELLED",
        "EMITTED", "FAILED", "NONE", "OPEN", "PARTIAL_PROVEN", "PROVEN", "READY",
        "RECORDED", "REGISTERED", "STOPPED", "VERIFIED",
    }
)
REFERENCE_CODES = frozenset({"DETACHED", "SYMBOLIC"})
VERSION_CODES = {
    "schema_version": frozenset({"HEARTBEAT-0.1"}),
    "adapter_version": frozenset({"LOCAL-0.1"}),
    "signing_version": frozenset({"HMAC-0.1"}),
    "version_code": frozenset({"HANDOFF-0.1"}),
}
CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    re.compile(r"A3T[A-Z0-9]{17}"),
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,255}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,255}"),
)


def normalize_key(key: str) -> str:
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key.strip())
    return re.sub(r"[-\s]+", "_", snake.lower())


def _key_is_sensitive(key: str) -> bool:
    normalized = normalize_key(key)
    return normalized in SENSITIVE_KEY_PARTS or any(
        normalized.endswith("_" + part) for part in SENSITIVE_KEY_PARTS
    )


def _key_is_raw(key: str) -> bool:
    normalized = normalize_key(key)
    return normalized in RAW_CONTENT_KEYS or any(
        normalized.endswith("_" + part) for part in RAW_CONTENT_KEYS
    )


def reject_sensitive_tree(value: Any, *, path: str = "$") -> None:
    """Reject credential labels, raw-content fields, callables, and PII shapes."""
    if callable(value):
        raise PrivacyError(f"CALLABLE_PROHIBITED:{path}")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise PrivacyError(f"NON_STRING_KEY:{path}")
            if _key_is_sensitive(key):
                raise PrivacyError(f"CREDENTIAL_LABEL_PROHIBITED:{path}.{normalize_key(key)}")
            if _key_is_raw(key):
                raise PrivacyError(f"RAW_CONTENT_KEY_PROHIBITED:{path}.{normalize_key(key)}")
            reject_sensitive_tree(child, path=f"{path}.{normalize_key(key)}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            reject_sensitive_tree(child, path=f"{path}[{index}]")
        return
    if isinstance(value, (bytes, bytearray)):
        raise PrivacyError(f"BINARY_PAYLOAD_PROHIBITED:{path}")
    if isinstance(value, str):
        if PRIVATE_KEY.search(value):
            raise PrivacyError(f"PRIVATE_KEY_MATERIAL_PROHIBITED:{path}")
        if any(pattern.search(value) for pattern in CREDENTIAL_VALUE_PATTERNS):
            raise PrivacyError(f"CREDENTIAL_VALUE_SHAPE_PROHIBITED:{path}")
        if EMAIL.search(value):
            raise PrivacyError(f"EMAIL_SHAPE_PROHIBITED:{path}")
        if URL.search(value):
            raise PrivacyError(f"URL_SHAPE_PROHIBITED:{path}")
        if PHONE.search(value):
            raise PrivacyError(f"PHONE_SHAPE_PROHIBITED:{path}")
        if WINDOWS_PATH.search(value) or UNIX_PERSONAL_PATH.search(value.lower()):
            raise PrivacyError(f"PERSONAL_PATH_PROHIBITED:{path}")
        if SAFE_CODE.fullmatch(value) or SAFE_HASH.fullmatch(value) or SAFE_TIMESTAMP.fullmatch(value):
            return
        if LONG_PROVIDER_ID.fullmatch(value) and not (
            SAFE_CODE.fullmatch(value) or SAFE_HASH.fullmatch(value)
        ):
            raise PrivacyError(f"OPAQUE_PROVIDER_ID_PROHIBITED:{path}")


def _code_rule_matches(value: str, *, field: str) -> bool:
    leaf = normalize_key(field.rsplit(".", 1)[-1])
    if leaf in {"node_id", "parent_node_id", "origin_node_id", "signing_node_id", "accepting_node_id", "master_node_id", "root_node_id", "from_node_id", "to_node_id", "node_code", "entity_code", "visited_node_ids"}:
        return NODE_CODE.fullmatch(value) is not None
    if leaf == "owner_code":
        return OWNER_CODE.fullmatch(value) is not None
    if leaf == "matter_code":
        return MATTER_CODE.fullmatch(value) is not None
    if leaf in {"mission_code", "id"} and ("mission" in normalize_key(field) or leaf == "mission_code"):
        return MISSION_CODE.fullmatch(value) is not None
    if leaf == "capability_code":
        return value in CAPABILITY_CODES or CAPABILITY_CODE.fullmatch(value) is not None
    if leaf == "source_code":
        return value in SOURCE_CODES
    if leaf in {"state_code", "mission_state"}:
        return value in STATE_CODES
    if leaf == "key_id":
        return KEY_CODE.fullmatch(value) is not None
    if leaf == "latest_transaction":
        return TRANSACTION_CODE.fullmatch(value) is not None
    if leaf in VERSION_CODES:
        return value in VERSION_CODES[leaf]
    if leaf == "reference_code":
        return value in REFERENCE_CODES
    if leaf in {"stop_reason_code", "reason_code"}:
        return value == "NONE" or STOP_REASON_CODE.fullmatch(value) is not None
    if leaf == "manifest_code":
        return MANIFEST_CODE.fullmatch(value) is not None
    return False


def require_code(value: str, *, field: str) -> str:
    if not isinstance(value, str) or SAFE_CODE.fullmatch(value) is None:
        raise PrivacyError(f"INVALID_PSEUDONYMOUS_CODE:{field}")
    reject_sensitive_tree(value, path=field)
    if not _code_rule_matches(value, field=field):
        raise PrivacyError(f"FIELD_CODE_NAMESPACE_MISMATCH:{field}")
    return value


def strict_json_loads(payload: str, *, field: str) -> Any:
    """Decode JSON while rejecting duplicate keys at every object depth."""
    if not isinstance(payload, str):
        raise PrivacyError(f"JSON_TEXT_REQUIRED:{field}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PrivacyError(f"DUPLICATE_JSON_KEY:{field}:{normalize_key(key)}")
            result[key] = value
        return result

    try:
        return json.loads(payload, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        raise PrivacyError(f"INVALID_JSON:{field}") from exc


def require_hash(value: str, *, field: str, hmac_allowed: bool = False) -> str:
    prefixes = ("sha256:", "hmac-sha256:") if hmac_allowed else ("sha256:",)
    if not isinstance(value, str) or not value.startswith(prefixes) or SAFE_HASH.fullmatch(value) is None:
        raise PrivacyError(f"INVALID_DIGEST:{field}")
    return value


def require_timestamp_shape(value: str, *, field: str) -> str:
    if not isinstance(value, str) or SAFE_TIMESTAMP.fullmatch(value) is None:
        raise PrivacyError(f"INVALID_UTC_TIMESTAMP:{field}")
    return value


def minimize_metadata(payload: Mapping[str, Any], *, allowed_keys: frozenset[str]) -> dict[str, Any]:
    """Return a canonical safe subset; reject instead of silently dropping data."""
    if not isinstance(payload, Mapping):
        raise PrivacyError("METADATA_OBJECT_REQUIRED")
    unknown = sorted(set(payload) - allowed_keys)
    if unknown:
        raise PrivacyError("UNKNOWN_METADATA_FIELDS:" + ",".join(unknown))
    result = dict(payload)
    reject_sensitive_tree(result)
    return result


def validate_explicit_metadata(
    payload: Mapping[str, Any],
    *,
    schema: Mapping[str, str],
) -> dict[str, Any]:
    """Validate an exact metadata schema; generic strings and extra keys are forbidden."""
    if not isinstance(payload, Mapping):
        raise PrivacyError("EXPLICIT_METADATA_OBJECT_REQUIRED")
    unknown = sorted(set(payload) - set(schema))
    missing = sorted(set(schema) - set(payload))
    if unknown:
        raise PrivacyError("UNKNOWN_EXPLICIT_METADATA_FIELDS:" + ",".join(unknown))
    if missing:
        raise PrivacyError("MISSING_EXPLICIT_METADATA_FIELDS:" + ",".join(missing))
    result = dict(payload)
    for key, kind in schema.items():
        value = result[key]
        if kind == "code":
            require_code(value, field=key)
        elif kind == "hash":
            require_hash(value, field=key)
        elif kind == "timestamp":
            require_timestamp_shape(value, field=key)
        elif kind == "boolean":
            if not isinstance(value, bool):
                raise PrivacyError(f"BOOLEAN_METADATA_REQUIRED:{key}")
        elif kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PrivacyError(f"NONNEGATIVE_INTEGER_METADATA_REQUIRED:{key}")
        else:
            raise PrivacyError(f"UNKNOWN_METADATA_SCHEMA_KIND:{key}")
    reject_sensitive_tree(result)
    return result
