#!/usr/bin/env python3
"""Prepare and verify the non-executing owner-reserved custody packet for step 2."""

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
import owner_execution_evidence_intake as intake  # noqa: E402
import owner_execution_step1_binding as step1  # noqa: E402
import owner_sealed_packet as sealed_packet  # noqa: E402

RELEASE_SCHEMA = "AO-COMMERCIAL-PHOENIX-OWNER-EXECUTION-STEP1-BINDING-RELEASE-RECEIPT-39"
RELEASE_STATUS = "OWNER_EXECUTION_STEP1_BINDING_PROVIDER_PROOF_VERIFIED_OWNER_CUSTODY_ACTION_REQUIRED"
PACKET_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-EXECUTION-STEP2-CUSTODY-PACKET-1"
PACKET_STATUS = "OWNER_EXECUTION_STEP2_CUSTODY_PACKET_VERIFIED_NOT_EXECUTED"
CONTRACT_PATH = OPS_DIR / "governance" / "OWNER_CUSTODY_CEREMONY_CONTRACT.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DEPENDENCY_PATH = ["C03", "C06", "C07", "C11", "C14", "C15"]
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
STEP2 = {
    "sequence": 2,
    "id": "EXECUTE_OWNER_CUSTODY_CEREMONY",
    "stage": "C03",
    "entrypoint": "owner_custody_ceremony.py",
    "authority": "OWNER_RESERVED",
    "external_effect": False,
}
OWNER_FIELDS = [
    "owner_reference",
    "destination_label",
    "destination_fingerprint",
    "destination_path",
]


