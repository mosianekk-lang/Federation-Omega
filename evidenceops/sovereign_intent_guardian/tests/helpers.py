from __future__ import annotations

import hashlib

from sovereign_intent_guardian.contracts import AuditRequest, ProposedAction, ValidationError, sha256_json
from sovereign_intent_guardian.policy import POLICY_FINGERPRINT


CONTINUITY_KEYS = (
    "mission_id", "mission_version", "latest_instruction_hash", "requirement_ids",
    "source_hashes", "source_readback_hash", "formation_mission_hash", "policy_hash",
    "local_bible_transaction_id", "local_bible_transaction_hash", "local_bible_audit_hash",
    "local_bible_read_model_hash", "local_bible_hash_chain_valid", "mission_current",
    "source_fingerprints_current", "requirements_current",
)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_payload(**overrides):
    explicit_attestation_id = "trusted_attestation_id" in overrides
    payload = {
        "mission_id": "mission-1",
        "mission_version": 2,
        "latest_instruction_hash": digest("Review this bounded read-only plan."),
        "requirement_ids": ["R1", "R2"],
        "source_hashes": {"source-1": "a" * 64, "source-2": "b" * 64},
        "source_readback_hash": "d" * 64,
        "formation_mission_hash": "e" * 64,
        "policy_hash": POLICY_FINGERPRINT,
        "local_bible_transaction_id": "transaction-0009",
        "local_bible_transaction_hash": "c" * 64,
        "local_bible_audit_hash": "f" * 64,
        "local_bible_read_model_hash": "1" * 64,
        "local_bible_hash_chain_valid": True,
        "mission_current": True,
        "source_fingerprints_current": True,
        "requirements_current": True,
        "trusted_attestation_id": "trusted-verifier-1",
        "trusted_attestation_hash": "0" * 64,
        "proposed_action": {
            "action_id": "action-1",
            "authority_class": "A0",
            "kind": "READ_ONLY_AUDIT",
            "description_hash": digest("Inspect a bounded local control record."),
            "requested_effects": [],
            "claim_hashes": [],
            "estimated_cost": 0,
            "recurring_cost": 0,
            "user_burden": 0,
            "reversible": True,
            "owner_decision_required": False,
            "formation_gate_decision": "",
            "formation_permit_current": False,
            "state_claims": {"deployed": False, "proven": False, "autonomous": False},
            "proof": {},
        },
        "manual_user_task_count": 0,
        "cadence_every": 5,
    }
    action_updates = overrides.pop("proposed_action", None)
    payload.update(overrides)
    if action_updates:
        payload["proposed_action"].update(action_updates)
    try:
        normalized_action = ProposedAction.from_dict(payload["proposed_action"]).to_dict()
        binding = {
            **{key: payload[key] for key in CONTINUITY_KEYS},
            "proposed_action": normalized_action,
            "manual_user_task_count": payload["manual_user_task_count"],
            "cadence_every": payload["cadence_every"],
        }
        payload["trusted_attestation_hash"] = sha256_json(binding)
    except (ValidationError, ValueError):
        payload["trusted_attestation_hash"] = "0" * 64
    if not explicit_attestation_id:
        payload["trusted_attestation_id"] = f"trusted-verifier-{payload['trusted_attestation_hash'][:16]}"
    return payload


def audit_request(**overrides):
    return AuditRequest.from_dict(request_payload(**overrides))


def trusted_registry(*requests: AuditRequest) -> dict[str, str]:
    items = requests or (audit_request(),)
    return {item.trusted_attestation_id: item.continuity_binding_hash for item in items}


def trust(store, request: AuditRequest) -> AuditRequest:
    store.trusted_attestations[request.trusted_attestation_id] = request.attestation_binding_hash
    return request


def resume_registry(
    scope: str = "MISSION",
    subject: str = "mission-1",
    new_mission_version: int = 3,
    expected_generation: int = 1,
) -> tuple[dict[str, dict[str, object]], str]:
    record = {
        "scope": scope,
        "subject": subject,
        "new_mission_version": new_mission_version,
        "expected_generation": expected_generation,
    }
    record_hash = sha256_json(record)
    return {record_hash: record}, record_hash
