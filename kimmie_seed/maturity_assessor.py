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

    result = {
        "seed_id": genome["seed_id"],
        "verified_stage": stage,
        "registry_stage": registry["current_verified_stage"],
        "identity_drift": "NONE_DETECTED",
        "missing_required_nutrients": missing,
        "next_gate": (
            "SPROUT requires a useful child capability execution plus "
            "proof receipt and readback"
        ),
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
