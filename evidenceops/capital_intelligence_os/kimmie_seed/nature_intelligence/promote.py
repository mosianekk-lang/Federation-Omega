#!/usr/bin/env python3
"""Deterministically reconcile a verified Nature Intelligence germination event."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "kimmie_seed" / "registry.json"
HEALTH_PATH = REPO / "kimmie_seed" / "nature_intelligence" / "monitoring" / "latest_health.json"
ACQUISITION_RECEIPT_PATH = REPO / "kimmie_seed" / "nature_intelligence" / "receipts" / "latest_acquisition_receipt.json"
CHECKPOINT_PATH = REPO / "kimmie_seed" / "checkpoints" / "KSA-20260803-022.json"
LANE_RECEIPT_PATH = REPO / "evidenceops" / "innovation_engine" / "receipts" / "lane-watch-receipt-026.json"

PROOF_COMMIT = "2963edd9f5ee6213ff1d06622fd903cad4565d83"
BIBLE_REVISION = "AIroW36Jri7dyy9JjE25cy_E8DpCnL_cuu0LWwV7QU0XEgW-xxVnUgN2H6BIxWhI5JAfsDr74KetR5vNUpUxBaC_Rz1VWa4Y2-kWxX3YBqc"
BIBLE_NOTE_SHA256 = "0e5e00fac67dbfd2973a3e4c41bab22dfd80a5807f05bd2307f6c0810bdc93f0"
BIBLE_HEADING_RANGE = {"start_index": 107681, "end_index": 107752, "tab_id": "t.0"}
BIBLE_HASH_RANGE = {"start_index": 110150, "end_index": 110214, "tab_id": "t.0"}


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
    health = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
    acquisition = json.loads(ACQUISITION_RECEIPT_PATH.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    assert health["lane_id"] == "LANE-KIMMIE-NATURE-INTELLIGENCE"
    assert health["status"] == "PASS"
    assert health["germination_gate"] == "PASSED"
    assert health["sources_passed"] == health["sources_expected"] == 3
    assert health["full_text_persisted"] is False
    assert health["identity_drift"] == "NONE_DETECTED"
    assert acquisition["status"] == "PASS"
    assert acquisition["health_sha256"] == health["health_sha256"]
    assert acquisition["corpus_sha256"] == health["corpus_sha256"]

    child = next(item for item in registry["child_lanes"] if item["lane_id"] == health["lane_id"])
    if child.get("verified_stage") != "SEED":
        print(json.dumps({"status": "NO_STAGE_CHANGE", "verified_stage": child.get("verified_stage")}))
        return 0

    checkpoint = {
        "checkpoint_id": "KSA-20260803-022",
        "observed_at": "2026-08-03T07:23:00+02:00",
        "seed_id": registry["seed_id"],
        "root_stage": registry["current_verified_stage"],
        "child_lane": health["lane_id"],
        "transition": "SEED_TO_GERMINATED",
        "verified_stage": "GERMINATED",
        "proof_commit": PROOF_COMMIT,
        "health_sha256": health["health_sha256"],
        "acquisition_receipt_sha256": acquisition["receipt_sha256"],
        "corpus_sha256": health["corpus_sha256"],
        "sources_passed": health["sources_passed"],
        "full_text_persisted": False,
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
        "next_stage_gate": {
            "stage": "ROOTED",
            "repeated_acquisition_cycles": "NOT_YET_VERIFIED",
            "persistent_monitoring": "NOT_YET_VERIFIED",
            "controlled_recovery": "NOT_YET_VERIFIED",
            "stable_translation_runtime": "NOT_YET_VERIFIED"
        },
        "truth_boundary": "Germination proves one successful external acquisition and durable readback cycle. It does not prove repeated monitoring, recovery, useful mechanism translation, ROOTED, SPROUT or higher maturity."
    }
    checkpoint_sha = write_hashed(CHECKPOINT_PATH, checkpoint, "checkpoint_sha256")

    lane_receipt = {
        "receipt_id": "LANE-WATCH-RECEIPT-026",
        "observed_at": "2026-08-03T07:23:00+02:00",
        "lane_id": health["lane_id"],
        "transition": "SEED_TO_GERMINATED",
        "proof_commit": PROOF_COMMIT,
        "checkpoint_path": "kimmie_seed/checkpoints/KSA-20260803-022.json",
        "checkpoint_sha256": checkpoint_sha,
        "health_path": "kimmie_seed/nature_intelligence/monitoring/latest_health.json",
        "health_sha256": health["health_sha256"],
        "acquisition_receipt_path": "kimmie_seed/nature_intelligence/receipts/latest_acquisition_receipt.json",
        "acquisition_receipt_sha256": acquisition["receipt_sha256"],
        "ipep_bible": {
            "revision_id": BIBLE_REVISION,
            "heading_readback": BIBLE_HEADING_RANGE,
            "hash_readback": BIBLE_HASH_RANGE,
            "evidence_note_sha256": BIBLE_NOTE_SHA256
        },
        "root_promotion": "NONE",
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
        "status": "PASS"
    }
    lane_receipt_sha = write_hashed(LANE_RECEIPT_PATH, lane_receipt, "receipt_sha256")

    child.clear()
    child.update({
        "lane_id": health["lane_id"],
        "verified_stage": "GERMINATED",
        "operational_state": "ACQUISITION_PROOF_VERIFIED_SINGLE_EXTERNAL_CYCLE",
        "authorised_environment": {
            "github_repository": "VERIFIED_READ_WRITE",
            "public_source_acquisition": "VERIFIED_TRANSIENT_PROJECT_GUTENBERG_FETCH_3_OF_3"
        },
        "required_nutrients": {
            "source_manifest": "VERIFIED_PRESENT",
            "source_provenance": "VERIFIED_3_OF_3",
            "proof_receipt": "VERIFIED_PRESENT",
            "maintenance_owner": "mosianekk-lang"
        },
        "dependencies": {
            "python_standard_library": "VERIFIED",
            "github_actions": "VERIFIED_EXTERNAL_EXECUTION",
            "source_endpoints": "VERIFIED_3_OF_3_AT_OBSERVED_TIME"
        },
        "proof_gates": {
            "external_acquisition": "PASSED_3_OF_3",
            "source_marker_validation": "PASSED_3_OF_3",
            "cryptographic_hashing": "PASSED_3_OF_3",
            "bounded_signal_extraction": "PASSED",
            "durable_external_readback": "PASSED",
            "full_text_non_persistence": "PASSED"
        },
        "tests": {
            "regression_tests": "PASSED_BEFORE_ACQUISITION_COMMIT",
            "source_validations": "PASSED_3_OF_3",
            "health_status": "PASS"
        },
        "deployment_surfaces": {
            "github_workflow": ".github/workflows/nature-intelligence-acquisition.yml",
            "proof_commit": PROOF_COMMIT,
            "public_source_urls": "VERIFIED_TRANSIENT_ACCESS",
            "full_text_repository_storage": "DISABLED"
        },
        "monitoring": {
            "health_path": "kimmie_seed/nature_intelligence/monitoring/latest_health.json",
            "health_sha256": health["health_sha256"],
            "corpus_sha256": health["corpus_sha256"],
            "acquisition_receipt_sha256": acquisition["receipt_sha256"],
            "cycles_verified": 1,
            "persistent_monitoring": "NOT_YET_VERIFIED"
        },
        "maintenance_owner": "mosianekk-lang",
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
        "next_stage_gate": {
            "stage": "ROOTED",
            "repeated_acquisition_cycles": "NOT_YET_VERIFIED",
            "persistent_monitoring": "NOT_YET_VERIFIED",
            "controlled_recovery": "NOT_YET_VERIFIED",
            "stable_translation_runtime": "NOT_YET_VERIFIED"
        }
    })

    registry["registry_version"] = "1.12.0"
    registry["updated_at"] = "2026-08-03T07:24:00+02:00"
    registry["latest_review"] = {
        "checkpoint_path": "kimmie_seed/checkpoints/KSA-20260803-022.json",
        "checkpoint_sha256": checkpoint_sha,
        "source_proof_commit": PROOF_COMMIT,
        "lane_receipt_path": "evidenceops/innovation_engine/receipts/lane-watch-receipt-026.json",
        "lane_receipt_sha256": lane_receipt_sha,
        "root_promotion": "NONE",
        "child_promotion": "LANE-KIMMIE-NATURE-INTELLIGENCE:SEED_TO_GERMINATED",
        "material_change": True,
        "qualifying_notification_event": True,
        "notification": "NATURE_INTELLIGENCE_REACHED_GERMINATED"
    }
    registry["ipep_bible"] = {
        "receipt": "LANE WATCH RECEIPT 026 — NATURE INTELLIGENCE GERMINATED",
        "revision_id": BIBLE_REVISION,
        "readback": "PASSED_EXACT_HEADING_AND_HASH",
        "heading_readback": BIBLE_HEADING_RANGE,
        "hash_readback": BIBLE_HASH_RANGE,
        "evidence_note_sha256": BIBLE_NOTE_SHA256
    }
    registry.setdefault("latest_cross_lane_review", {})["lane_watch_receipt_026"] = {
        "result": "NATURE_INTELLIGENCE_EXTERNAL_ACQUISITION_VERIFIED_AND_CHILD_PROMOTED_TO_GERMINATED",
        "receipt_sha256": lane_receipt_sha
    }
    registry.setdefault("lesson_register", []).append({
        "lesson_id": "KIMMIE-LESSON-20260803-002",
        "lesson": "A nature corpus can germinate without public full-text persistence when transient authorised acquisition, source-marker validation, cryptographic hashing, bounded signal extraction and durable external readback all converge.",
        "source_checkpoint": "KSA-20260803-022"
    })
    registry["truth_boundary"] = (
        "KIMMIE-IPEP-001 remains SAPLING. Connector Foundry and Provenance Passport remain SAPLING. "
        "Nature Intelligence is GERMINATED after one verified external acquisition cycle. Audio Live Transcription remains SEED/BLOCKED. "
        "Nature Intelligence ROOTED is not inferred until repeated acquisition, persistent monitoring, controlled recovery and a stable translation runtime are verified. "
        "No MATURE or FEDERATED stage is inferred for the root."
    )

    REGISTRY_PATH.write_text(json.dumps(registry, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PROMOTED",
        "child_lane": health["lane_id"],
        "verified_stage": "GERMINATED",
        "checkpoint_sha256": checkpoint_sha,
        "lane_receipt_sha256": lane_receipt_sha
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
