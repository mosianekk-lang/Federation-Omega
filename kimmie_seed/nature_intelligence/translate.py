#!/usr/bin/env python3
"""Deterministically translate Nature Intelligence hypotheses into bounded engineering candidates."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "source_manifest.json"
HEALTH_PATH = ROOT / "monitoring" / "latest_health.json"
TRANSLATION_PATH = ROOT / "monitoring" / "latest_translation.json"
RECEIPT_PATH = ROOT / "receipts" / "latest_translation_receipt.json"

PATTERNS: dict[str, dict[str, Any]] = {
    "variation supplies alternatives before selection": {"engineering_pattern": "candidate_portfolio_before_promotion", "target_domain": "decision_systems", "design_constraints": ["generate more than one bounded candidate", "hold promotion until evidence gates pass", "retain rejected candidates with reasons"], "proof_gate": "At least two candidates are evaluated under the same deterministic test contract.", "failure_modes": ["single-candidate lock-in", "selection without comparable evidence"]},
    "environmental pressure filters alternatives over repeated cycles": {"engineering_pattern": "repeated_evidence_filtering", "target_domain": "continuous_validation", "design_constraints": ["use repeatable test conditions", "record every cycle result", "promote only after repeated passes"], "proof_gate": "Two distinct cycles pass with durable readback and stable identity.", "failure_modes": ["one-shot success treated as maturity", "test environment drift"]},
    "adaptation is cumulative and context-dependent": {"engineering_pattern": "versioned_context_learning", "target_domain": "learning_systems", "design_constraints": ["preserve prior versions", "record context with every lesson", "do not generalise beyond observed conditions"], "proof_gate": "A later version improves a measured outcome without losing provenance.", "failure_modes": ["context-free lesson reuse", "silent overwrite of prior learning"]},
    "branching preserves diversity while enabling specialization": {"engineering_pattern": "isolated_specialist_branches", "target_domain": "workstream_orchestration", "design_constraints": ["isolate specialist workstreams", "use collision keys and leases", "merge only after independent verification"], "proof_gate": "Parallel branches produce non-colliding artifacts and a verified merge.", "failure_modes": ["cross-lane contamination", "premature branch convergence"]},
    "deliberate constraints reduce waste and reveal essential function": {"engineering_pattern": "minimum_sufficient_build", "target_domain": "system_design", "design_constraints": ["define a strict objective boundary", "exclude nonessential dependencies", "measure whether each component contributes to the objective"], "proof_gate": "Removing nonessential components does not reduce required test coverage.", "failure_modes": ["feature accumulation", "dependency inflation"]},
    "direct observation produces stronger feedback than inherited assumption": {"engineering_pattern": "provider_native_readback", "target_domain": "evidence_operations", "design_constraints": ["read results from the execution provider", "separate observed state from expected state", "store exact identifiers and hashes"], "proof_gate": "Destination-native state is read back and matches the expected artifact hash.", "failure_modes": ["claiming execution from design", "relying only on local expectations"]},
    "simplicity can increase resilience by lowering dependency load": {"engineering_pattern": "dependency_minimisation", "target_domain": "reliability_engineering", "design_constraints": ["prefer standard-library paths where sufficient", "make optional dependencies explicit", "test degraded operation"], "proof_gate": "The capability passes its core test contract with the minimum declared dependencies.", "failure_modes": ["hidden dependency", "fragile transitive dependency chain"]},
    "periodic withdrawal creates space for system-level reflection": {"engineering_pattern": "checkpoint_and_reflection_cycle", "target_domain": "operations_governance", "design_constraints": ["pause at defined checkpoints", "reconcile current state against mission", "record lessons before continuing"], "proof_gate": "A checkpoint detects or prevents at least one material drift or defect.", "failure_modes": ["continuous action without reconciliation", "lesson loss"]},
    "distributed coordination can emerge from local role rules": {"engineering_pattern": "packet_bound_distributed_roles", "target_domain": "multi_agent_orchestration", "design_constraints": ["give every role a unique packet", "bound authority per role", "require leases and collision keys"], "proof_gate": "All roles are uniquely packet-bound and no collision key is duplicated.", "failure_modes": ["role ambiguity", "duplicate ownership", "unbounded authority"]},
    "specialization raises throughput but requires shared survival signals": {"engineering_pattern": "specialist_squads_shared_health", "target_domain": "operational_scaling", "design_constraints": ["specialise role responsibilities", "share canonical health signals", "stop local optimisation that harms root objectives"], "proof_gate": "Specialist outputs improve throughput while root health gates remain passing.", "failure_modes": ["local optimum harms system", "siloed monitoring"]},
    "redundancy and replacement protect collective continuity": {"engineering_pattern": "verified_failover_and_recovery", "target_domain": "resilience_engineering", "design_constraints": ["maintain a recoverable canonical baseline", "detect corruption before use", "prove exact restoration"], "proof_gate": "A controlled corruption is rejected and deterministic recovery restores the baseline hash.", "failure_modes": ["silent corruption", "backup without tested restoration"]},
    "collective adaptation may outperform isolated optimization": {"engineering_pattern": "ensemble_with_independent_verification", "target_domain": "quality_assurance", "design_constraints": ["separate producer and verifier roles", "aggregate evidence rather than votes alone", "retain dissent and defect records"], "proof_gate": "Independent verification catches a defect or confirms the same result through a separate route.", "failure_modes": ["groupthink", "majority vote without evidence"]}
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def add_digest(payload: dict[str, Any], field: str) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result[field] = canonical_sha256(result)
    return result


def validate_inputs(manifest: dict[str, Any], health: dict[str, Any]) -> None:
    if manifest.get("lane_id") != "LANE-KIMMIE-NATURE-INTELLIGENCE":
        raise ValueError("manifest_lane_identity_mismatch")
    if health.get("lane_id") != manifest["lane_id"]:
        raise ValueError("health_lane_identity_mismatch")
    if health.get("status") != "PASS":
        raise ValueError("health_not_passing")
    if health.get("identity_drift") != "NONE_DETECTED":
        raise ValueError("identity_drift_detected")
    if health.get("full_text_persisted") is not False:
        raise ValueError("full_text_persistence_boundary_violated")
    manifest_sources = {item["source_id"]: item for item in manifest["sources"]}
    health_sources = {item["source_id"]: item for item in health["results"]}
    if set(manifest_sources) != set(health_sources):
        raise ValueError("source_set_mismatch")
    for source_id, observed in health_sources.items():
        if observed.get("validation") != "PASS":
            raise ValueError(f"source_validation_failed:{source_id}")
        if observed.get("mechanism_hypotheses") != manifest_sources[source_id].get("mechanism_hypotheses"):
            raise ValueError(f"hypothesis_drift:{source_id}")


def build_translation(manifest: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    validate_inputs(manifest, health)
    records: list[dict[str, Any]] = []
    for source in sorted(manifest["sources"], key=lambda item: item["source_id"]):
        for hypothesis in source["mechanism_hypotheses"]:
            if hypothesis not in PATTERNS:
                raise ValueError(f"unmapped_hypothesis:{hypothesis}")
            record = {
                "mechanism_id": "NAT-MECH-" + hashlib.sha256(f"{source['source_id']}|{hypothesis}".encode("utf-8")).hexdigest()[:16],
                "source_id": source["source_id"],
                "source_title": source["title"],
                "hypothesis": hypothesis,
                **copy.deepcopy(PATTERNS[hypothesis]),
                "claim_state": "ENGINEERING_CANDIDATE_NOT_DEPLOYED"
            }
            record["record_sha256"] = canonical_sha256(record)
            records.append(record)
    payload = {
        "schema_version": "1.0.0",
        "lane_id": manifest["lane_id"],
        "manifest_version": manifest["manifest_version"],
        "source_manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "source_health_sha256": health["health_sha256"],
        "corpus_sha256": health["corpus_sha256"],
        "identity_drift": "NONE_DETECTED",
        "mechanism_count": len(records),
        "records": records,
        "translation_state": "STABLE_DETERMINISTIC_RUNTIME_OUTPUT",
        "proof_boundary": "This output proves deterministic translation of registered mechanism hypotheses into bounded engineering candidates. It does not prove that any candidate is useful, deployed, mature, or causally validated."
    }
    return add_digest(payload, "translation_sha256")


def validate_translation(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "1.0.0":
        raise ValueError("unsupported_schema")
    if payload.get("lane_id") != "LANE-KIMMIE-NATURE-INTELLIGENCE":
        raise ValueError("lane_identity_mismatch")
    if payload.get("identity_drift") != "NONE_DETECTED":
        raise ValueError("identity_drift")
    records = payload.get("records")
    if not isinstance(records, list) or payload.get("mechanism_count") != len(records):
        raise ValueError("mechanism_count_mismatch")
    ids = [record.get("mechanism_id") for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_mechanism_id")
    for record in records:
        supplied = record.get("record_sha256")
        candidate = dict(record)
        candidate.pop("record_sha256", None)
        if supplied != canonical_sha256(candidate):
            raise ValueError(f"record_digest_mismatch:{record.get('mechanism_id')}")
        if record.get("claim_state") != "ENGINEERING_CANDIDATE_NOT_DEPLOYED":
            raise ValueError("claim_boundary_violation")
    supplied_translation = payload.get("translation_sha256")
    candidate_translation = dict(payload)
    candidate_translation.pop("translation_sha256", None)
    if supplied_translation != canonical_sha256(candidate_translation):
        raise ValueError("translation_digest_mismatch")


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    health = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    translation = build_translation(manifest, health)
    validate_translation(translation)
    TRANSLATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATION_PATH.write_text(json.dumps(translation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = add_digest({"receipt_id": "NATURE-TRANSLATION-" + translation["translation_sha256"][:20], "lane_id": translation["lane_id"], "schema_version": translation["schema_version"], "translation_sha256": translation["translation_sha256"], "source_health_sha256": translation["source_health_sha256"], "corpus_sha256": translation["corpus_sha256"], "mechanism_count": translation["mechanism_count"], "validation": "PASS", "identity_drift": "NONE_DETECTED", "proof_boundary": translation["proof_boundary"]}, "receipt_sha256")
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "translation_sha256": translation["translation_sha256"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
