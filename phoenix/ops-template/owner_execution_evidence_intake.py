#!/usr/bin/env python3
"""Build and verify a fail-closed owner-execution evidence dossier candidate.

The intake validates an exact v37 release receipt, an exact owner-execution
handoff and a contiguous chain of hash-bound step evidence. It does not perform
an owner action, provider request, provider apply, external communication or
commercial-gate advancement. Provider-native and owner-authenticity claims
remain unproven until independently read back from the relevant provider.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

RELEASE_SCHEMA = "AO-COMMERCIAL-PHOENIX-OWNER-EXECUTION-HANDOFF-RELEASE-RECEIPT-37"
RELEASE_STATUS = (
    "OWNER_EXECUTION_HANDOFF_PROVIDER_PROOF_VERIFIED_"
    "OWNER_ACTION_AND_FRESH_PROVIDER_AUTHORITY_REQUIRED"
)
HANDOFF_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-EXECUTION-HANDOFF-1"
HANDOFF_STATUS = "OWNER_EXECUTION_HANDOFF_VERIFIED_NO_OWNER_ACTION_PERFORMED"
EVIDENCE_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-EXECUTION-STEP-EVIDENCE-1"
DOSSIER_SCHEMA = "FEDOMEGA-PHOENIX-OWNER-EXECUTION-EVIDENCE-DOSSIER-1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_STEPS = [
    "VERIFY_PACKET_AND_RELEASE_BINDING",
    "EXECUTE_OWNER_CUSTODY_CEREMONY",
    "GENERATE_OWNER_ATTESTATION_CHALLENGE",
    "PUBLISH_EXACT_OWNER_ATTESTATION",
    "READ_BACK_PROVIDER_NATIVE_OWNER_IDENTITY",
    "PROBE_FRESH_EXECUTION_PROVIDER_AUTHORITY",
    "ISSUE_EXACT_SHORT_LIVED_OWNER_DECISION",
    "VERIFY_PROVIDER_ATTESTED_AUTHORIZATION_INTAKE",
    "REPROBE_AUTHORITY_AND_VALIDATE_CANDIDATE",
    "OWNER_RESERVED_PROVIDER_APPLY",
    "PROVIDER_NATIVE_READBACK_AND_RECONCILIATION",
]
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


class OwnerExecutionEvidenceIntakeError(RuntimeError):
    """Fail-closed owner-execution evidence intake error."""


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerExecutionEvidenceIntakeError(f"{label} is unreadable") from exc
    if not isinstance(payload, dict):
        raise OwnerExecutionEvidenceIntakeError(f"{label} must be a JSON object")
    return payload


def _verify_hash(payload: dict[str, Any], field: str, label: str) -> str:
    claimed = str(payload.get(field) or "").lower()
    if not HEX64.fullmatch(claimed):
        raise OwnerExecutionEvidenceIntakeError(f"{label} hash is invalid")
    body = dict(payload)
    body.pop(field, None)
    if canonical_sha256(body) != claimed:
        raise OwnerExecutionEvidenceIntakeError(f"{label} hash verification failed")
    return claimed


def _require_truth(payload: dict[str, Any], label: str) -> None:
    for field, expected in COMMERCIAL_TRUTH.items():
        if payload.get(field) != expected:
            raise OwnerExecutionEvidenceIntakeError(
                f"{label} commercial truth changed: {field}"
            )


def verify_release_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != RELEASE_SCHEMA:
        raise OwnerExecutionEvidenceIntakeError("release receipt schema mismatch")
    receipt_sha = _verify_hash(receipt, "receipt_sha256", "release receipt")
    if receipt.get("status") != RELEASE_STATUS:
        raise OwnerExecutionEvidenceIntakeError("release receipt status mismatch")
    if receipt.get("dependency_path") != ["C03", "C06", "C07", "C11", "C14", "C15"]:
        raise OwnerExecutionEvidenceIntakeError("release dependency path mismatch")
    _require_truth(receipt.get("commercial_truth") or {}, "release")

    proof = receipt.get("provider_proof")
    if not isinstance(proof, dict):
        raise OwnerExecutionEvidenceIntakeError("provider proof is missing")
    for field in (
        "airlock_findings",
        "changed_workflows",
        "unadmitted_commits",
        "unexpected_active_workflows",
    ):
        if proof.get(field) != 0:
            raise OwnerExecutionEvidenceIntakeError(
                f"provider proof contains unresolved {field}"
            )
    if proof.get("provider_apply_performed") is not False:
        raise OwnerExecutionEvidenceIntakeError("release overclaims provider apply")
    if proof.get("source_mutation_attempted") is not False:
        raise OwnerExecutionEvidenceIntakeError("release overclaims source mutation")
    owner_packet_sha = str(proof.get("owner_packet_sha256") or "").lower()
    if not HEX64.fullmatch(owner_packet_sha):
        raise OwnerExecutionEvidenceIntakeError("release owner packet hash is invalid")

    authority = receipt.get("provider_authority")
    if not isinstance(authority, dict):
        raise OwnerExecutionEvidenceIntakeError("provider authority is missing")
    if authority.get("provider_mutation_performed") is not False:
        raise OwnerExecutionEvidenceIntakeError("authority receipt claims mutation")
    if authority.get("target_core_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionEvidenceIntakeError("Core repository truth changed")
    if authority.get("target_ops_repository") != "NOT_FOUND_NOT_CLAIMED_CREATED":
        raise OwnerExecutionEvidenceIntakeError("Ops repository truth changed")

    attestation = receipt.get("attestation_truth")
    if not isinstance(attestation, dict) or any(attestation.values()):
        raise OwnerExecutionEvidenceIntakeError("release overclaims owner execution")

    return {
        "receipt_sha256": receipt_sha,
        "checkpoint_sha256": receipt["checkpoint_sha256"],
        "projection_sha256": receipt["projection_sha256"],
        "owner_packet_sha256": owner_packet_sha,
        "implementation_pr": receipt["implementation_pr"],
        "implementation_pr_head": receipt["implementation_pr_head"],
        "merged_main_sha": receipt["merged_main_sha"],
        "drive_release_file_id": receipt["drive_release"]["file_id"],
    }


def verify_handoff(
    handoff: dict[str, Any],
    *,
    current_source_sha: str,
    owner_packet_sha256: str,
) -> str:
    if handoff.get("schema") != HANDOFF_SCHEMA:
        raise OwnerExecutionEvidenceIntakeError("handoff schema mismatch")
    handoff_sha = _verify_hash(handoff, "handoff_sha256", "handoff")
    if handoff.get("status") != HANDOFF_STATUS:
        raise OwnerExecutionEvidenceIntakeError("handoff status mismatch")
    if handoff.get("programme_id") != "AO-COMMERCIAL-MATURITY-V1":
        raise OwnerExecutionEvidenceIntakeError("handoff programme mismatch")
    if handoff.get("dependency_path") != ["C03", "C06", "C07", "C11", "C14", "C15"]:
        raise OwnerExecutionEvidenceIntakeError("handoff dependency path mismatch")

    source_sha = str(handoff.get("current_source_sha") or "").lower()
    if not HEX40.fullmatch(source_sha) or source_sha != current_source_sha.lower():
        raise OwnerExecutionEvidenceIntakeError("handoff source binding mismatch")
    if handoff.get("owner_packet_sha256") != owner_packet_sha256:
        raise OwnerExecutionEvidenceIntakeError("handoff owner packet binding mismatch")

    repository = str(handoff.get("repository_full_name") or "")
    owner = str(handoff.get("owner_login") or "")
    if "/" not in repository or repository.split("/", 1)[0] != owner:
        raise OwnerExecutionEvidenceIntakeError("handoff owner identity mismatch")

    steps = handoff.get("ordered_steps")
    if not isinstance(steps, list) or len(steps) != len(EXPECTED_STEPS):
        raise OwnerExecutionEvidenceIntakeError("handoff step count mismatch")
    for index, (step, expected_id) in enumerate(zip(steps, EXPECTED_STEPS), start=1):
        if not isinstance(step, dict):
            raise OwnerExecutionEvidenceIntakeError("handoff step is invalid")
        if step.get("sequence") != index or step.get("id") != expected_id:
            raise OwnerExecutionEvidenceIntakeError("handoff step order mismatch")

    if handoff.get("owner_reserved_steps") != [2, 4, 7, 10]:
        raise OwnerExecutionEvidenceIntakeError("handoff owner-reserved steps drift")
    for field in (
        "owner_action_performed",
        "provider_request_performed",
        "provider_apply_performed",
        "authorization_consumption_state_created",
        "credential_value_recorded",
        "external_communication_performed",
        "external_commercial_gate_advanced",
    ):
        if handoff.get(field) is not False:
            raise OwnerExecutionEvidenceIntakeError(f"unsafe handoff claim: {field}")
    _require_truth(handoff.get("commercial_truth") or {}, "handoff")
    return handoff_sha


def _parse_zulu(value: object, field: str) -> datetime:
    text = str(value or "")
    if not text.endswith("Z"):
        raise OwnerExecutionEvidenceIntakeError(f"{field} must be UTC Zulu time")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise OwnerExecutionEvidenceIntakeError(f"{field} is invalid") from exc
    return parsed


def verify_step_evidence(
    evidence: dict[str, Any],
    *,
    expected_step: dict[str, Any],
    handoff_sha256: str,
) -> str:
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise OwnerExecutionEvidenceIntakeError("step evidence schema mismatch")
    evidence_sha = _verify_hash(evidence, "evidence_sha256", "step evidence")
    if evidence.get("status") != "STEP_EVIDENCE_CANDIDATE_VERIFIED_NOT_PROVIDER_PROOF":
        raise OwnerExecutionEvidenceIntakeError("step evidence status mismatch")
    if evidence.get("handoff_sha256") != handoff_sha256:
        raise OwnerExecutionEvidenceIntakeError("step evidence handoff binding mismatch")

    for field in ("sequence", "step_id", "stage", "authority", "external_effect"):
        expected_value = {
            "sequence": expected_step["sequence"],
            "step_id": expected_step["id"],
            "stage": expected_step["stage"],
            "authority": expected_step["authority"],
            "external_effect": expected_step["external_effect"],
        }[field]
        if evidence.get(field) != expected_value:
            raise OwnerExecutionEvidenceIntakeError(
                f"step evidence metadata mismatch: {field}"
            )

    if evidence.get("mock_conformance") is not False:
        raise OwnerExecutionEvidenceIntakeError(
            "mock conformance cannot enter the execution evidence chain"
        )
    if evidence.get("credential_value_recorded") is not False:
        raise OwnerExecutionEvidenceIntakeError("credential material is prohibited")
    if evidence.get("external_commercial_gate_advanced") is not False:
        raise OwnerExecutionEvidenceIntakeError(
            "step evidence cannot advance an external commercial gate"
        )

    artifact_sha = str(evidence.get("artifact_sha256") or "").lower()
    if not HEX64.fullmatch(artifact_sha):
        raise OwnerExecutionEvidenceIntakeError("step artifact hash is invalid")
    _parse_zulu(evidence.get("recorded_at"), "recorded_at")

    authority = expected_step["authority"]
    mode = evidence.get("evidence_mode")
    owner_attested = evidence.get("owner_attested")
    provider_native = evidence.get("provider_native")
    external_communication = evidence.get("external_communication_performed")
    provider_apply = evidence.get("provider_apply_performed")

    if authority == "A1_INTERNAL":
        if mode != "INTERNAL_HASH_BOUND" or owner_attested is not False or provider_native is not False:
            raise OwnerExecutionEvidenceIntakeError("internal evidence mode mismatch")
    elif authority == "OWNER_RESERVED":
        if mode != "OWNER_ATTESTED_CANDIDATE" or owner_attested is not True or provider_native is not False:
            raise OwnerExecutionEvidenceIntakeError("owner-reserved evidence mode mismatch")
    elif authority == "GET_ONLY_PROVIDER_NATIVE":
        if mode != "PROVIDER_NATIVE_READBACK_CANDIDATE" or provider_native is not True:
            raise OwnerExecutionEvidenceIntakeError("provider readback evidence mode mismatch")
    elif authority in (
        "OWNER_RESERVED_EXTERNAL_COMMUNICATION",
        "OWNER_RESERVED_CONSEQUENTIAL_RELEASE",
    ):
        if (
            mode != "OWNER_AND_PROVIDER_NATIVE_CANDIDATE"
            or owner_attested is not True
            or provider_native is not True
        ):
            raise OwnerExecutionEvidenceIntakeError(
                "owner/provider evidence mode mismatch"
            )
    else:
        raise OwnerExecutionEvidenceIntakeError("unsupported authority class")

    expected_external_communication = expected_step["sequence"] == 4
    expected_provider_apply = expected_step["sequence"] == 10
    if external_communication is not expected_external_communication:
        raise OwnerExecutionEvidenceIntakeError("external communication truth mismatch")
    if provider_apply is not expected_provider_apply:
        raise OwnerExecutionEvidenceIntakeError("provider apply truth mismatch")
    return evidence_sha


def build_dossier(
    *,
    release_receipt: dict[str, Any],
    handoff: dict[str, Any],
    evidence_chain: Iterable[dict[str, Any]],
    current_source_sha: str,
    generated_at: datetime,
) -> dict[str, Any]:
    predecessor = verify_release_receipt(release_receipt)
    if not HEX40.fullmatch(current_source_sha.lower()):
        raise OwnerExecutionEvidenceIntakeError("current source SHA is invalid")
    handoff_sha = verify_handoff(
        handoff,
        current_source_sha=current_source_sha,
        owner_packet_sha256=predecessor["owner_packet_sha256"],
    )
    if generated_at.tzinfo is None:
        raise OwnerExecutionEvidenceIntakeError("generated_at must include timezone")

    evidence_list = list(evidence_chain)
    if len(evidence_list) > len(EXPECTED_STEPS):
        raise OwnerExecutionEvidenceIntakeError("too many step evidence records")

    admitted: list[dict[str, Any]] = []
    for expected_sequence, evidence in enumerate(evidence_list, start=1):
        expected_step = handoff["ordered_steps"][expected_sequence - 1]
        if evidence.get("sequence") != expected_sequence:
            raise OwnerExecutionEvidenceIntakeError(
                "evidence chain must be contiguous and dependency ordered"
            )
        evidence_sha = verify_step_evidence(
            evidence,
            expected_step=expected_step,
            handoff_sha256=handoff_sha,
        )
        admitted.append(
            {
                "sequence": expected_sequence,
                "step_id": expected_step["id"],
                "evidence_sha256": evidence_sha,
                "evidence_mode": evidence["evidence_mode"],
            }
        )

    next_step = None
    if len(admitted) < len(EXPECTED_STEPS):
        step = handoff["ordered_steps"][len(admitted)]
        next_step = {
            "sequence": step["sequence"],
            "step_id": step["id"],
            "authority": step["authority"],
            "owner_reserved": step["sequence"] in handoff["owner_reserved_steps"],
        }

    body: dict[str, Any] = {
        "schema": DOSSIER_SCHEMA,
        "status": (
            "OWNER_EXECUTION_EVIDENCE_DOSSIER_CANDIDATE_VERIFIED_"
            "NO_OWNER_OR_PROVIDER_PROOF_ADVANCED"
        ),
        "generated_at": generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "programme_id": "AO-COMMERCIAL-MATURITY-V1",
        "dependency_path": ["C03", "C06", "C07", "C11", "C14", "C15"],
        "current_source_sha": current_source_sha.lower(),
        "release_receipt_sha256": predecessor["receipt_sha256"],
        "handoff_sha256": handoff_sha,
        "owner_packet_sha256": predecessor["owner_packet_sha256"],
        "admitted_evidence": admitted,
        "admitted_evidence_count": len(admitted),
        "highest_candidate_step": len(admitted),
        "candidate_chain_complete": len(admitted) == len(EXPECTED_STEPS),
        "next_eligible_step": next_step,
        "owner_execution_proven": False,
        "owner_identity_authenticity_proven": False,
        "owner_authorization_proven": False,
        "provider_authority_proven": False,
        "provider_apply_proven": False,
        "provider_native_outcome_proven": False,
        "external_commercial_gate_advanced": False,
        "requires_independent_provider_native_verification": True,
        "commercial_truth": dict(COMMERCIAL_TRUTH),
    }
    body["dossier_sha256"] = canonical_sha256(body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-receipt", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--current-source-sha", required=True)
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = build_dossier(
        release_receipt=_load_json(args.release_receipt, "release receipt"),
        handoff=_load_json(args.handoff, "handoff"),
        evidence_chain=[_load_json(path, f"evidence {path}") for path in args.evidence],
        current_source_sha=args.current_source_sha,
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
