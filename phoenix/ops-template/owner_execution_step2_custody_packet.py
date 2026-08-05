#!/usr/bin/env python3
"""Prepare and verify the owner-reserved step-2 custody execution packet.

This module advances only the non-executing handoff for the next dependency-
ordered step. It verifies the exact provider-proof v39 release, the current
handoff, the admitted step-1 evidence and the sealed owner packet. It then
produces a deterministic instruction packet for the owner-reserved custody
ceremony without selecting a destination, supplying owner attestations,
copying a packet, contacting a provider, consuming authorization or advancing
an external commercial gate.
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

import owner_custody_ceremony as custody  # noqa: E402
import owner_execution_evidence_intake as evidence_intake  # noqa: E402
import owner_execution_step1_binding as step1_binding  # noqa: E402
import owner_sealed_packet as sealed_packet  # noqa: E402

RELEASE_SCHEMA = (
    "AO-COMMERCIAL-PHOENIX-OWNER-EXECUTION-STEP1-BINDING-RELEASE-RECEIPT-39"
)
RELEASE_STATUS = (
    "OWNER_EXECUTION_STEP1_BINDING_PROVIDER_PROOF_VERIFIED_"
    "OWNER_CUSTODY_ACTION_REQUIRED"
)
PACKET_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-EXECUTION-STEP2-CUSTODY-PACKET-1"
PACKET_STATUS = "OWNER_EXECUTION_STEP2_CUSTODY_PACKET_VERIFIED_NOT_EXECUTED"
CONTRACT_PATH = OPS_DIR / "governance" / "OWNER_CUSTODY_CEREMONY_CONTRACT.json"
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


class OwnerExecutionStep2CustodyPacketError(RuntimeError):
    """Fail-closed step-2 custody execution-packet error."""


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
        raise OwnerExecutionStep2CustodyPacketError("owner packet is unreadable") from exc
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerExecutionStep2CustodyPacketError(f"{label} is unreadable") from exc
    if not isinstance(payload, dict):
        raise OwnerExecutionStep2CustodyPacketError(f"{label} must be a JSON object")
    return payload


def _verify_self_hash(payload: dict[str, Any], field: str, label: str) -> str:
    claimed = str(payload.get(field) or "").lower()
    if not HEX64.fullmatch(claimed):
        raise OwnerExecutionStep2CustodyPacketError(f"{label} hash is invalid")
    body = dict(payload)
    body.pop(field, None)
    if canonical_sha256(body) != claimed:
        raise OwnerExecutionStep2CustodyPacketError(f"{label} hash verification failed")
    return claimed


def _require_truth(payload: dict[str, Any], label: str) -> None:
    for field, expected in COMMERCIAL_TRUTH.items():
        if payload.get(field) != expected:
            raise OwnerExecutionStep2CustodyPacketError(
                f"{label} commercial truth changed: {field}"
            )


def verify_release_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Verify the exact provider-proof v39 predecessor release."""

    if receipt.get("schema") != RELEASE_SCHEMA:
        raise OwnerExecutionStep2CustodyPacketError("release receipt schema mismatch")
    receipt_sha = _verify_self_hash(receipt, "receipt_sha256", "release receipt")
    if receipt.get("status") != RELEASE_STATUS:
        raise OwnerExecutionStep2CustodyPacketError("release receipt status mismatch")
    if receipt.get("programme_id") != "AO-COMMERCIAL-MATURITY-V1":
        raise OwnerExecutionStep2CustodyPacketError("release programme mismatch")
    if receipt.get("dependency_path") != ["C03", "C06", "C07", "C11", "C14", "C15"]:
        raise OwnerExecutionStep2CustodyPacketError("release dependency path mismatch")
    _require_truth(receipt.get("commercial_truth") or {}, "release")

    proof = receipt.get("provider_proof")
    if not isinstance(proof, dict):
        raise OwnerExecutionStep2CustodyPacketError("provider proof is missing")
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
            raise OwnerExecutionStep2CustodyPacketError(
                f"provider proof contains unresolved {field}"
            )
    if proof.get("provider_apply_performed") is not False:
        raise OwnerExecutionStep2CustodyPacketError("release overclaims provider apply")
    if proof.get("source_mutation_attempted") is not False:
        raise OwnerExecutionStep2CustodyPacketError("release overclaims source mutation")
    if proof.get("owner_execution_step1_binding_in_ops") is not True:
        raise OwnerExecutionStep2CustodyPacketError("step-1 binding is absent from Ops")
    if proof.get("owner_execution_step1_binding_contract_in_ops") is not True:
        raise OwnerExecutionStep2CustodyPacketError(
            "step-1 binding contract is absent from Ops"
        )

    packet_sha = str(proof.get("owner_packet_sha256") or "").lower()
    packet_file_sha = str(proof.get("owner_packet_file_sha256") or "").lower()
    if not HEX64.fullmatch(packet_sha) or not HEX64.fullmatch(packet_file_sha):
        raise OwnerExecutionStep2CustodyPacketError(
            "release owner packet identity is invalid"
        )

    authority = receipt.get("provider_authority")
    if not isinstance(authority, dict):
        raise OwnerExecutionStep2CustodyPacketError("provider authority readback is missing")
    if authority.get("provider_mutation_performed") is not False:
        raise OwnerExecutionStep2CustodyPacketError("authority readback claims mutation")
    if authority.get("target_core_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionStep2CustodyPacketError("Core repository truth changed")
    if authority.get("target_ops_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionStep2CustodyPacketError("Ops repository truth changed")

    attestation = receipt.get("attestation_truth")
    if not isinstance(attestation, dict) or any(attestation.values()):
        raise OwnerExecutionStep2CustodyPacketError(
            "release overclaims owner execution or provider outcome"
        )

    return {
        "receipt_sha256": receipt_sha,
        "implementation_pr": receipt["implementation_pr"],
        "implementation_pr_head": receipt["implementation_pr_head"],
        "merged_main_sha": receipt["merged_main_sha"],
        "owner_packet_sha256": packet_sha,
        "owner_packet_file_sha256": packet_file_sha,
        "drive_release_file_id": receipt["drive_release"]["file_id"],
    }


def verify_custody_contract() -> dict[str, Any]:
    contract = _load_json(CONTRACT_PATH, "custody ceremony contract")
    expected = {
        "schema": "FEDOMEGA-PHOENIX-OWNER-CUSTODY-CEREMONY-CONTRACT-1",
        "status": "PREPARED_NOT_EXECUTED_OWNER_RESERVED",
        "entrypoint": "owner_custody_ceremony.py",
        "route": "OWNER_ONLY_SEALED_PACKET",
        "required_confirmation": custody.CONFIRMATION,
        "prepare_output": "CUSTODY_CEREMONY_PREPARED_OWNER_EXECUTION_REQUIRED",
        "copy_output": "CUSTODY_COPY_INTEGRITY_VERIFIED_OWNER_CONTROL_ATTESTATION_REQUIRED",
    }
    for field, value in expected.items():
        if contract.get(field) != value:
            raise OwnerExecutionStep2CustodyPacketError(
                f"custody contract mismatch: {field}"
            )
    controls = contract.get("controls")
    if not isinstance(controls, dict):
        raise OwnerExecutionStep2CustodyPacketError("custody controls are missing")
    required_true = (
        "atomic_local_copy",
        "destination_fingerprint_binding",
        "idempotent_exact_replay",
        "manifest_hash_binding",
        "owner_attestation_required",
        "packet_round_trip_verification",
        "symlink_destination_prohibited",
    )
    if any(controls.get(field) is not True for field in required_true):
        raise OwnerExecutionStep2CustodyPacketError(
            "custody contract is missing a required control"
        )
    if controls.get("copy_permissions") != "0600":
        raise OwnerExecutionStep2CustodyPacketError(
            "custody contract permission mode changed"
        )
    for field in (
        "credential_material_allowed",
        "external_commercial_gate_advanced",
        "owner_authorization_created",
        "owner_control_inferred_from_copy",
        "provider_apply_performed",
        "provider_authority_created",
    ):
        if controls.get(field) is not False:
            raise OwnerExecutionStep2CustodyPacketError(
                f"unsafe custody contract control: {field}"
            )
    return contract


def _verify_packet(
    owner_packet_path: Path, *, release: dict[str, Any]
) -> dict[str, Any]:
    try:
        verified = sealed_packet.verify_packet_candidate(owner_packet_path)
    except sealed_packet.OwnerSealedPacketError as exc:
        raise OwnerExecutionStep2CustodyPacketError(str(exc)) from exc
    packet_sha = str(verified.get("packet_sha256") or "").lower()
    packet_file_sha = sha256_file(owner_packet_path)
    if packet_sha != release["owner_packet_sha256"]:
        raise OwnerExecutionStep2CustodyPacketError(
            "owner packet canonical hash mismatch"
        )
    if packet_file_sha != release["owner_packet_file_sha256"]:
        raise OwnerExecutionStep2CustodyPacketError("owner packet file hash mismatch")
    return {
        "packet_sha256": packet_sha,
        "packet_file_sha256": packet_file_sha,
        "packet_source_repository": verified["source_repository"],
        "packet_source_sha": verified["source_sha"],
        "core_archive_sha256": verified["archives"]["core"]["sha256"],
        "ops_archive_sha256": verified["archives"]["ops"]["sha256"],
    }


def build_step2_custody_packet(
    *,
    release_receipt: dict[str, Any],
    handoff: dict[str, Any],
    step1_evidence: dict[str, Any],
    owner_packet_path: Path,
    handoff_source_sha: str,
    generated_at: datetime,
) -> dict[str, Any]:
    """Build a deterministic owner-reserved step-2 packet without executing it."""

    release = verify_release_receipt(release_receipt)
    handoff_source_sha = handoff_source_sha.lower()
    if not HEX40.fullmatch(handoff_source_sha):
        raise OwnerExecutionStep2CustodyPacketError("handoff source SHA is invalid")
    if generated_at.tzinfo is None:
        raise OwnerExecutionStep2CustodyPacketError(
            "generated_at must include timezone"
        )

    try:
        handoff_sha = evidence_intake.verify_handoff(
            handoff,
            current_source_sha=handoff_source_sha,
            owner_packet_sha256=release["owner_packet_sha256"],
        )
        step1 = step1_binding.verify_step1_evidence(
            step1_evidence, handoff=handoff
        )
    except (
        evidence_intake.OwnerExecutionEvidenceIntakeError,
        step1_binding.OwnerExecutionStep1BindingError,
    ) as exc:
        raise OwnerExecutionStep2CustodyPacketError(str(exc)) from exc
    if step1.get("next_eligible_step") != 2:
        raise OwnerExecutionStep2CustodyPacketError(
            "step-1 evidence does not admit step 2"
        )

    steps = handoff.get("ordered_steps") or []
    if len(steps) < 2:
        raise OwnerExecutionStep2CustodyPacketError("handoff step 2 is missing")
    second = steps[1]
    expected_step = {
        "sequence": 2,
        "id": "EXECUTE_OWNER_CUSTODY_CEREMONY",
        "stage": "C03",
        "entrypoint": "owner_custody_ceremony.py",
        "authority": "OWNER_RESERVED",
        "external_effect": False,
    }
    for field, value in expected_step.items():
        if second.get(field) != value:
            raise OwnerExecutionStep2CustodyPacketError(
                f"step-2 metadata mismatch: {field}"
            )

    contract = verify_custody_contract()
    owner_packet = _verify_packet(owner_packet_path, release=release)
    generated_z = (
        generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    body: dict[str, Any] = {
        "schema": PACKET_SCHEMA,
        "status": PACKET_STATUS,
        "generated_at": generated_z,
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "dependency_path": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "handoff_source_sha": handoff_source_sha,
        "handoff_sha256": handoff_sha,
        "v39_release_receipt_sha256": release["receipt_sha256"],
        "step1_evidence_sha256": step1["evidence_sha256"],
        "step1_binding_sha256": step1["binding_sha256"],
        "owner_packet": owner_packet,
        "step": dict(expected_step),
        "custody_contract": {
            "schema": contract["schema"],
            "entrypoint": contract["entrypoint"],
            "route": contract["route"],
            "required_confirmation": contract["required_confirmation"],
            "prepare_output": contract["prepare_output"],
            "copy_output": contract["copy_output"],
            "copy_permissions": contract["controls"]["copy_permissions"],
        },
        "required_owner_inputs": {
            "fields": [
                "owner_reference",
                "destination_label",
                "destination_fingerprint",
                "destination_path",
            ],
            "values_present": False,
            "owner_reference_constraint": "OWNER_SELECTED_NON_SECRET_LABEL",
            "destination_label_constraint": "OWNER_SELECTED_NON_SECRET_LABEL",
            "destination_fingerprint_constraint": "LOWERCASE_SHA256",
            "destination_path_constraint": (
                "OWNER_SELECTED_LOCAL_REAL_DIRECTORY_NON_SYMLINK_DESTINATION"
            ),
        },
        "prepare_command_template": [
            "python",
            "owner_custody_ceremony.py",
            "prepare",
            "--packet",
            "<OWNER_PACKET>",
            "--output",
            "<CUSTODY_MANIFEST>",
            "--owner-reference",
            "<OWNER_REFERENCE>",
            "--destination-label",
            "<DESTINATION_LABEL>",
            "--destination-fingerprint",
            "<DESTINATION_FINGERPRINT_SHA256>",
        ],
        "copy_command_template": [
            "python",
            "owner_custody_ceremony.py",
            "copy",
            "--packet",
            "<OWNER_PACKET>",
            "--manifest",
            "<CUSTODY_MANIFEST>",
            "--destination",
            "<OWNER_CONTROLLED_DESTINATION>",
            "--receipt-output",
            "<CUSTODY_RECEIPT>",
            "--confirm",
            custody.CONFIRMATION,
        ],
        "expected_execution_outputs": {
            "manifest_schema": custody.SCHEMA,
            "manifest_status": contract["prepare_output"],
            "receipt_schema": custody.RECEIPT_SCHEMA,
            "receipt_status": contract["copy_output"],
            "copy_mode": "0600",
            "owner_controlled_custody_proven_by_copy_alone": False,
            "owner_attestation_required": True,
        },
        "next_gate_after_verified_owner_execution": {
            "sequence": 3,
            "step_id": "GENERATE_OWNER_ATTESTATION_CHALLENGE",
            "authority": "A1_INTERNAL",
            "owner_attestation_still_required": True,
        },
        "owner_execution_required": True,
        "owner_action_performed": False,
        "owner_input_values_recorded": False,
        "owner_attestation_present": False,
        "owner_authorization_present": False,
        "provider_request_performed": False,
        "provider_apply_performed": False,
        "external_communication_performed": False,
        "credential_value_recorded": False,
        "external_commercial_gate_advanced": False,
        "commercial_truth": dict(COMMERCIAL_TRUTH),
    }
    body["execution_packet_sha256"] = canonical_sha256(body)
    verify_step2_custody_packet(body)
    return body


def verify_step2_custody_packet(payload: dict[str, Any]) -> dict[str, Any]:
    packet_sha = _verify_self_hash(
        payload, "execution_packet_sha256", "step-2 execution packet"
    )
    if payload.get("schema") != PACKET_SCHEMA or payload.get("status") != PACKET_STATUS:
        raise OwnerExecutionStep2CustodyPacketError(
            "step-2 execution packet schema or status mismatch"
        )
    if payload.get("dependency_path") != ["C03", "C06", "C07", "C11", "C14", "C15"]:
        raise OwnerExecutionStep2CustodyPacketError(
            "step-2 execution packet dependency path mismatch"
        )
    _require_truth(payload.get("commercial_truth") or {}, "step-2 execution packet")

    expected_step = {
        "sequence": 2,
        "id": "EXECUTE_OWNER_CUSTODY_CEREMONY",
        "stage": "C03",
        "entrypoint": "owner_custody_ceremony.py",
        "authority": "OWNER_RESERVED",
        "external_effect": False,
    }
    if payload.get("step") != expected_step:
        raise OwnerExecutionStep2CustodyPacketError("step-2 execution metadata drift")

    inputs = payload.get("required_owner_inputs")
    if not isinstance(inputs, dict) or inputs.get("values_present") is not False:
        raise OwnerExecutionStep2CustodyPacketError(
            "owner input values must remain absent"
        )
    if inputs.get("fields") != [
        "owner_reference",
        "destination_label",
        "destination_fingerprint",
        "destination_path",
    ]:
        raise OwnerExecutionStep2CustodyPacketError("owner input contract drift")

    contract = payload.get("custody_contract")
    if not isinstance(contract, dict):
        raise OwnerExecutionStep2CustodyPacketError("custody contract binding is missing")
    if contract.get("required_confirmation") != custody.CONFIRMATION:
        raise OwnerExecutionStep2CustodyPacketError(
            "custody confirmation binding drift"
        )
    if contract.get("copy_permissions") != "0600":
        raise OwnerExecutionStep2CustodyPacketError("custody copy mode drift")

    expected_prepare = [
        "python",
        "owner_custody_ceremony.py",
        "prepare",
        "--packet",
        "<OWNER_PACKET>",
        "--output",
        "<CUSTODY_MANIFEST>",
        "--owner-reference",
        "<OWNER_REFERENCE>",
        "--destination-label",
        "<DESTINATION_LABEL>",
        "--destination-fingerprint",
        "<DESTINATION_FINGERPRINT_SHA256>",
    ]
    expected_copy = [
        "python",
        "owner_custody_ceremony.py",
        "copy",
        "--packet",
        "<OWNER_PACKET>",
        "--manifest",
        "<CUSTODY_MANIFEST>",
        "--destination",
        "<OWNER_CONTROLLED_DESTINATION>",
        "--receipt-output",
        "<CUSTODY_RECEIPT>",
        "--confirm",
        custody.CONFIRMATION,
    ]
    if payload.get("prepare_command_template") != expected_prepare:
        raise OwnerExecutionStep2CustodyPacketError("prepare command template drift")
    if payload.get("copy_command_template") != expected_copy:
        raise OwnerExecutionStep2CustodyPacketError("copy command template drift")

    outputs = payload.get("expected_execution_outputs")
    if not isinstance(outputs, dict):
        raise OwnerExecutionStep2CustodyPacketError("execution output contract missing")
    if outputs.get("manifest_schema") != custody.SCHEMA:
        raise OwnerExecutionStep2CustodyPacketError("manifest schema drift")
    if outputs.get("receipt_schema") != custody.RECEIPT_SCHEMA:
        raise OwnerExecutionStep2CustodyPacketError("receipt schema drift")
    if outputs.get("copy_mode") != "0600":
        raise OwnerExecutionStep2CustodyPacketError("execution copy mode drift")
    if outputs.get("owner_controlled_custody_proven_by_copy_alone") is not False:
        raise OwnerExecutionStep2CustodyPacketError(
            "local copy cannot prove owner control"
        )
    if outputs.get("owner_attestation_required") is not True:
        raise OwnerExecutionStep2CustodyPacketError(
            "owner attestation requirement is missing"
        )

    if payload.get("owner_execution_required") is not True:
        raise OwnerExecutionStep2CustodyPacketError(
            "owner execution requirement is missing"
        )
    for field in (
        "owner_action_performed",
        "owner_input_values_recorded",
        "owner_attestation_present",
        "owner_authorization_present",
        "provider_request_performed",
        "provider_apply_performed",
        "external_communication_performed",
        "credential_value_recorded",
        "external_commercial_gate_advanced",
    ):
        if payload.get(field) is not False:
            raise OwnerExecutionStep2CustodyPacketError(
                f"unsafe step-2 execution packet claim: {field}"
            )

    owner_packet = payload.get("owner_packet")
    if not isinstance(owner_packet, dict):
        raise OwnerExecutionStep2CustodyPacketError("owner packet binding is missing")
    for field in (
        "packet_sha256",
        "packet_file_sha256",
        "core_archive_sha256",
        "ops_archive_sha256",
    ):
        if not HEX64.fullmatch(str(owner_packet.get(field) or "")):
            raise OwnerExecutionStep2CustodyPacketError(
                f"owner packet binding is invalid: {field}"
            )
    return {
        "execution_packet_sha256": packet_sha,
        "step_sequence": 2,
        "owner_execution_required": True,
        "owner_action_performed": False,
        "next_eligible_step_after_owner_execution": 3,
        "provider_apply_performed": False,
        "external_commercial_gate_advanced": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-receipt", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--step1-evidence", type=Path, required=True)
    parser.add_argument("--owner-packet", type=Path, required=True)
    parser.add_argument("--handoff-source-sha", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = build_step2_custody_packet(
        release_receipt=_load_json(args.release_receipt, "release receipt"),
        handoff=_load_json(args.handoff, "handoff"),
        step1_evidence=_load_json(args.step1_evidence, "step-1 evidence"),
        owner_packet_path=args.owner_packet,
        handoff_source_sha=args.handoff_source_sha,
        generated_at=datetime.now(timezone.utc),
    )
    encoded = canonical_bytes(result) + b"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