class OwnerExecutionStep2CustodyPacketError(RuntimeError):
    """Fail-closed step-2 custody packet error."""


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
    if receipt.get("schema") != RELEASE_SCHEMA:
        raise OwnerExecutionStep2CustodyPacketError("release receipt schema mismatch")
    receipt_sha = _verify_self_hash(receipt, "receipt_sha256", "release receipt")
    if receipt.get("status") != RELEASE_STATUS:
        raise OwnerExecutionStep2CustodyPacketError("release receipt status mismatch")
    if receipt.get("programme_id") != "AO-COMMERCIAL-MATURITY-V1":
        raise OwnerExecutionStep2CustodyPacketError("release programme mismatch")
    if receipt.get("dependency_path") != DEPENDENCY_PATH:
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
            raise OwnerExecutionStep2CustodyPacketError(f"unresolved provider proof: {field}")
    for field in ("provider_apply_performed", "source_mutation_attempted"):
        if proof.get(field) is not False:
            raise OwnerExecutionStep2CustodyPacketError(f"unsafe release claim: {field}")
    for field in (
        "owner_execution_step1_binding_in_ops",
        "owner_execution_step1_binding_contract_in_ops",
    ):
        if proof.get(field) is not True:
            raise OwnerExecutionStep2CustodyPacketError(f"required Ops proof missing: {field}")

    packet_sha = str(proof.get("owner_packet_sha256") or "").lower()
    packet_file_sha = str(proof.get("owner_packet_file_sha256") or "").lower()
    if not HEX64.fullmatch(packet_sha) or not HEX64.fullmatch(packet_file_sha):
        raise OwnerExecutionStep2CustodyPacketError("release packet identity is invalid")

    authority = receipt.get("provider_authority")
    if not isinstance(authority, dict) or authority.get("provider_mutation_performed") is not False:
        raise OwnerExecutionStep2CustodyPacketError("provider authority readback is unsafe")
    if authority.get("target_core_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionStep2CustodyPacketError("Core repository truth changed")
    if authority.get("target_ops_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionStep2CustodyPacketError("Ops repository truth changed")

    attestation = receipt.get("attestation_truth")
    if not isinstance(attestation, dict) or any(attestation.values()):
        raise OwnerExecutionStep2CustodyPacketError("release overclaims owner execution")

    return {
        "receipt_sha256": receipt_sha,
        "owner_packet_sha256": packet_sha,
        "owner_packet_file_sha256": packet_file_sha,
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
            raise OwnerExecutionStep2CustodyPacketError(f"custody contract drift: {field}")
    controls = contract.get("controls") or {}
    for field in (
        "atomic_local_copy",
        "destination_fingerprint_binding",
        "idempotent_exact_replay",
        "manifest_hash_binding",
        "owner_attestation_required",
        "packet_round_trip_verification",
        "symlink_destination_prohibited",
    ):
        if controls.get(field) is not True:
            raise OwnerExecutionStep2CustodyPacketError(f"custody control missing: {field}")
    if controls.get("copy_permissions") != "0600":
        raise OwnerExecutionStep2CustodyPacketError("custody copy mode drift")
    for field in (
        "credential_material_allowed",
        "external_commercial_gate_advanced",
        "owner_authorization_created",
        "owner_control_inferred_from_copy",
        "provider_apply_performed",
        "provider_authority_created",
    ):
        if controls.get(field) is not False:
            raise OwnerExecutionStep2CustodyPacketError(f"unsafe custody control: {field}")
    return contract


def _verify_packet(path: Path, release: dict[str, Any]) -> dict[str, Any]:
    try:
        verified = sealed_packet.verify_packet_candidate(path)
    except sealed_packet.OwnerSealedPacketError as exc:
        raise OwnerExecutionStep2CustodyPacketError(str(exc)) from exc
    raw = _load_json(path, "owner packet")
    file_sha = sha256_file(path)
    if verified.get("packet_sha256") != release["owner_packet_sha256"]:
        raise OwnerExecutionStep2CustodyPacketError("owner packet canonical hash mismatch")
    if file_sha != release["owner_packet_file_sha256"]:
        raise OwnerExecutionStep2CustodyPacketError("owner packet file hash mismatch")
    repository = str(raw.get("source_repository") or "")
    source_sha = str(raw.get("source_sha") or "").lower()
    if not repository or not HEX40.fullmatch(source_sha):
        raise OwnerExecutionStep2CustodyPacketError("owner packet source identity is invalid")
    return {
        "packet_sha256": verified["packet_sha256"],
        "packet_file_sha256": file_sha,
        "packet_source_repository": repository,
        "packet_source_sha": source_sha,
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
    release = verify_release_receipt(release_receipt)
    handoff_source_sha = handoff_source_sha.lower()
    if not HEX40.fullmatch(handoff_source_sha):
        raise OwnerExecutionStep2CustodyPacketError("handoff source SHA is invalid")
    if generated_at.tzinfo is None:
        raise OwnerExecutionStep2CustodyPacketError("generated_at must include timezone")
    try:
        handoff_sha = intake.verify_handoff(
            handoff,
            current_source_sha=handoff_source_sha,
            owner_packet_sha256=release["owner_packet_sha256"],
        )
        admitted = step1.verify_step1_evidence(step1_evidence, handoff=handoff)
    except (
        intake.OwnerExecutionEvidenceIntakeError,
        step1.OwnerExecutionStep1BindingError,
    ) as exc:
        raise OwnerExecutionStep2CustodyPacketError(str(exc)) from exc
    if admitted.get("next_eligible_step") != 2:
        raise OwnerExecutionStep2CustodyPacketError("step 2 is not eligible")
    steps = handoff.get("ordered_steps") or []
    if len(steps) < 2 or steps[1] != STEP2:
        raise OwnerExecutionStep2CustodyPacketError("step-2 handoff metadata drift")

    contract = verify_custody_contract()
    owner_packet = _verify_packet(owner_packet_path, release)
    generated_z = generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    prepare = [
        "python", "owner_custody_ceremony.py", "prepare",
        "--packet", "<OWNER_PACKET>",
        "--output", "<CUSTODY_MANIFEST>",
        "--owner-reference", "<OWNER_REFERENCE>",
        "--destination-label", "<DESTINATION_LABEL>",
        "--destination-fingerprint", "<DESTINATION_FINGERPRINT_SHA256>",
    ]
    copy = [
        "python", "owner_custody_ceremony.py", "copy",
        "--packet", "<OWNER_PACKET>",
        "--manifest", "<CUSTODY_MANIFEST>",
        "--destination", "<OWNER_CONTROLLED_DESTINATION>",
        "--receipt-output", "<CUSTODY_RECEIPT>",
        "--confirm", custody.CONFIRMATION,
    ]
    body: dict[str, Any] = {
        "schema": PACKET_SCHEMA,
        "status": PACKET_STATUS,
        "generated_at": generated_z,
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "dependency_path": DEPENDENCY_PATH,
        "handoff_source_sha": handoff_source_sha,
        "handoff_sha256": handoff_sha,
        "v39_release_receipt_sha256": release["receipt_sha256"],
        "step1_evidence_sha256": admitted["evidence_sha256"],
        "step1_binding_sha256": admitted["binding_sha256"],
        "owner_packet": owner_packet,
        "step": STEP2,
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
            "fields": OWNER_FIELDS,
            "values_present": False,
            "owner_reference_constraint": "OWNER_SELECTED_NON_SECRET_LABEL",
            "destination_label_constraint": "OWNER_SELECTED_NON_SECRET_LABEL",
            "destination_fingerprint_constraint": "LOWERCASE_SHA256",
            "destination_path_constraint": "OWNER_SELECTED_LOCAL_REAL_DIRECTORY_NON_SYMLINK_DESTINATION",
        },
        "prepare_command_template": prepare,
        "copy_command_template": copy,
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
        "commercial_truth": COMMERCIAL_TRUTH,
    }
    body["execution_packet_sha256"] = canonical_sha256(body)
    verify_step2_custody_packet(body)
    return body


def verify_step2_custody_packet(payload: dict[str, Any]) -> dict[str, Any]:
    packet_sha = _verify_self_hash(payload, "execution_packet_sha256", "step-2 packet")
    if payload.get("schema") != PACKET_SCHEMA or payload.get("status") != PACKET_STATUS:
        raise OwnerExecutionStep2CustodyPacketError("step-2 packet identity drift")
    if payload.get("dependency_path") != DEPENDENCY_PATH:
        raise OwnerExecutionStep2CustodyPacketError("dependency path drift")
    _require_truth(payload.get("commercial_truth") or {}, "step-2 packet")
    if payload.get("step") != STEP2:
        raise OwnerExecutionStep2CustodyPacketError("step-2 metadata drift")
    inputs = payload.get("required_owner_inputs") or {}
    if inputs.get("fields") != OWNER_FIELDS or inputs.get("values_present") is not False:
        raise OwnerExecutionStep2CustodyPacketError("owner input contract drift")
    contract = payload.get("custody_contract") or {}
    if contract.get("required_confirmation") != custody.CONFIRMATION:
        raise OwnerExecutionStep2CustodyPacketError("confirmation binding drift")
    if contract.get("copy_permissions") != "0600":
        raise OwnerExecutionStep2CustodyPacketError("copy mode drift")
    if payload.get("copy_command_template", [])[-2:] != ["--confirm", custody.CONFIRMATION]:
        raise OwnerExecutionStep2CustodyPacketError("copy command drift")
    outputs = payload.get("expected_execution_outputs") or {}
    if outputs.get("manifest_schema") != custody.SCHEMA:
        raise OwnerExecutionStep2CustodyPacketError("manifest schema drift")
    if outputs.get("receipt_schema") != custody.RECEIPT_SCHEMA:
        raise OwnerExecutionStep2CustodyPacketError("receipt schema drift")
    if outputs.get("owner_controlled_custody_proven_by_copy_alone") is not False:
        raise OwnerExecutionStep2CustodyPacketError("copy cannot prove owner control")
    if outputs.get("owner_attestation_required") is not True:
        raise OwnerExecutionStep2CustodyPacketError("attestation requirement missing")
    if payload.get("owner_execution_required") is not True:
        raise OwnerExecutionStep2CustodyPacketError("owner execution requirement missing")
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
            raise OwnerExecutionStep2CustodyPacketError(f"unsafe packet claim: {field}")
    owner_packet = payload.get("owner_packet") or {}
    for field in (
        "packet_sha256",
        "packet_file_sha256",
        "core_archive_sha256",
        "ops_archive_sha256",
    ):
        if not HEX64.fullmatch(str(owner_packet.get(field) or "")):
            raise OwnerExecutionStep2CustodyPacketError(f"invalid packet binding: {field}")
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
