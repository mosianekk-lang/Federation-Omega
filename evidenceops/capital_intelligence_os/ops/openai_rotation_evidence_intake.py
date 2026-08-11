#!/usr/bin/env python3
"""Validate redacted, hash-bound provider evidence for OpenAI key rotation.

This module is an A1_INTERNAL evidence intake. It performs no provider call,
credential read, provider mutation, deployment, revocation, communication, or
production promotion. It accepts metadata and redacted provider receipts only.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MANIFEST_SCHEMA = "FEDOMEGA-OPENAI-CREDENTIAL-ROTATION-1"
EVIDENCE_SCHEMA = "FEDOMEGA-OPENAI-ROTATION-PROVIDER-EVIDENCE-2"
INTAKE_SCHEMA = "FEDOMEGA-OPENAI-ROTATION-EVIDENCE-INTAKE-2"
CLOSURE_SCHEMA = "FEDOMEGA-OPENAI-CREDENTIAL-ROTATION-RECEIPT-1"

DESTINATION_IDS = {"mosiane-live-thread", "modisa-legal-v2"}
DESTINATION_EVIDENCE_TYPES = {
    "SECRET_METADATA_READBACK",
    "RUNTIME_IDENTITY_READBACK",
    "SECRET_REFERENCE_BINDING_READBACK",
    "ROLLBACK_TARGET_CAPTURE",
    "CANARY_HEALTH",
    "SEMANTIC_PROBE",
}
PROVIDER_EVIDENCE_TYPES = {
    "KEY_CREATION_ASSERTION",
    "EXPOSED_KEY_REVOCATION",
    "EXPOSED_KEY_REJECTION",
}
EVIDENCE_TYPES = DESTINATION_EVIDENCE_TYPES | PROVIDER_EVIDENCE_TYPES

FRESHNESS_SECONDS = {
    "SECRET_METADATA_READBACK": 86400,
    "RUNTIME_IDENTITY_READBACK": 86400,
    "SECRET_REFERENCE_BINDING_READBACK": 3600,
    "ROLLBACK_TARGET_CAPTURE": 3600,
    "CANARY_HEALTH": 1800,
    "SEMANTIC_PROBE": 1800,
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
KEY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])" + "sk-" + r"(?:proj-)?" + r"[A-Za-z0-9_-]{20,}"
)


class RotationEvidenceError(ValueError):
    """Fail-closed provider evidence error."""


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _iter_strings(item)


def reject_credential_material(payload: Any) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).lower() in {
                "token", "secret_value", "credential_value", "api_key",
                "private_key", "password", "authorization_header",
            }:
                raise RotationEvidenceError(f"secret-bearing field prohibited: {key}")
            reject_credential_material(value)
    elif isinstance(payload, Sequence) and not isinstance(
        payload, (str, bytes, bytearray)
    ):
        for item in payload:
            reject_credential_material(item)
    elif isinstance(payload, str) and KEY_PATTERN.search(payload):
        raise RotationEvidenceError("raw OpenAI credential pattern detected")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RotationEvidenceError(message)


def _parse_time(value: Any, label: str) -> datetime:
    _require(
        isinstance(value, str) and ISO_Z.fullmatch(value) is not None,
        f"{label} must be an ISO-8601 UTC timestamp",
    )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RotationEvidenceError(f"{label} is invalid") from exc
    return parsed.astimezone(timezone.utc)


def _verify_self_hash(payload: Mapping[str, Any], field: str, label: str) -> str:
    claimed = str(payload.get(field) or "").lower()
    _require(HEX64.fullmatch(claimed) is not None, f"{label} hash is invalid")
    body = dict(payload)
    body.pop(field, None)
    _require(canonical_sha256(body) == claimed, f"{label} hash verification failed")
    return claimed


def _manifest_destinations(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    reject_credential_material(manifest)
    _require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema mismatch")
    _require(bool(manifest.get("manifest_id")), "manifest_id is required")
    destinations = manifest.get("destinations")
    _require(
        isinstance(destinations, list) and len(destinations) == 2,
        "exactly two manifest destinations are required",
    )
    mapped: dict[str, dict[str, Any]] = {}
    for item in destinations:
        _require(isinstance(item, Mapping), "manifest destination must be an object")
        destination_id = str(item.get("destination_id") or "")
        _require(destination_id in DESTINATION_IDS, "unexpected manifest destination")
        _require(destination_id not in mapped, "duplicate manifest destination")
        mapped[destination_id] = dict(item)
    _require(set(mapped) == DESTINATION_IDS, "manifest destination set incomplete")
    return mapped


def _gate_key(evidence_type: str, destination_id: str | None) -> str:
    return f"{destination_id}:{evidence_type}" if destination_id else evidence_type


def required_gate_keys() -> set[str]:
    keys = {
        "KEY_CREATION_ASSERTION",
        "EXPOSED_KEY_REVOCATION",
        "EXPOSED_KEY_REJECTION",
    }
    for destination_id in DESTINATION_IDS:
        for evidence_type in DESTINATION_EVIDENCE_TYPES:
            keys.add(_gate_key(evidence_type, destination_id))
    return keys


def _validate_common(
    evidence: Mapping[str, Any],
    *,
    manifest_id: str,
    evaluated_at: datetime,
) -> tuple[str, str | None, datetime]:
    reject_credential_material(evidence)
    _require(evidence.get("schema") == EVIDENCE_SCHEMA, "evidence schema mismatch")
    _verify_self_hash(evidence, "evidence_sha256", "provider evidence")
    _require(evidence.get("manifest_id") == manifest_id, "evidence manifest mismatch")
    _require(bool(evidence.get("evidence_id")), "evidence_id is required")
    evidence_type = str(evidence.get("evidence_type") or "")
    _require(evidence_type in EVIDENCE_TYPES, "unsupported evidence_type")
    destination_id = evidence.get("destination_id")
    if evidence_type in DESTINATION_EVIDENCE_TYPES:
        _require(
            destination_id in DESTINATION_IDS,
            "destination evidence requires destination_id",
        )
    else:
        _require(
            destination_id is None,
            "provider-level evidence cannot name a destination",
        )
    _require(
        evidence.get("plaintext_observed") is False,
        "plaintext credential observation is prohibited",
    )
    _require(
        evidence.get("credential_value_recorded") is False,
        "credential value recording is prohibited",
    )
    _require(
        evidence.get("intake_provider_mutation_performed") is False,
        "evidence intake must not mutate a provider",
    )
    _require(
        evidence.get("external_effect_performed") is False,
        "evidence intake must not perform an external effect",
    )
    _require(
        bool(str(evidence.get("provider_reference") or "").strip()),
        "provider_reference is required",
    )
    observed_at = _parse_time(evidence.get("observed_at"), "observed_at")
    _require(observed_at <= evaluated_at, "evidence observed_at is in the future")
    max_age = FRESHNESS_SECONDS.get(evidence_type)
    if max_age is not None:
        age = (evaluated_at - observed_at).total_seconds()
        _require(age <= max_age, f"{evidence_type} evidence is stale")
    return evidence_type, destination_id, observed_at


def _validate_destination_details(
    evidence_type: str,
    destination_id: str,
    details: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> None:
    if evidence_type == "SECRET_METADATA_READBACK":
        _require(
            details.get("secret_id") == expected.get("secret_id"),
            "secret metadata reference mismatch",
        )
        _require(details.get("payload_read") is False, "secret payload must not be read")
        _require(
            details.get("metadata_readback") is True,
            "secret metadata readback missing",
        )
    elif evidence_type == "RUNTIME_IDENTITY_READBACK":
        _require(
            bool(str(details.get("runtime_identity") or "").strip()),
            "runtime identity readback missing",
        )
        if destination_id == "mosiane-live-thread":
            _require(
                details.get("runtime_identity") == expected.get("runtime_identity"),
                "Live Thread runtime identity mismatch",
            )
            _require(
                details.get("runtime_service") == expected.get("runtime_service"),
                "Live Thread runtime service mismatch",
            )
        else:
            _require(
                details.get("private_execution_plane") is True,
                "MODISA private execution plane is unproven",
            )
    elif evidence_type == "SECRET_REFERENCE_BINDING_READBACK":
        _require(
            details.get("secret_id") == expected.get("secret_id"),
            "bound secret reference mismatch",
        )
        _require(
            details.get("runtime_environment_name") == "OPENAI_API_KEY",
            "runtime environment contract mismatch",
        )
        _require(
            details.get("literal_value_present") is False,
            "literal credential binding is prohibited",
        )
        _require(
            details.get("reference_readback") is True,
            "secret-reference binding readback missing",
        )
    elif evidence_type == "ROLLBACK_TARGET_CAPTURE":
        _require(
            bool(str(details.get("rollback_target") or "").strip()),
            "rollback target is required",
        )
        _require(
            details.get("rollback_target_readback") is True,
            "rollback target readback missing",
        )
    elif evidence_type == "CANARY_HEALTH":
        _require(details.get("health_verified") is True, "canary health proof missing")
        if destination_id == "mosiane-live-thread":
            _require(
                details.get("traffic_percent") == 0,
                "Live Thread canary must remain zero traffic",
            )
        else:
            _require(
                details.get("isolated_non_production") is True,
                "MODISA canary must be isolated",
            )
            _require(
                details.get("external_actions_disabled") is True,
                "MODISA external actions must remain disabled",
            )
    elif evidence_type == "SEMANTIC_PROBE":
        _require(bool(str(details.get("trace_id") or "").strip()), "trace_id is required")
        _require(
            bool(str(details.get("semantic_fingerprint") or "").strip()),
            "semantic fingerprint is required",
        )
        if destination_id == "mosiane-live-thread":
            _require(
                details.get("hash_chain_valid") is True,
                "Live Thread hash-chain proof missing",
            )
            _require(
                details.get("action_specific_response") is True,
                "Live Thread action-specific semantic proof missing",
            )
        else:
            _require(
                details.get("seven_independent_opinions") is True,
                "MODISA seven-opinion proof missing",
            )
            _require(
                details.get("council_complete") is True,
                "MODISA council completion missing",
            )
            _require(
                details.get("proof_bound_release") is True,
                "MODISA proof-bound release missing",
            )
            _require(
                details.get("external_actions_disabled") is True,
                "MODISA external actions must remain disabled",
            )


def validate_evidence(
    evidence: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    evaluated_at: datetime,
) -> dict[str, Any]:
    destinations = _manifest_destinations(manifest)
    evidence_type, destination_id, _ = _validate_common(
        evidence,
        manifest_id=str(manifest["manifest_id"]),
        evaluated_at=evaluated_at.astimezone(timezone.utc),
    )
    details = evidence.get("details")
    _require(isinstance(details, Mapping), "evidence details must be an object")
    provider_native = evidence.get("provider_native")
    owner_attested = evidence.get("owner_attested")

    if evidence_type == "KEY_CREATION_ASSERTION":
        _require(
            provider_native is True or owner_attested is True,
            "key creation requires provider proof or owner attestation",
        )
        _require(
            details.get("display_name") == manifest["provider_key"]["display_name"],
            "provider key display name mismatch",
        )
        _require(details.get("created") is True, "replacement key creation is unproven")
    else:
        _require(
            provider_native is True,
            f"{evidence_type} requires provider-native proof",
        )
        _require(
            owner_attested is False,
            "owner assertion cannot replace provider-native proof",
        )

    if evidence_type in DESTINATION_EVIDENCE_TYPES:
        _validate_destination_details(
            evidence_type,
            str(destination_id),
            details,
            destinations[str(destination_id)],
        )
    elif evidence_type == "EXPOSED_KEY_REVOCATION":
        _require(details.get("revoked") is True, "exposed key revocation is unproven")
        _require(
            details.get("revocation_readback") is True,
            "provider revocation readback missing",
        )
    elif evidence_type == "EXPOSED_KEY_REJECTION":
        _require(details.get("rejected") is True, "exposed key rejection is unproven")
        _require(
            details.get("response_class") == "AUTHENTICATION_REJECTED",
            "old-key rejection response class mismatch",
        )
        _require(
            details.get("tested_value_recorded") is False,
            "tested key value must not be recorded",
        )

    return copy.deepcopy(dict(evidence))


def evaluate_evidence(
    *,
    manifest: Mapping[str, Any],
    evidence_items: Sequence[Mapping[str, Any]],
    evaluated_at: datetime,
) -> dict[str, Any]:
    _manifest_destinations(manifest)
    _require(evaluated_at.tzinfo is not None, "evaluated_at must include timezone")
    evaluated = evaluated_at.astimezone(timezone.utc)
    seen_ids: set[str] = set()
    seen_gates: set[str] = set()
    seen_refs: set[str] = set()
    semantic_fingerprints: set[str] = set()
    accepted: list[dict[str, Any]] = []

    for raw in evidence_items:
        item = validate_evidence(raw, manifest=manifest, evaluated_at=evaluated)
        evidence_id = str(item["evidence_id"])
        _require(evidence_id not in seen_ids, "duplicate evidence_id")
        seen_ids.add(evidence_id)
        evidence_type = str(item["evidence_type"])
        destination_id = item.get("destination_id")
        gate = _gate_key(evidence_type, destination_id)
        _require(gate not in seen_gates, f"duplicate evidence gate: {gate}")
        seen_gates.add(gate)
        provider_reference = str(item["provider_reference"])
        _require(
            provider_reference not in seen_refs,
            "provider_reference cannot be reused across evidence",
        )
        seen_refs.add(provider_reference)
        if evidence_type == "SEMANTIC_PROBE":
            fingerprint = str(item["details"]["semantic_fingerprint"])
            _require(
                fingerprint not in semantic_fingerprints,
                "semantic fingerprint cannot be reused across destinations",
            )
            semantic_fingerprints.add(fingerprint)
        accepted.append(item)

    required = required_gate_keys()
    open_gates = sorted(required - seen_gates)
    status = (
        "COMPLETE_PROVIDER_EVIDENCE_CLOSURE_ELIGIBLE"
        if not open_gates
        else "INCOMPLETE_PROVIDER_EVIDENCE_OPEN_GATES"
    )
    receipt: dict[str, Any] = {
        "schema": INTAKE_SCHEMA,
        "manifest_id": manifest["manifest_id"],
        "status": status,
        "evaluated_at": evaluated.isoformat().replace("+00:00", "Z"),
        "accepted_evidence_count": len(accepted),
        "accepted_evidence_ids": sorted(seen_ids),
        "covered_gates": sorted(seen_gates),
        "open_gates": open_gates,
        "credential_value_recorded": False,
        "provider_mutation_performed": False,
        "external_effect_performed": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def build_closure_receipt_candidate(
    *,
    manifest: Mapping[str, Any],
    evidence_items: Sequence[Mapping[str, Any]],
    evaluated_at: datetime,
) -> dict[str, Any]:
    intake = evaluate_evidence(
        manifest=manifest,
        evidence_items=evidence_items,
        evaluated_at=evaluated_at,
    )
    _require(not intake["open_gates"], "provider evidence set is incomplete")
    by_gate = {
        _gate_key(str(item["evidence_type"]), item.get("destination_id")): item
        for item in evidence_items
    }
    destinations = []
    for item in manifest["destinations"]:
        destination_id = item["destination_id"]
        destinations.append(
            {
                "destination_id": destination_id,
                "secret_id": item["secret_id"],
                "secret_reference_readback": True,
                "least_privilege_identity_readback": True,
                "canary_health_verified": True,
                "semantic_probe_verified": True,
                "rollback_target_captured": True,
                "production_promotion": False,
                "evidence_sha256": {
                    evidence_type: by_gate[
                        _gate_key(evidence_type, destination_id)
                    ]["evidence_sha256"]
                    for evidence_type in sorted(DESTINATION_EVIDENCE_TYPES)
                },
            }
        )
    closure: dict[str, Any] = {
        "schema": CLOSURE_SCHEMA,
        "manifest_id": manifest["manifest_id"],
        "plaintext_observed": False,
        "destinations": destinations,
        "provider_closure": {
            "exposed_key_revoked": True,
            "exposed_key_rejection_verified": True,
            "revocation_evidence_sha256": by_gate[
                "EXPOSED_KEY_REVOCATION"
            ]["evidence_sha256"],
            "rejection_evidence_sha256": by_gate[
                "EXPOSED_KEY_REJECTION"
            ]["evidence_sha256"],
        },
        "evidence_intake_receipt_sha256": intake["receipt_sha256"],
        "completion_state": "COMPLETE_REDACTED_AND_VERIFIED",
    }
    closure["closure_receipt_sha256"] = canonical_sha256(closure)
    reject_credential_material(closure)
    return closure


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RotationEvidenceError(f"unable to read JSON: {path}") from exc


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--closure-output", type=Path)
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    evidence = load_json(args.evidence)
    _require(isinstance(evidence, list), "evidence file must contain a list")
    evaluated_at = _parse_time(args.evaluated_at, "evaluated_at")
    receipt = evaluate_evidence(
        manifest=manifest,
        evidence_items=evidence,
        evaluated_at=evaluated_at,
    )
    write_json(args.output, receipt)
    if args.closure_output and not receipt["open_gates"]:
        closure = build_closure_receipt_candidate(
            manifest=manifest,
            evidence_items=evidence,
            evaluated_at=evaluated_at,
        )
        write_json(args.closure_output, closure)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if not receipt["open_gates"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
