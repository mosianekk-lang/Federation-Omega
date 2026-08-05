from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA = "FEDOMEGA-AWARENESS-HASH-DOMAIN-RECONCILIATION-2"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile("github" + r"_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)

LOGICAL_CONTROL_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("Manifest ID", "manifest_id", "string"),
    ("Version", "version", "string"),
    ("Owner / Final Authority", "owner", "string"),
    ("Public Contract Alias", "public_contract_alias", "string"),
    ("Private Manifest Alias", "private_manifest_alias", "string"),
    ("Credential Value Recorded", "credential_value_recorded", "bool"),
    ("Provider Authority Inferred from Storage", "provider_authority_inferred_from_storage", "bool"),
    ("Hidden Cross-Chat Access Claimed", "hidden_cross_chat_access_claimed", "bool"),
    ("Runtime Readback Required", "runtime_readback_required", "bool"),
    ("Current Bootstrap Block", "current_bootstrap_block", "string"),
)
RUNTIME_ONLY_CONTROL_FIELDS: tuple[str, ...] = (
    "Created At",
    "Current GitHub Main",
    "Reconciler Source Merge",
    "Registered Surface Count",
    "Credential Handle Count",
    "Automation Asset Count",
    "Read-Proven Provider Count",
    "Effectful Successor Build Count",
    "Current State",
    "Final Reconciliation SHA-256",
)
MUTABLE_RUNTIME_FIELDS: frozenset[str] = frozenset(
    {"Current GitHub Main", "Current State", "Final Reconciliation SHA-256"}
)


