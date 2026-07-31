#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
GENOME = ROOT / "kimmie_seed" / "genome.json"
ENV = ROOT / "kimmie_seed" / "environment_profile.json"
REGISTRY = ROOT / "kimmie_seed" / "registry.json"
WORKFLOW_RECEIPT = ROOT / "kimmie_seed" / "monitoring" / "first_successful_workflow_receipt.json"
OUT = ROOT / "kimmie_seed" / "monitoring" / "latest_assessment.json"
REQUIRED = {
    "durable_state",
    "authorised_storage",
    "audit_ledger",
    "hashing",
    "connector_registry",
    "rollback",
    "maintenance_owner",
}


def canonical_hash(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_workflow_receipt(seed_id: str):
    if not WORKFLOW_RECEIPT.exists():
        return False, "ABSENT", None
    receipt = json.loads(WORKFLOW_RECEIPT.read_text())
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


def main():
    genome = json.loads(GENOME.read_text())
    environment = json.loads(ENV.read_text())
    registry = json.loads(REGISTRY.read_text())

    expected_hash = genome.pop("genome_sha256")
    actual_hash = canonical_hash(genome)
    genome["genome_sha256"] = expected_hash
    if actual_hash != expected_hash:
        raise SystemExit("GENOME_HASH_MISMATCH")

    states = {item["type"]: item["state"] for item in environment["nutrients"]}
    missing = sorted(
        nutrient
        for nutrient in REQUIRED
        if not states.get(nutrient, "").startswith("VERIFIED")
    )

    stage = "ROOTED" if not missing else "SEED"
    child_lanes = {item["lane_id"]: item for item in registry.get("child_lanes", [])}
    passport = child_lanes.get("LANE-PROVENANCE-PASSPORT", {})
    useful_child_verified = (
        passport.get("verified_stage") in {"SPROUT", "SAPLING", "MATURE", "FEDERATED"}
        and passport.get("proof_gates", {}).get("drive_readback") == "PASSED"
        and passport.get("proof_gates", {}).get("merkle_root_independent_recalculation") == "PASSED"
    )
    receipt_valid, receipt_state, receipt = validate_workflow_receipt(genome["seed_id"])

    if stage == "ROOTED" and useful_child_verified and receipt_valid:
        stage = "SPROUT"

    next_gate = (
        "SAPLING requires repeated successful maturity cycles, a reusable child "
        "capability across multiple corpora or environments, persistent monitoring, "
        "maintenance and recovery evidence"
        if stage == "SPROUT"
        else "SPROUT requires a useful child capability execution plus proof receipt, readback and a successful dedicated maturity workflow receipt"
    )

    result = {
        "seed_id": genome["seed_id"],
        "verified_stage": stage,
        "registry_stage": registry["current_verified_stage"],
        "identity_drift": "NONE_DETECTED",
        "missing_required_nutrients": missing,
        "useful_child_capability_verified": useful_child_verified,
        "workflow_receipt_validation": receipt_state,
        "workflow_receipt_sha256": receipt.get("receipt_sha256") if receipt else None,
        "next_gate": next_gate,
        "status": (
            "PASS"
            if stage == registry["current_verified_stage"]
            else "STAGE_DRIFT"
        ),
    }
    result["assessment_sha256"] = canonical_hash(result)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
