#!/usr/bin/env python3
"""Materialize and verify the dependency-ordered step-1 execution evidence.

This module verifies the exact provider-proof v38 intake release, the v37
handoff release, the current-source-bound handoff and the owner packet
candidate before creating a hash-bound A1_INTERNAL evidence record for step 1.

It performs no owner action, provider request, external communication,
authorization consumption, provider apply or commercial-gate advancement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPS_DIR = Path(__file__).resolve().parent
if str(OPS_DIR) not in sys.path:
    sys.path.insert(0, str(OPS_DIR))

import owner_execution_evidence_intake as evidence_intake  # noqa: E402
import owner_sealed_packet as sealed_packet  # noqa: E402

CAPABILITY_RELEASE_SCHEMA = (
    "AO-COMMERCIAL-PHOENIX-OWNER-EXECUTION-EVIDENCE-INTAKE-RELEASE-RECEIPT-38"
)
CAPABILITY_RELEASE_STATUS = (
    "OWNER_EXECUTION_EVIDENCE_INTAKE_PROVIDER_PROOF_VERIFIED_"
    "OWNER_ACTION_AND_FRESH_PROVIDER_AUTHORITY_REQUIRED"
)
BINDING_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-EXECUTION-STEP1-BINDING-1"
EVIDENCE_SCHEMA = evidence_intake.EVIDENCE_SCHEMA
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

COMMERCIAL_TRUTH = {
    "customer_demand": "MARKET_PROOF_REQUIRED",
    "signed_customer_contract": "NOT_PROVEN",
    "payment_provider_operation": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
    "cloud_run_operation": "NOT_PROVEN",
    "enterprise_assurance": "UNVERIFIED",
    "partner_adoption": "MARKET_PROOF_REQUIRED",
    "production_scale": "PRODUCTION_PROOF_REQUIRED",
    "verified_live_revenue_events": 0,
    "full_commercial_maturity": False,
    "self_service_saas": "HELD",
    "service_enabled_platform": "VERIFIED_AND_PRIORISED",
}


class OwnerExecutionStep1BindingError(RuntimeError):
    """Fail-closed owner-execution step-1 binding error."""


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise OwnerExecutionStep1BindingError("owner packet is unreadable") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerExecutionStep1BindingError(f"{label} is unreadable") from exc
    if not isinstance(payload, dict):
        raise OwnerExecutionStep1BindingError(f"{label} must be a JSON object")
    return payload


def _verify_self_hash(payload: dict[str, Any], field: str, label: str) -> str:
    claimed = str(payload.get(field) or "").lower()
    if not HEX64.fullmatch(claimed):
        raise OwnerExecutionStep1BindingError(f"{label} hash is invalid")
    body = dict(payload)
    body.pop(field, None)
    if canonical_sha256(body) != claimed:
        raise OwnerExecutionStep1BindingError(f"{label} hash verification failed")
    return claimed


def _require_truth(payload: dict[str, Any], label: str) -> None:
    for field, expected in COMMERCIAL_TRUTH.items():
        if payload.get(field) != expected:
            raise OwnerExecutionStep1BindingError(
                f"{label} commercial truth changed: {field}"
            )


def verify_capability_release(receipt: dict[str, Any]) -> dict[str, Any]:
    """Verify the exact provider-proof v38 evidence-intake release."""

    if receipt.get("schema") != CAPABILITY_RELEASE_SCHEMA:
        raise OwnerExecutionStep1BindingError("capability release schema mismatch")
    receipt_sha = _verify_self_hash(
        receipt, "receipt_sha256", "capability release receipt"
    )
    if receipt.get("status") != CAPABILITY_RELEASE_STATUS:
        raise OwnerExecutionStep1BindingError("capability release status mismatch")
    if receipt.get("programme_id") != "AO-COMMERCIAL-MATURITY-V1":
        raise OwnerExecutionStep1BindingError("capability release programme mismatch")
    if receipt.get("dependency_path") != ["C03", "C06", "C07", "C11", "C14", "C15"]:
        raise OwnerExecutionStep1BindingError("capability dependency path mismatch")
    if receipt.get("implementation_pr") != 286:
        raise OwnerExecutionStep1BindingError("unexpected capability implementation PR")
    _require_truth(receipt.get("commercial_truth") or {}, "capability release")

    proof = receipt.get("provider_proof")
    if not isinstance(proof, dict):
        raise OwnerExecutionStep1BindingError("capability provider proof is missing")
    for field in (
        "airlock_findings",
        "changed_workflows",
        "unadmitted_commits",
        "unexpected_active_workflows",
        "core_active_workflows",
        "core_runtime_bytecode",
        "ops_active_workflows",
        "ops_runtime_bytecode",
    ):
        if proof.get(field) != 0:
            raise OwnerExecutionStep1BindingError(
                f"capability proof contains unresolved {field}"
            )
    if proof.get("provider_apply_performed") is not False:
        raise OwnerExecutionStep1BindingError("capability release overclaims apply")
    if proof.get("source_mutation_attempted") is not False:
        raise OwnerExecutionStep1BindingError("capability release overclaims mutation")
    if proof.get("owner_execution_evidence_intake_in_ops") is not True:
        raise OwnerExecutionStep1BindingError("evidence intake is absent from Ops")
    if proof.get("owner_execution_evidence_contract_in_ops") is not True:
        raise OwnerExecutionStep1BindingError("evidence contract is absent from Ops")

    authority = receipt.get("provider_authority")
    if not isinstance(authority, dict):
        raise OwnerExecutionStep1BindingError("provider authority readback is missing")
    if authority.get("provider_mutation_performed") is not False:
        raise OwnerExecutionStep1BindingError("authority readback claims mutation")
    if authority.get("target_core_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionStep1BindingError("Core repository truth changed")
    if authority.get("target_ops_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionStep1BindingError("Ops repository truth changed")

    attestation = receipt.get("attestation_truth")
    if not isinstance(attestation, dict) or any(attestation.values()):
        raise OwnerExecutionStep1BindingError("capability release overclaims execution")

    return {
        "receipt_sha256": receipt_sha,
        "implementation_pr": receipt["implementation_pr"],
        "implementation_pr_head": receipt["implementation_pr_head"],
        "merged_main_sha": receipt["merged_main_sha"],
        "drive_release_file_id": receipt["drive_release"]["file_id"],
    }


def _verify_packet_payload(
    *,
    packet_path: Path,
    packet_result: dict[str, Any],
    predecessor_release: dict[str, Any],
    handoff: dict[str, Any],
) -> dict[str, Any]:
    payload = _load_json(packet_path, "owner packet")
    packet_sha = str(packet_result.get("packet_sha256") or "").lower()
    packet_file_sha = sha256_file(packet_path)
    proof = predecessor_release["provider_proof"]

    if packet_sha != proof.get("owner_packet_sha256"):
        raise OwnerExecutionStep1BindingError("owner packet canonical hash mismatch")
    if packet_file_sha != proof.get("owner_packet_file_sha256"):
        raise OwnerExecutionStep1BindingError("owner packet file hash mismatch")
    if payload.get("packet_sha256") != packet_sha:
        raise OwnerExecutionStep1BindingError("owner packet result drift")
    if payload.get("route") != "OWNER_ONLY_SEALED_PACKET":
        raise OwnerExecutionStep1BindingError("owner packet route mismatch")
    if payload.get("source_repository") != handoff.get("repository_full_name"):
        raise OwnerExecutionStep1BindingError("owner packet repository mismatch")
    if payload.get("source_sha") != predecessor_release.get("merged_main_sha"):
        raise OwnerExecutionStep1BindingError("owner packet source binding mismatch")
    _require_truth(payload.get("commercial_truth") or {}, "owner packet")

    for field in (
        "credential_material_included",
        "owner_authorization_consumed",
        "provider_apply_performed",
        "external_effect_performed",
        "external_commercial_gate_advanced",
    ):
        if payload.get(field) is not False:
            raise OwnerExecutionStep1BindingError(f"unsafe owner packet claim: {field}")

    return {
        "packet_sha256": packet_sha,
        "packet_file_sha256": packet_file_sha,
        "packet_source_sha": payload["source_sha"],
        "packet_source_repository": payload["source_repository"],
        "core_archive_sha256": packet_result["archives"]["core"]["sha256"],
        "ops_archive_sha256": packet_result["archives"]["ops"]["sha256"],
    }


def build_step1_evidence(
    *,
    capability_release: dict[str, Any],
    predecessor_release: dict[str, Any],
    handoff: dict[str, Any],
    owner_packet_path: Path,
    current_source_sha: str,
    recorded_at: datetime,
) -> dict[str, Any]:
    """Build the exact A1_INTERNAL step-1 evidence candidate."""

    capability = verify_capability_release(capability_release)
    predecessor = evidence_intake.verify_release_receipt(predecessor_release)
    current_source_sha = current_source_sha.lower()
    if not HEX40.fullmatch(current_source_sha):
        raise OwnerExecutionStep1BindingError("current source SHA is invalid")
    if recorded_at.tzinfo is None:
        raise OwnerExecutionStep1BindingError("recorded_at must include timezone")

    try:
        handoff_sha = evidence_intake.verify_handoff(
            handoff,
            current_source_sha=current_source_sha,
            owner_packet_sha256=predecessor["owner_packet_sha256"],
        )
        packet_result = sealed_packet.verify_packet_candidate(owner_packet_path)
    except (evidence_intake.OwnerExecutionEvidenceIntakeError, sealed_packet.OwnerSealedPacketError) as exc:
        raise OwnerExecutionStep1BindingError(str(exc)) from exc

    first = (handoff.get("ordered_steps") or [{}])[0]
    expected = {
        "sequence": 1,
        "id": "VERIFY_PACKET_AND_RELEASE_BINDING",
        "stage": "C03",
        "authority": "A1_INTERNAL",
        "external_effect": False,
    }
    for field, value in expected.items():
        if first.get(field) != value:
            raise OwnerExecutionStep1BindingError(f"step-1 metadata mismatch: {field}")

    packet = _verify_packet_payload(
        packet_path=owner_packet_path,
        packet_result=packet_result,
        predecessor_release=predecessor_release,
        handoff=handoff,
    )
    recorded_z = recorded_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    binding: dict[str, Any] = {
        "schema": BINDING_SCHEMA,
        "status": "PACKET_AND_RELEASE_BINDING_VERIFIED_INTERNAL_ONLY",
        "recorded_at": recorded_z,
        "capability_release_receipt_sha256": capability["receipt_sha256"],
        "predecessor_release_receipt_sha256": predecessor["receipt_sha256"],
        "handoff_sha256": handoff_sha,
        "current_source_sha": current_source_sha,
        **packet,
        "owner_action_performed": False,
        "provider_request_performed": False,
        "provider_apply_performed": False,
        "external_communication_performed": False,
        "credential_value_recorded": False,
        "external_commercial_gate_advanced": False,
        "commercial_truth": dict(COMMERCIAL_TRUTH),
    }
    binding["binding_sha256"] = canonical_sha256(binding)

    evidence: dict[str, Any] = {
        "schema": EVIDENCE_SCHEMA,
        "status": "STEP_EVIDENCE_CANDIDATE_VERIFIED_NOT_PROVIDER_PROOF",
        "handoff_sha256": handoff_sha,
        "sequence": 1,
        "step_id": first["id"],
        "stage": first["stage"],
        "authority": first["authority"],
        "external_effect": first["external_effect"],
        "evidence_mode": "INTERNAL_HASH_BOUND",
        "artifact_sha256": binding["binding_sha256"],
        "recorded_at": recorded_z,
        "owner_attested": False,
        "provider_native": False,
        "external_communication_performed": False,
        "provider_apply_performed": False,
        "mock_conformance": False,
        "credential_value_recorded": False,
        "external_commercial_gate_advanced": False,
        "binding_receipt": binding,
    }
    evidence["evidence_sha256"] = canonical_sha256(evidence)
    verify_step1_evidence(evidence, handoff=handoff)
    return evidence


def verify_step1_evidence(
    evidence: dict[str, Any], *, handoff: dict[str, Any]
) -> dict[str, Any]:
    evidence_sha = _verify_self_hash(evidence, "evidence_sha256", "step-1 evidence")
    binding = evidence.get("binding_receipt")
    if not isinstance(binding, dict):
        raise OwnerExecutionStep1BindingError("binding receipt is missing")
    binding_sha = _verify_self_hash(binding, "binding_sha256", "binding receipt")
    if evidence.get("artifact_sha256") != binding_sha:
        raise OwnerExecutionStep1BindingError("binding artifact hash mismatch")
    if binding.get("handoff_sha256") != evidence.get("handoff_sha256"):
        raise OwnerExecutionStep1BindingError("binding handoff hash mismatch")
    _require_truth(binding.get("commercial_truth") or {}, "binding receipt")
    for field in (
        "owner_action_performed",
        "provider_request_performed",
        "provider_apply_performed",
        "external_communication_performed",
        "credential_value_recorded",
        "external_commercial_gate_advanced",
    ):
        if binding.get(field) is not False:
            raise OwnerExecutionStep1BindingError(f"unsafe binding claim: {field}")

    first = (handoff.get("ordered_steps") or [{}])[0]
    try:
        evidence_intake.verify_step_evidence(
            evidence,
            expected_step=first,
            handoff_sha256=str(handoff.get("handoff_sha256") or ""),
        )
    except evidence_intake.OwnerExecutionEvidenceIntakeError as exc:
        raise OwnerExecutionStep1BindingError(str(exc)) from exc
    return {
        "evidence_sha256": evidence_sha,
        "binding_sha256": binding_sha,
        "next_eligible_step": 2,
        "next_gate": "OWNER_RESERVED_CUSTODY_CEREMONY",
        "owner_action_performed": False,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capability-release", type=Path, required=True)
    parser.add_argument("--predecessor-release", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--owner-packet", type=Path, required=True)
    parser.add_argument("--current-source-sha", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = build_step1_evidence(
        capability_release=_load_json(args.capability_release, "capability release"),
        predecessor_release=_load_json(args.predecessor_release, "predecessor release"),
        handoff=_load_json(args.handoff, "handoff"),
        owner_packet_path=args.owner_packet,
        current_source_sha=args.current_source_sha,
        recorded_at=datetime.now(timezone.utc),
    )
    encoded = canonical_bytes(result) + b"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