class HashDomainError(RuntimeError):
    """Fail-closed awareness hash-domain or rollback validation error."""


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def reject_secret_material(value: Any, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in {
                "token", "secret", "password", "api_key",
                "credential_value", "private_key",
            }:
                raise HashDomainError(f"secret-bearing field prohibited: {path}.{key}")
            reject_secret_material(item, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            reject_secret_material(item, f"{path}[{index}]")
    elif isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise HashDomainError(f"secret-shaped value prohibited at {path}")


def _bool(value: Any, field: str) -> bool:
    normalized = str(value).strip().upper()
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    raise HashDomainError(f"{field} must be TRUE or FALSE")


def control_map(control_table: Sequence[Sequence[Any]]) -> dict[str, dict[str, str]]:
    reject_secret_material(control_table, "control_table")
    mapped: dict[str, dict[str, str]] = {}
    header_seen = False
    for row in control_table:
        values = [str(item).strip() for item in row]
        if len(values) >= 3 and values[:3] == ["Field", "Value", "Verification"]:
            header_seen = True
            continue
        if not header_seen or not values or not values[0]:
            continue
        field = values[0]
        if field in mapped:
            raise HashDomainError(f"duplicate CONTROL field: {field}")
        mapped[field] = {
            "value": values[1] if len(values) > 1 else "",
            "verification": values[2] if len(values) > 2 else "",
        }
    if not header_seen:
        raise HashDomainError("CONTROL header not found")
    return mapped


def project_logical_control(control: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    logical: dict[str, Any] = {}
    for label, key, value_type in LOGICAL_CONTROL_FIELDS:
        if label not in control:
            raise HashDomainError(f"missing logical CONTROL field: {label}")
        raw = control[label].get("value", "")
        logical[key] = _bool(raw, label) if value_type == "bool" else str(raw).strip()
        if value_type == "string" and not logical[key]:
            raise HashDomainError(f"logical CONTROL field is empty: {label}")
    return logical


def project_runtime_control(control: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    missing = [field for field in RUNTIME_ONLY_CONTROL_FIELDS if field not in control]
    if missing:
        raise HashDomainError(f"missing runtime CONTROL fields: {missing}")
    return {
        field: {
            "value": str(control[field].get("value", "")).strip(),
            "verification": str(control[field].get("verification", "")).strip(),
        }
        for field in RUNTIME_ONLY_CONTROL_FIELDS
    }


def _validate_hash(value: str, name: str, pattern: re.Pattern[str]) -> str:
    normalized = str(value).strip().lower()
    if not pattern.fullmatch(normalized):
        raise HashDomainError(f"{name} has invalid hash format")
    return normalized


def _apply_updates(
    control: Mapping[str, Mapping[str, str]], updates: Mapping[str, Mapping[str, str]]
) -> dict[str, dict[str, str]]:
    disallowed = sorted(set(updates) - MUTABLE_RUNTIME_FIELDS)
    if disallowed:
        raise HashDomainError(f"candidate update touches non-runtime fields: {disallowed}")
    result = deepcopy({key: dict(value) for key, value in control.items()})
    for field, update in updates.items():
        if field not in result:
            raise HashDomainError(f"candidate update targets missing field: {field}")
        if "value" in update:
            result[field]["value"] = str(update["value"])
        if "verification" in update:
            result[field]["verification"] = str(update["verification"])
    return result


def plan_freshness_reconciliation(
    *,
    control_table: Sequence[Sequence[Any]],
    observed_main: str,
    expected_legacy_logical_sha256: str,
    expected_logical_sha256_v2: str,
    previous_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    control = control_map(control_table)
    observed = _validate_hash(observed_main, "observed_main", HEX40)
    expected_legacy = _validate_hash(
        expected_legacy_logical_sha256, "expected_legacy_logical_sha256", HEX64
    )
    expected_v2 = _validate_hash(
        expected_logical_sha256_v2, "expected_logical_sha256_v2", HEX64
    )
    if previous_receipt_sha256 is not None:
        previous_receipt_sha256 = _validate_hash(
            previous_receipt_sha256, "previous_receipt_sha256", HEX64
        )

    stored_legacy = _validate_hash(
        control.get("Private Manifest Logical SHA-256", {}).get("value", ""),
        "stored legacy logical SHA-256",
        HEX64,
    )
    if stored_legacy != expected_legacy:
        raise HashDomainError("legacy logical hash differs from the public contract")

    logical_before = project_logical_control(control)
    logical_before_sha256 = canonical_sha256(logical_before)
    if logical_before_sha256 != expected_v2:
        raise HashDomainError("v2 logical projection differs from the public contract")

    runtime_before = project_runtime_control(control)
    runtime_before_sha256 = canonical_sha256(runtime_before)
    stored_main = _validate_hash(
        runtime_before["Current GitHub Main"]["value"], "stored Current GitHub Main", HEX40
    )
    stale = stored_main != observed

    proposed_state = (
        "HASH_DOMAIN_V2_RECONCILED_RUNTIME_FRESH"
        if stale else "HASH_DOMAIN_V2_RUNTIME_ALREADY_FRESH"
    )
    transaction_body = {
        "schema": SCHEMA,
        "observed_main": observed,
        "stored_main": stored_main,
        "legacy_logical_sha256": expected_legacy,
        "logical_sha256_v2": expected_v2,
        "runtime_before_sha256": runtime_before_sha256,
        "proposed_state": proposed_state,
        "previous_receipt_sha256": previous_receipt_sha256,
    }
    transaction_sha256 = canonical_sha256(transaction_body)
    updates = {
        "Current GitHub Main": {
            "value": observed,
            "verification": "PROVIDER_READBACK_CURRENT_HEAD_HASH_DOMAIN_V2",
        },
        "Current State": {
            "value": proposed_state,
            "verification": "BUILD_AO_010_HASH_DOMAIN_V2",
        },
        "Final Reconciliation SHA-256": {
            "value": transaction_sha256,
            "verification": "HASH_DOMAIN_V2_TRANSACTION",
        },
    }
    candidate = _apply_updates(control, updates)
    logical_after = project_logical_control(candidate)
    logical_after_sha256 = canonical_sha256(logical_after)
    runtime_after = project_runtime_control(candidate)
    runtime_after_sha256 = canonical_sha256(runtime_after)

    rollback_updates = {
        field: {
            "value": runtime_before[field]["value"],
            "verification": runtime_before[field]["verification"],
        }
        for field in MUTABLE_RUNTIME_FIELDS
    }
    rolled_back = _apply_updates(candidate, rollback_updates)
    rollback_runtime_sha256 = canonical_sha256(project_runtime_control(rolled_back))

    checks = {
        "legacy_hash_preserved": stored_legacy == expected_legacy,
        "logical_v2_before_matches_contract": logical_before_sha256 == expected_v2,
        "logical_v2_unchanged_by_runtime_patch": logical_after_sha256 == logical_before_sha256,
        "runtime_patch_changes_runtime_domain_when_stale": (
            runtime_after_sha256 != runtime_before_sha256 if stale else True
        ),
        "rollback_restores_runtime_domain": rollback_runtime_sha256 == runtime_before_sha256,
        "patch_fields_runtime_only": set(updates).issubset(MUTABLE_RUNTIME_FIELDS),
        "credential_value_recorded_false": True,
        "provider_mutation_performed_false": True,
    }
    if not all(checks.values()):
        raise HashDomainError("hash-domain canary failed")

    result = {
        "schema": SCHEMA,
        "status": "APPLY_ELIGIBLE" if stale else "NO_CHANGE_VERIFIED",
        "observed_main": observed,
        "stored_main": stored_main,
        "stale_runtime_head": stale,
        "legacy_logical_sha256": expected_legacy,
        "logical_sha256_v2": expected_v2,
        "logical_projection": logical_before,
        "runtime_before_sha256": runtime_before_sha256,
        "runtime_after_sha256": runtime_after_sha256,
        "rollback_runtime_sha256": rollback_runtime_sha256,
        "transaction_sha256": transaction_sha256,
        "patch_plan": updates if stale else {},
        "rollback_plan": rollback_updates if stale else {},
        "checks": checks,
        "previous_receipt_sha256": previous_receipt_sha256,
        "credential_value_recorded": False,
        "provider_mutation_performed": False,
        "external_effect_performed": False,
        "truth_boundary": (
            "This receipt proves hash-domain separation, an in-memory patch plan and rollback. "
            "It does not prove that Google Drive was mutated until exact provider readback is attached."
        ),
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result
