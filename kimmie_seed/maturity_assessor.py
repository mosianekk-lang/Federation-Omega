#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from typing import Any
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
GENOME = ROOT / "kimmie_seed" / "genome.json"
ENV = ROOT / "kimmie_seed" / "environment_profile.json"
REGISTRY = ROOT / "kimmie_seed" / "registry.json"
WORKFLOW_RECEIPT = ROOT / "kimmie_seed" / "monitoring" / "first_successful_workflow_receipt.json"
OUT = ROOT / "kimmie_seed" / "monitoring" / "latest_assessment.json"

STAGES = ("SEED", "GERMINATED", "ROOTED", "SPROUT", "SAPLING", "MATURE", "FEDERATED")
STAGE_RANK = {stage: rank for rank, stage in enumerate(STAGES)}
REQUIRED = {
    "durable_state",
    "authorised_storage",
    "audit_ledger",
    "hashing",
    "connector_registry",
    "rollback",
    "maintenance_owner",
}
SAPLING_REQUIREMENTS = {
    "repeated_successful_maturity_cycles",
    "reusable_capability_multiple_corpora_or_environments",
    "persistent_monitoring",
    "maintenance_evidence",
    "recovery_evidence",
}
MATURE_REQUIREMENTS = {
    "sustained_production_use",
    "resilience_over_time",
    "measurable_operational_value",
    "complete_operational_ownership",
}


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def is_verified(value: Any) -> bool:
    if value is True:
        return True
    if not isinstance(value, str):
        return False
    state = value.upper()
    return (
        state in {"PASS", "PASSED", "VERIFIED", "COMPLETE", "COMPLETED", "PRESENT"}
        or state.startswith("PASSED_")
        or state.startswith("VERIFIED_")
    )


