#!/usr/bin/env python3
"""Reconcile MAX-Technical activation and verified Nature Intelligence ROOTED gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "kimmie_seed" / "registry.json"
TRANSLATION_PATH = REPO / "kimmie_seed" / "nature_intelligence" / "monitoring" / "latest_translation.json"
TRANSLATION_RECEIPT_PATH = REPO / "kimmie_seed" / "nature_intelligence" / "receipts" / "latest_translation_receipt.json"
RECOVERY_RECEIPT_PATH = REPO / "kimmie_seed" / "nature_intelligence" / "recovery" / "latest_recovery_receipt.json"
GATE_HEALTH_PATH = REPO / "kimmie_seed" / "nature_intelligence" / "monitoring" / "latest_rooted_gate_health.json"
MAX_PROFILE_PATH = REPO / "evidenceops" / "runtime" / "MAX_TECHNICAL_CAPABILITY_KIMMIE.json"
CHECKPOINT_PATH = REPO / "kimmie_seed" / "checkpoints" / "KSA-20260803-024.json"
LANE_RECEIPT_PATH = REPO / "evidenceops" / "innovation_engine" / "receipts" / "lane-watch-receipt-028.json"

PROFILE_COMMIT = "b9dafd7868ffefb5862c24e1f024e6cd148006d6"
WORKFLOW_SOURCE_COMMIT = "d883140478cc527f76de231d476a0ed77f842e89"
PROOF_COMMIT = "9a6608130e6d98dd583177d1b35bea9c3c3a75e0"
WORKFLOW_RUN_ID = "30791514633"
BIBLE_REVISION = "AIroW35HNbHAEe7d_WP7acwMtPl5h6KF7zo9vuGemZCcWxanE_aAYVOpONQ5iW3hXkGyH_CGM5RyuEEhLgCyCt7TPkzl624MFXN_r1djjZ0"
BIBLE_NOTE_SHA256 = "322cfe083b3c7e9b31c0db02fd427dd0e7dbd1c68525117d0a65033945cecbc6"
BIBLE_HEADING_RANGE = {"start_index": 117565, "end_index": 117644, "tab_id": "t.0"}
BIBLE_HASH_RANGE = {"start_index": 119674, "end_index": 119738, "tab_id": "t.0"}


def canonical_sha256(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def write_hashed(path: Path, payload: dict[str, Any], field: str) -> str:
    digest = canonical_sha256(payload)
    payload[field] = digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return digest


def main() -> int:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    translation = json.loads(TRANSLATION_PATH.read_text(encoding="utf-8"))
    translation_receipt = json.loads(TRANSLATION_RECEIPT_PATH.read_text(encoding="utf-8"))
    recovery = json.loads(RECOVERY_RECEIPT_PATH.read_text(encoding="utf-8"))
    gate_health = json.loads(GATE_HEALTH_PATH.read_text(encoding="utf-8"))
    max_profile = json.loads(MAX_PROFILE_PATH.read_text(encoding="utf-8"))

    assert registry["seed_id"] == "KIMMIE-IPEP-001"
    assert registry["current_verified_stage"] == "SAPLING"
    assert registry["identity_drift"] == "NONE_DETECTED"
    child = next(item for item in registry["child_lanes"] if item["lane_id"] == "LANE-KIMMIE-NATURE-INTELLIGENCE")
    assert child["verified_stage"] == "GERMINATED"

    assert max_profile["state"] == "ACTIVE_VERIFIED_EXECUTION_PROFILE"
    assert translation["translation_state"] == "STABLE_DETERMINISTIC_RUNTIME_OUTPUT"
    assert translation["mechanism_count"] == 12
    assert translation["identity_drift"] == "NONE_DETECTED"
    assert translation_receipt["validation"] == "PASS"
    assert translation_receipt["translation_sha256"] == translation["translation_sha256"]
    assert recovery["controlled_recovery"] == "PASS"
    assert recovery["exact_restoration"] == "PASS"
    assert recovery["baseline_translation_sha256"] == recovery["recovered_translation_sha256"] == translation["translation_sha256"]
    assert gate_health["workflow_event"] == "push"
    assert gate_health["stable_translation_runtime"] == "PASS"
    assert gate_health["controlled_recovery"] == "PASS"
    assert gate_health["schedule_triggered_monitoring"] == "NOT_YET_VERIFIED"
    assert gate_health["identity_drift"] == "NONE_DETECTED"

    observed_at = "2026-08-03T08:50:42+02:00"
    checkpoint = {
        "checkpoint_id": "KSA-20260803-024",
        "observed_at": observed_at,
        "seed_id": registry["seed_id"],
        "root_stage": registry["current_verified_stage"],
        "child_lane": child["lane_id"],
        "child_stage": child["verified_stage"],
        "event": "MAX_TECHNICAL_ACTIVATED_NATURE_ROOTED_GATES_PARTIAL_PASS",
        "profile_id": max_profile["profile_id"],
        "profile_commit": PROFILE_COMMIT,
        "workflow_source_commit": WORKFLOW_SOURCE_COMMIT,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "workflow_event": gate_health["workflow_event"],
        "proof_commit": PROOF_COMMIT,
        "mechanism_count": translation["mechanism_count"],
        "translation_sha256": translation["translation_sha256"],
        "translation_receipt_sha256": translation_receipt["receipt_sha256"],
        "recovery_receipt_sha256": recovery["receipt_sha256"],
        "gate_health_sha256": gate_health["health_sha256"],
        "stable_translation_runtime": "VERIFIED",
        "controlled_recovery": "VERIFIED",
        "schedule_triggered_monitoring": "NOT_YET_VERIFIED",
        "root_promotion": "NONE",
        "child_promotion": "NONE",
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
        "truth_boundary": "Nature Intelligence remains GERMINATED. ROOTED is withheld until an actual schedule-triggered provider run passes and is durably read back."
    }
    checkpoint_sha = write_hashed(CHECKPOINT_PATH, checkpoint, "checkpoint_sha256")

    lane_receipt = {
        "receipt_id": "LANE-WATCH-RECEIPT-028",
        "observed_at": observed_at,
        "seed_id": registry["seed_id"],
        "lane_id": child["lane_id"],
        "event": checkpoint["event"],
        "checkpoint_path": "kimmie_seed/checkpoints/KSA-20260803-024.json",
        "checkpoint_sha256": checkpoint_sha,
        "profile_path": "evidenceops/runtime/MAX_TECHNICAL_CAPABILITY_KIMMIE.json",
        "profile_commit": PROFILE_COMMIT,
        "workflow_source_commit": WORKFLOW_SOURCE_COMMIT,
        "workflow_run_id": WORKFLOW_RUN_ID,
        "proof_commit": PROOF_COMMIT,
        "translation_path": "kimmie_seed/nature_intelligence/monitoring/latest_translation.json",
        "translation_sha256": translation["translation_sha256"],
        "translation_receipt_sha256": translation_receipt["receipt_sha256"],
        "recovery_receipt_sha256": recovery["receipt_sha256"],
        "gate_health_sha256": gate_health["health_sha256"],
        "ipep_bible": {
            "receipt": "EVIDENCE NOTE — MAX-TECHNICAL CAPABILITY ACTIVATION AND NATURE ROOTED GATES 028",
            "revision_id": BIBLE_REVISION,
            "heading_readback": BIBLE_HEADING_RANGE,
            "hash_readback": BIBLE_HASH_RANGE,
            "evidence_note_sha256": BIBLE_NOTE_SHA256
        },
        "root_promotion": "NONE",
        "child_promotion": "NONE",
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
        "status": "PASS"
    }
    lane_receipt_sha = write_hashed(LANE_RECEIPT_PATH, lane_receipt, "receipt_sha256")

    child["operational_state"] = "GERMINATED_TRANSLATION_AND_RECOVERY_VERIFIED_SCHEDULE_GATE_PENDING"
    child.setdefault("proof_gates", {})["stable_mechanism_translation"] = "PASSED_12_OF_12"
    child["proof_gates"]["controlled_recovery"] = "PASSED_TAMPER_REJECTION_AND_EXACT_RESTORATION"
    child.setdefault("tests", {})["translation_regression_suite"] = "PASSED_5_OF_5"
    child["tests"]["claim_inflation_rejection"] = "PASSED"
    child.setdefault("deployment_surfaces", {})["rooted_gate_workflow"] = ".github/workflows/nature-intelligence-rooted-gates.yml"
    child["deployment_surfaces"]["rooted_gate_proof_commit"] = PROOF_COMMIT
    child.setdefault("monitoring", {})["translation_path"] = "kimmie_seed/nature_intelligence/monitoring/latest_translation.json"
    child["monitoring"]["translation_sha256"] = translation["translation_sha256"]
    child["monitoring"]["translation_receipt_sha256"] = translation_receipt["receipt_sha256"]
    child["monitoring"]["recovery_receipt_sha256"] = recovery["receipt_sha256"]
    child["monitoring"]["rooted_gate_health_path"] = "kimmie_seed/nature_intelligence/monitoring/latest_rooted_gate_health.json"
    child["monitoring"]["rooted_gate_health_sha256"] = gate_health["health_sha256"]
    child["monitoring"]["rooted_gate_workflow_event"] = "push"
    child["monitoring"]["scheduled_cycles_verified"] = 0
    child["monitoring"]["persistent_monitoring"] = "AWAITING_FIRST_SCHEDULE_TRIGGERED_CYCLE"
    child["next_stage_gate"] = {
        "stage": "ROOTED",
        "repeated_acquisition_cycles": "VERIFIED_4_EXTERNAL_PUSH_TRIGGERED_CYCLES",
        "stable_translation_runtime": "VERIFIED_12_MECHANISMS",
        "controlled_recovery": "VERIFIED_TAMPER_REJECTION_AND_EXACT_RESTORATION",
        "persistent_schedule_triggered_monitoring": "NOT_YET_VERIFIED"
    }

    registry["registry_version"] = "1.14.0"
    registry["updated_at"] = observed_at
    registry["max_technical_capability"] = {
        "profile_id": max_profile["profile_id"],
        "version": max_profile["version"],
        "state": max_profile["state"],
        "profile_path": "evidenceops/runtime/MAX_TECHNICAL_CAPABILITY_KIMMIE.json",
        "profile_commit": PROFILE_COMMIT,
        "scope": max_profile["scope"],
        "authority_boundary": max_profile["authority_boundary"],
        "truth_boundary": max_profile["truth_boundary"]
    }
    registry["latest_review"] = {
        "checkpoint_path": "kimmie_seed/checkpoints/KSA-20260803-024.json",
        "checkpoint_sha256": checkpoint_sha,
        "lane_receipt_path": "evidenceops/innovation_engine/receipts/lane-watch-receipt-028.json",
        "lane_receipt_sha256": lane_receipt_sha,
        "proof_commit": PROOF_COMMIT,
        "root_promotion": "NONE",
        "child_promotion": "NONE",
        "material_change": True,
        "qualifying_notification_event": False,
        "notification": "MAX_TECHNICAL_ACTIVE_NATURE_ROOTED_GATES_PARTIAL_PASS"
    }
    registry["ipep_bible"] = {
        "receipt": "MAX-TECHNICAL CAPABILITY ACTIVATION AND NATURE ROOTED GATES 028",
        "revision_id": BIBLE_REVISION,
        "readback": "PASSED_EXACT_HEADING_AND_HASH",
        "heading_readback": BIBLE_HEADING_RANGE,
        "hash_readback": BIBLE_HASH_RANGE,
        "evidence_note_sha256": BIBLE_NOTE_SHA256
    }
    registry.setdefault("latest_cross_lane_review", {})["lane_watch_receipt_028"] = {
        "result": "MAX_TECHNICAL_ACTIVE_STABLE_TRANSLATION_AND_CONTROLLED_RECOVERY_VERIFIED_SCHEDULE_GATE_PENDING_NO_PROMOTION",
        "receipt_sha256": lane_receipt_sha
    }
    lessons = registry.setdefault("lesson_register", [])
    lesson_id = "KIMMIE-LESSON-20260803-006"
    if not any(item.get("lesson_id") == lesson_id for item in lessons):
        lessons.append({
            "lesson_id": lesson_id,
            "lesson": "A stable mechanism-translation runtime must preserve provenance, label outputs as candidates rather than deployed facts, reject claim inflation and prove exact deterministic restoration after controlled corruption.",
            "source_checkpoint": "KSA-20260803-024"
        })
    registry["truth_boundary"] = "KIMMIE-IPEP-001 remains SAPLING. Connector Foundry and Provenance Passport remain SAPLING. Nature Intelligence remains GERMINATED with repeated acquisition, stable deterministic translation and controlled recovery verified; ROOTED is withheld only pending an actual schedule-triggered monitoring cycle with durable readback. Audio Live Transcription remains SEED/BLOCKED. MAX-Technical Capability is active within connected authorised surfaces. Identity drift is not detected and no owner decision is required."

    REGISTRY_PATH.write_text(json.dumps(registry, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "RECONCILED", "registry_version": registry["registry_version"], "checkpoint_sha256": checkpoint_sha, "lane_receipt_sha256": lane_receipt_sha}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
