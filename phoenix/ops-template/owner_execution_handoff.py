#!/usr/bin/env python3
"""Compile a deterministic, non-executing owner execution handoff.

The handoff binds the provider-proof verified v36 release to an exact current
source identity, owner/repository identity and sealed-packet hash. It orders
the remaining owner-reserved and provider-native gates without performing any
provider request, external communication, authorization consumption or apply.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RELEASE_SCHEMA = (
    "AO-COMMERCIAL-PHOENIX-PROVIDER-ATTESTED-AUTHORIZATION-RELEASE-RECEIPT-36"
)
RELEASE_STATUS = (
    "PROVIDER_ATTESTED_AUTHORIZATION_INTAKE_PROVIDER_PROOF_VERIFIED_"
    "OWNER_EXECUTION_AND_FRESH_PROVIDER_AUTHORITY_REQUIRED"
)
HANDOFF_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-EXECUTION-HANDOFF-1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class OwnerExecutionHandoffError(RuntimeError):
    """Fail-closed owner execution handoff error."""


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerExecutionHandoffError(f"{label} is unreadable") from exc
    if not isinstance(payload, dict):
        raise OwnerExecutionHandoffError(f"{label} must be a JSON object")
    return payload


def _verify_self_hash(payload: dict[str, Any], *, field: str, label: str) -> str:
    claimed = str(payload.get(field) or "").lower()
    if not HEX64.fullmatch(claimed):
        raise OwnerExecutionHandoffError(f"{label} SHA-256 is invalid")
    body = dict(payload)
    body.pop(field, None)
    if canonical_sha256(body) != claimed:
        raise OwnerExecutionHandoffError(f"{label} hash verification failed")
    return claimed


def verify_release_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """Verify the exact fail-closed v36 predecessor release."""

    if receipt.get("schema") != RELEASE_SCHEMA:
        raise OwnerExecutionHandoffError("release receipt schema mismatch")
    receipt_sha = _verify_self_hash(
        receipt, field="receipt_sha256", label="release receipt"
    )
    if receipt.get("status") != RELEASE_STATUS:
        raise OwnerExecutionHandoffError("release receipt status mismatch")
    if receipt.get("dependency_path") != ["C03", "C06", "C07", "C11", "C14", "C15"]:
        raise OwnerExecutionHandoffError("release dependency path mismatch")

    proof = receipt.get("provider_proof")
    if not isinstance(proof, dict):
        raise OwnerExecutionHandoffError("provider proof is missing")
    required_zero = (
        "airlock_findings",
        "changed_workflows",
        "unadmitted_commits",
        "unexpected_active_workflows",
    )
    if any(proof.get(field) != 0 for field in required_zero):
        raise OwnerExecutionHandoffError("provider proof contains unresolved findings")
    if proof.get("provider_apply_performed") is not False:
        raise OwnerExecutionHandoffError("release already claims provider apply")
    if proof.get("source_mutation_attempted") is not False:
        raise OwnerExecutionHandoffError("release already claims source mutation")

    attestation = receipt.get("attestation_truth")
    if not isinstance(attestation, dict) or any(attestation.values()):
        raise OwnerExecutionHandoffError(
            "release receipt overclaims owner execution or authorization"
        )

    truth = receipt.get("commercial_truth")
    if not isinstance(truth, dict):
        raise OwnerExecutionHandoffError("commercial truth is missing")
    expected_truth = {
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
    for field, expected in expected_truth.items():
        if truth.get(field) != expected:
            raise OwnerExecutionHandoffError(f"commercial truth changed: {field}")

    authority = receipt.get("provider_authority")
    if not isinstance(authority, dict):
        raise OwnerExecutionHandoffError("provider authority readback is missing")
    if authority.get("provider_mutation_performed") is not False:
        raise OwnerExecutionHandoffError("provider authority readback claims mutation")
    if authority.get("target_core_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionHandoffError("target Core repository truth changed")
    if authority.get("target_ops_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionHandoffError("target Ops repository truth changed")

    return {
        "receipt_sha256": receipt_sha,
        "checkpoint_sha256": receipt["checkpoint_sha256"],
        "projection_sha256": receipt["projection_sha256"],
        "implementation_pr": receipt["implementation_pr"],
        "implementation_pr_head": receipt["implementation_pr_head"],
        "merged_main_sha": receipt["merged_main_sha"],
        "drive_release_file_id": receipt["drive_release"]["file_id"],
    }


def build_handoff(
    *,
    release_receipt: dict[str, Any],
    current_source_sha: str,
    owner_login: str,
    repository_full_name: str,
    owner_packet_sha256: str,
    generated_at: datetime,
) -> dict[str, Any]:
    """Create the exact ordered handoff without performing any gated action."""

    predecessor = verify_release_receipt(release_receipt)
    current_source_sha = current_source_sha.lower()
    owner_packet_sha256 = owner_packet_sha256.lower()
    if not HEX40.fullmatch(current_source_sha):
        raise OwnerExecutionHandoffError("current source SHA must be lowercase SHA-1")
    if not HEX64.fullmatch(owner_packet_sha256):
        raise OwnerExecutionHandoffError("owner packet SHA-256 is invalid")
    if not REPOSITORY.fullmatch(repository_full_name):
        raise OwnerExecutionHandoffError("repository identity is invalid")
    if repository_full_name.split("/", 1)[0] != owner_login:
        raise OwnerExecutionHandoffError("owner/repository identity mismatch")
    if generated_at.tzinfo is None:
        raise OwnerExecutionHandoffError("generated_at must include timezone")

    steps = [
        {"sequence": 1, "id": "VERIFY_PACKET_AND_RELEASE_BINDING", "stage": "C03", "entrypoint": "owner_sealed_packet.py", "authority": "A1_INTERNAL", "external_effect": False},
        {"sequence": 2, "id": "EXECUTE_OWNER_CUSTODY_CEREMONY", "stage": "C03", "entrypoint": "owner_custody_ceremony.py", "authority": "OWNER_RESERVED", "external_effect": False},
        {"sequence": 3, "id": "GENERATE_OWNER_ATTESTATION_CHALLENGE", "stage": "C03", "entrypoint": "owner_custody_attestation.py", "authority": "A1_INTERNAL", "external_effect": False},
        {"sequence": 4, "id": "PUBLISH_EXACT_OWNER_ATTESTATION", "stage": "C03", "entrypoint": "provider_authenticated_owner_attestation.py", "authority": "OWNER_RESERVED_EXTERNAL_COMMUNICATION", "external_effect": True},
        {"sequence": 5, "id": "READ_BACK_PROVIDER_NATIVE_OWNER_IDENTITY", "stage": "C03", "entrypoint": "provider_authenticated_owner_attestation.py", "authority": "GET_ONLY_PROVIDER_NATIVE", "external_effect": False},
        {"sequence": 6, "id": "PROBE_FRESH_EXECUTION_PROVIDER_AUTHORITY", "stage": "C03", "entrypoint": "provider_authority_probe.py", "authority": "GET_ONLY_PROVIDER_NATIVE", "external_effect": False},
        {"sequence": 7, "id": "ISSUE_EXACT_SHORT_LIVED_OWNER_DECISION", "stage": "C15", "entrypoint": "provider_attested_authorization.py", "authority": "OWNER_RESERVED", "external_effect": False},
        {"sequence": 8, "id": "VERIFY_PROVIDER_ATTESTED_AUTHORIZATION_INTAKE", "stage": "C15", "entrypoint": "provider_attested_authorization.py", "authority": "A1_INTERNAL", "external_effect": False},
        {"sequence": 9, "id": "REPROBE_AUTHORITY_AND_VALIDATE_CANDIDATE", "stage": "C15", "entrypoint": "provider_cutover_owner_authority_bound.py", "authority": "GET_ONLY_PROVIDER_NATIVE", "external_effect": False},
        {"sequence": 10, "id": "OWNER_RESERVED_PROVIDER_APPLY", "stage": "C15", "entrypoint": "provider_cutover_owner_authority_bound.py", "authority": "OWNER_RESERVED_CONSEQUENTIAL_RELEASE", "external_effect": True},
        {"sequence": 11, "id": "PROVIDER_NATIVE_READBACK_AND_RECONCILIATION", "stage": "C15", "entrypoint": "provider_cutover_outcome_reconciler.py", "authority": "GET_ONLY_PROVIDER_NATIVE", "external_effect": False},
    ]
    body: dict[str, Any] = {
        "schema": HANDOFF_SCHEMA,
        "status": "OWNER_EXECUTION_HANDOFF_VERIFIED_NO_OWNER_ACTION_PERFORMED",
        "generated_at": generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "dependency_path": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "current_source_sha": current_source_sha,
        "owner_login": owner_login,
        "repository_full_name": repository_full_name,
        "owner_packet_sha256": owner_packet_sha256,
        "predecessor_release": predecessor,
        "ordered_steps": steps,
        "owner_reserved_steps": [2, 4, 7, 10],
        "current_blockers": {
            "owner_controlled_custody": "OWNER_EXECUTION_REQUIRED",
            "provider_native_owner_attestation": "OWNER_PUBLICATION_AND_READBACK_REQUIRED",
            "execution_provider_authority": "PROVIDER_BLOCKED_SELECTED_REPOSITORY_INSTALLATION_OR_USER_SCOPED_ADMIN_AUTHORITY_REQUIRED",
            "owner_authorization": "NOT_PRESENT",
        },
        "commercial_truth": {
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
        },
        "owner_action_performed": False,
        "provider_request_performed": False,
        "provider_apply_performed": False,
        "authorization_consumption_state_created": False,
        "credential_value_recorded": False,
        "external_communication_performed": False,
        "external_commercial_gate_advanced": False,
    }
    body["handoff_sha256"] = canonical_sha256(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-receipt", type=Path, required=True)
    parser.add_argument("--current-source-sha", required=True)
    parser.add_argument("--owner-login", required=True)
    parser.add_argument("--repository-full-name", required=True)
    parser.add_argument("--owner-packet-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = build_handoff(
        release_receipt=_load_json(args.release_receipt, "release receipt"),
        current_source_sha=args.current_source_sha,
        owner_login=args.owner_login,
        repository_full_name=args.repository_full_name,
        owner_packet_sha256=args.owner_packet_sha256,
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