def flatten_states(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from flatten_states(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from flatten_states(nested)
    else:
        yield value


def validate_workflow_receipt(seed_id: str, receipt_path: Path = WORKFLOW_RECEIPT):
    if not receipt_path.exists():
        return False, "ABSENT", None
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    expected_hash = receipt.pop("receipt_sha256", None)
    actual_hash = canonical_hash(receipt)
    valid = (
        expected_hash == actual_hash
        and receipt.get("seed_id") == seed_id
        and receipt.get("workflow_result") == "PASS"
        and receipt.get("assessment_status") == "PASS"
    )
    receipt["receipt_sha256"] = expected_hash
    return valid, ("PASSED" if valid else "FAILED"), receipt


def child_is_useful_and_verified(lane: dict[str, Any]) -> bool:
    """Verify a useful child from current lane evidence, without hard-coding one child schema."""
    if STAGE_RANK.get(lane.get("verified_stage", "SEED"), 0) < STAGE_RANK["SPROUT"]:
        return False
    if lane.get("operational_state") in {"BLOCKED", "DORMANT", "FAILED"}:
        return False

    environment_states = list(flatten_states(lane.get("authorised_environment", {})))
    if not any(is_verified(state) for state in environment_states):
        return False

    nutrients = lane.get("required_nutrients", {})
    proof_receipt = nutrients.get("proof_receipt") if isinstance(nutrients, dict) else None
    if not is_verified(proof_receipt):
        return False

    proof_states = list(flatten_states(lane.get("proof_gates", {})))
    if sum(1 for state in proof_states if is_verified(state)) < 2:
        return False

    maintenance_owner = (
        lane.get("maintenance_owner")
        or (nutrients.get("maintenance_owner") if isinstance(nutrients, dict) else None)
    )
    if not maintenance_owner or str(maintenance_owner).upper() in {"UNVERIFIED", "ABSENT", "NONE"}:
        return False
    return True


def all_gate_requirements_verified(requirements: dict[str, Any], required_keys: set[str]) -> bool:
    return bool(required_keys) and all(
        key in requirements and is_verified(requirements[key]) for key in required_keys
    )


def stage_requirements(
    registry: dict[str, Any],
    candidate_stage: str,
    explicit_key: str,
) -> dict[str, Any]:
    """Resolve the named stage gate while preserving the active-gate compatibility alias."""
    gate = registry.get("promotion_gate", {})
    requirements = gate.get(explicit_key, {})
    if requirements:
        return requirements
    if gate.get("next_candidate_stage") == candidate_stage:
        active_requirements = gate.get("requirements", {})
        if isinstance(active_requirements, dict):
            return active_requirements
    return {}


def assess(genome: dict[str, Any], environment: dict[str, Any], registry: dict[str, Any],
           receipt_valid: bool, receipt_state: str, receipt: dict[str, Any] | None) -> dict[str, Any]:
    states = {item["type"]: item["state"] for item in environment["nutrients"]}
    missing = sorted(
        nutrient for nutrient in REQUIRED
        if not str(states.get(nutrient, "")).startswith("VERIFIED")
    )

    stage = "ROOTED" if not missing else "SEED"
    verified_children = [
        lane.get("lane_id") for lane in registry.get("child_lanes", [])
        if child_is_useful_and_verified(lane)
    ]
    useful_child_verified = bool(verified_children)

    if stage == "ROOTED" and useful_child_verified and receipt_valid:
        stage = "SPROUT"

    sapling = registry.get("promotion_gate", {}).get("sapling_requirements", {})
    if stage == "SPROUT" and all_gate_requirements_verified(sapling, SAPLING_REQUIREMENTS):
        stage = "SAPLING"

    mature = stage_requirements(registry, "MATURE", "mature_requirements")
    if stage == "SAPLING" and all_gate_requirements_verified(mature, MATURE_REQUIREMENTS):
        stage = "MATURE"

    federated = stage_requirements(registry, "FEDERATED", "federated_requirements")
    if stage == "MATURE" and federated and all(is_verified(value) for value in flatten_states(federated)):
        stage = "FEDERATED"

    next_gate = {
        "SEED": "GERMINATED requires verified access to an authorised environment and required foundational nutrients",
        "ROOTED": "SPROUT requires a useful child capability execution plus proof receipt, readback and a successful dedicated maturity workflow receipt",
        "SPROUT": "SAPLING requires repeated successful maturity cycles, reusable execution, persistent monitoring, maintenance and recovery evidence",
        "SAPLING": "MATURE requires sustained production use, resilience, measurable value and complete operational ownership",
        "MATURE": "FEDERATED requires verified operation across authorised independent environments with identity and governance continuity",
        "FEDERATED": "Maintain federation health, identity integrity and verified recovery capability",
    }.get(stage, "Complete the next verified maturity gate")

    result = {
        "seed_id": genome["seed_id"],
        "verified_stage": stage,
        "registry_stage": registry["current_verified_stage"],
        "identity_drift": "NONE_DETECTED",
        "missing_required_nutrients": missing,
        "useful_child_capability_verified": useful_child_verified,
        "verified_useful_child_lanes": verified_children,
        "workflow_receipt_validation": receipt_state,
        "workflow_receipt_sha256": receipt.get("receipt_sha256") if receipt else None,
        "sapling_gate_verified": all_gate_requirements_verified(sapling, SAPLING_REQUIREMENTS),
        "mature_gate_verified": all_gate_requirements_verified(mature, MATURE_REQUIREMENTS),
        "next_gate": next_gate,
        "status": "PASS" if stage == registry["current_verified_stage"] else "STAGE_DRIFT",
    }
    result["assessment_sha256"] = canonical_hash(result)
    return result


def main() -> int:
    genome = json.loads(GENOME.read_text(encoding="utf-8"))
    environment = json.loads(ENV.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    expected_hash = genome.pop("genome_sha256")
    actual_hash = canonical_hash(genome)
    genome["genome_sha256"] = expected_hash
    if actual_hash != expected_hash:
        raise SystemExit("GENOME_HASH_MISMATCH")

    receipt_valid, receipt_state, receipt = validate_workflow_receipt(genome["seed_id"])
    result = assess(genome, environment, registry, receipt_valid, receipt_state, receipt)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
