from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .provider_canary import ProviderObservation, ProviderObservationCanary


CAPSULE_SCHEMA = "AO_HARMONIC_V3_PROVIDER_WORKFLOW_CAPSULE_V1"
RECEIPT_SCHEMA = "AO_HARMONIC_V3_PROVIDER_WORKFLOW_RECEIPT_V1"
_ALLOWED_PRIVACY_MODELS = {"SANITIZED_METADATA_ONLY"}
_ALLOWED_PROVIDER_RUNTIMES = {"GITHUB_ACTIONS"}


def _canonical_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_capsule(payload: dict[str, Any]) -> None:
    if payload.get("schema") != CAPSULE_SCHEMA:
        raise ValueError("unsupported provider workflow capsule schema")
    if not str(payload.get("capsule_id", "")).strip():
        raise ValueError("capsule_id is required")
    if payload.get("privacy_model") not in _ALLOWED_PRIVACY_MODELS:
        raise ValueError("provider workflow requires sanitized metadata only")
    if payload.get("private_provider_object_identifier_persisted_publicly") is not False:
        raise ValueError("raw/private provider object identifiers may not be persisted publicly")
    if payload.get("external_effect") is not False:
        raise ValueError("provider workflow capsule must remain no-effect")


def run_provider_workflow_capsule(
    payload: dict[str, Any],
    *,
    provider_runtime: str,
) -> dict[str, Any]:
    validate_capsule(payload)
    if provider_runtime not in _ALLOWED_PROVIDER_RUNTIMES:
        raise ValueError("unapproved provider runtime")

    observation = ProviderObservation(
        provider=str(payload["provider"]),
        capability=str(payload["capability"]),
        object_fingerprint=str(payload["object_fingerprint"]),
        expected_status=str(payload["expected_status"]),
        observed_status=str(payload["observed_status"]),
        observed_at=str(payload["observed_at"]),
        transport_ok=bool(payload["transport_ok"]),
        semantic_match=bool(payload["semantic_match"]),
        result_count=int(payload.get("result_count", 0)),
        related_count=int(payload.get("related_count", 0)),
        authority_ceiling=str(payload.get("authority_ceiling", "A1_READ")),
        external_effect=bool(payload.get("external_effect", False)),
    )
    canary_receipt = ProviderObservationCanary().run(observation)
    workflow_pass = (
        canary_receipt["status"] == "PASS"
        and canary_receipt["semantic_readback"] == "SUCCESS"
        and canary_receipt["external_effect"] is False
        and canary_receipt["jarvis_defects"] == []
        and "dependent_internal" in canary_receipt["ready_node_ids"]
        and "unrelated_internal" in canary_receipt["ready_node_ids"]
    )

    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "capsule_id": payload["capsule_id"],
        "capsule_sha256": _canonical_sha256(payload),
        "provider_runtime": provider_runtime,
        "observed_provider_class": str(payload["provider"]),
        "capability": str(payload["capability"]),
        "authority_ceiling": str(payload.get("authority_ceiling", "A1_READ")),
        "privacy_model": payload["privacy_model"],
        "external_effect": False,
        "package_runtime_executed": True,
        "event_state_proof_mission_propagation": workflow_pass,
        "semantic_readback": canary_receipt["semantic_readback"],
        "jarvis_defects": list(canary_receipt["jarvis_defects"]),
        "ready_node_ids": list(canary_receipt["ready_node_ids"]),
        "workflow_status": "PASS" if workflow_pass else "HOLD",
        "maturity_candidate": (
            "WORKFLOW_VERIFIED_PENDING_INDEPENDENT_OBSERVED_PROVIDER_READBACK"
            if workflow_pass
            else "CANARY_VALIDATED"
        ),
        "truth_boundary": {
            "github_actions_provider_runtime_execution_verified": workflow_pass,
            "observed_provider_mutated": False,
            "independent_observed_provider_readback_pending": True,
            "workflow_verified": False,
            "operationally_verified": False,
            "authority_expansion": False,
        },
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute AO-HARMONIC v3 provider workflow capsule")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--provider-runtime", default="GITHUB_ACTIONS")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    receipt = run_provider_workflow_capsule(payload, provider_runtime=args.provider_runtime)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("AO_HARMONIC_PROVIDER_WORKFLOW_RECEIPT=" + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["workflow_status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
