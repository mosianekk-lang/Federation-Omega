#!/usr/bin/env python3
"""Reconcile Nature Intelligence maturity event 026 to immutable proof snapshots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "kimmie_seed" / "registry.json"
CHECKPOINT_PATH = REPO / "kimmie_seed" / "checkpoints" / "KSA-20260803-022.json"
LANE_RECEIPT_PATH = REPO / "evidenceops" / "innovation_engine" / "receipts" / "lane-watch-receipt-026.json"
HEALTH_SNAPSHOT_PATH = REPO / "kimmie_seed" / "nature_intelligence" / "monitoring" / "cycles" / "NATURE-ACQ-20260803T052836-health.json"
ACQUISITION_SNAPSHOT_PATH = REPO / "kimmie_seed" / "nature_intelligence" / "receipts" / "archive" / "NATURE-ACQ-20260803T052836.json"

FINAL_ACQUISITION_COMMIT = "208865474a01789b90da21612fd0e528503c5445"
HEALTH_SNAPSHOT_COMMIT = "3d8c232bf4189d29f9f900db87ecab5f18d1b145"
RECEIPT_SNAPSHOT_COMMIT = "d1806896f4c47d0b32abb64629a3d17bdfb6f15a"
BIBLE_REVISION = "AIroW366s9nR4bblJU9WigyCiYCcOZqrrha-1RTgOiuJ0_7heKzXVm7QOQGDUjiUlLQzo5B1Q90ZsF0tsBaV-65VdPoCU7k-9tozey3-Jzg"
BIBLE_NOTE_SHA256 = "5a3741e317d71eb553594f3ae321400a0ea81ded2ecdcecd663e541c43c30ebb"
BIBLE_HEADING_RANGE = {"start_index": 110217, "end_index": 110278, "tab_id": "t.0"}
BIBLE_HASH_RANGE = {"start_index": 112681, "end_index": 112745, "tab_id": "t.0"}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_hashed(path: Path, payload: dict[str, Any], field: str) -> str:
    payload.pop(field, None)
    digest = canonical_sha256(payload)
    payload[field] = digest
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return digest


def main() -> int:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    lane_receipt = json.loads(LANE_RECEIPT_PATH.read_text(encoding="utf-8"))
    health = json.loads(HEALTH_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    acquisition = json.loads(ACQUISITION_SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert registry["current_verified_stage"] == "SAPLING"
    assert registry["identity_drift"] == "NONE_DETECTED"
    child = next(item for item in registry["child_lanes"] if item["lane_id"] == "LANE-KIMMIE-NATURE-INTELLIGENCE")
    assert child["verified_stage"] == "GERMINATED"
    assert health["status"] == "PASS"
    assert health["germination_gate"] == "PASSED"
    assert health["sources_passed"] == health["sources_expected"] == 3
    assert health["full_text_persisted"] is False
    assert acquisition["status"] == "PASS"
    assert acquisition["health_sha256"] == health["health_sha256"]
    assert acquisition["corpus_sha256"] == health["corpus_sha256"]

    health_rel = "kimmie_seed/nature_intelligence/monitoring/cycles/NATURE-ACQ-20260803T052836-health.json"
    acquisition_rel = "kimmie_seed/nature_intelligence/receipts/archive/NATURE-ACQ-20260803T052836.json"

    checkpoint.update({
        "observed_at": "2026-08-03T07:29:00+02:00",
        "proof_commit": FINAL_ACQUISITION_COMMIT,
        "snapshot_commit": RECEIPT_SNAPSHOT_COMMIT,
        "health_snapshot_path": health_rel,
        "health_snapshot_commit": HEALTH_SNAPSHOT_COMMIT,
        "health_sha256": health["health_sha256"],
        "acquisition_receipt_snapshot_path": acquisition_rel,
        "acquisition_receipt_snapshot_commit": RECEIPT_SNAPSHOT_COMMIT,
        "acquisition_receipt_sha256": acquisition["receipt_sha256"],
        "corpus_sha256": health["corpus_sha256"],
        "sources_passed": 3,
        "external_acquisition_cycles_verified": 4,
        "integrity_reconciliation": "IMMUTABLE_EVENT_SNAPSHOTS_BOUND",
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
        "next_stage_gate": {
            "stage": "ROOTED",
            "repeated_acquisition_cycles": "VERIFIED_4_EXTERNAL_PUSH_TRIGGERED_CYCLES",
            "persistent_schedule_triggered_monitoring": "NOT_YET_VERIFIED",
            "controlled_recovery": "NOT_YET_VERIFIED",
            "stable_translation_runtime": "NOT_YET_VERIFIED"
        },
        "truth_boundary": "GERMINATED remains verified. Four external push-triggered acquisition cycles establish repetition, but ROOTED is not passed without schedule-triggered monitoring, controlled recovery and a stable mechanism-translation runtime."
    })
    checkpoint_sha = write_hashed(CHECKPOINT_PATH, checkpoint, "checkpoint_sha256")

    lane_receipt.update({
        "observed_at": "2026-08-03T07:29:00+02:00",
        "proof_commit": FINAL_ACQUISITION_COMMIT,
        "snapshot_commit": RECEIPT_SNAPSHOT_COMMIT,
        "checkpoint_sha256": checkpoint_sha,
        "health_path": health_rel,
        "health_snapshot_commit": HEALTH_SNAPSHOT_COMMIT,
        "health_sha256": health["health_sha256"],
        "acquisition_receipt_path": acquisition_rel,
        "acquisition_receipt_snapshot_commit": RECEIPT_SNAPSHOT_COMMIT,
        "acquisition_receipt_sha256": acquisition["receipt_sha256"],
        "external_acquisition_cycles_verified": 4,
        "integrity_reconciliation": "026A_IMMUTABLE_POINTERS_VERIFIED",
        "ipep_bible": {
            "correction_receipt": "KIMMIE SEED PROOF POINTER RECONCILIATION 026A",
            "revision_id": BIBLE_REVISION,
            "heading_readback": BIBLE_HEADING_RANGE,
            "hash_readback": BIBLE_HASH_RANGE,
            "evidence_note_sha256": BIBLE_NOTE_SHA256
        },
        "root_promotion": "NONE",
        "status": "PASS",
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False
    })
    lane_receipt_sha = write_hashed(LANE_RECEIPT_PATH, lane_receipt, "receipt_sha256")

    child["operational_state"] = "GERMINATED_REPEATED_EXTERNAL_ACQUISITION_IMMUTABLE_PROOF_BOUND"
    child["proof_gates"].update({
        "repeated_external_acquisition": "PASSED_4_PUSH_TRIGGERED_CYCLES",
        "immutable_event_snapshot": "PASSED",
        "proof_pointer_reconciliation": "PASSED"
    })
    child["monitoring"] = {
        "mutable_latest_health_path": "kimmie_seed/nature_intelligence/monitoring/latest_health.json",
        "immutable_health_snapshot_path": health_rel,
        "immutable_health_snapshot_commit": HEALTH_SNAPSHOT_COMMIT,
        "health_sha256": health["health_sha256"],
        "immutable_acquisition_receipt_path": acquisition_rel,
        "immutable_acquisition_receipt_snapshot_commit": RECEIPT_SNAPSHOT_COMMIT,
        "acquisition_receipt_sha256": acquisition["receipt_sha256"],
        "corpus_sha256": health["corpus_sha256"],
        "external_cycles_verified": 4,
        "scheduled_cycles_verified": 0,
        "persistent_monitoring": "NOT_YET_VERIFIED"
    }
    child["next_stage_gate"] = {
        "stage": "ROOTED",
        "repeated_acquisition_cycles": "VERIFIED_4_EXTERNAL_PUSH_TRIGGERED_CYCLES",
        "persistent_schedule_triggered_monitoring": "NOT_YET_VERIFIED",
        "controlled_recovery": "NOT_YET_VERIFIED",
        "stable_translation_runtime": "NOT_YET_VERIFIED"
    }

    registry["registry_version"] = "1.12.1"
    registry["updated_at"] = "2026-08-03T07:30:00+02:00"
    registry["latest_review"] = {
        "checkpoint_path": "kimmie_seed/checkpoints/KSA-20260803-022.json",
        "checkpoint_sha256": checkpoint_sha,
        "final_acquisition_commit": FINAL_ACQUISITION_COMMIT,
        "immutable_health_snapshot_path": health_rel,
        "immutable_health_snapshot_commit": HEALTH_SNAPSHOT_COMMIT,
        "immutable_acquisition_receipt_path": acquisition_rel,
        "immutable_acquisition_receipt_snapshot_commit": RECEIPT_SNAPSHOT_COMMIT,
        "lane_receipt_path": "evidenceops/innovation_engine/receipts/lane-watch-receipt-026.json",
        "lane_receipt_sha256": lane_receipt_sha,
        "root_promotion": "NONE",
        "child_promotion": "LANE-KIMMIE-NATURE-INTELLIGENCE:SEED_TO_GERMINATED_RETAINED",
        "integrity_reconciliation": "026A_COMPLETED",
        "material_change": True,
        "qualifying_notification_event": True,
        "notification": "NATURE_INTELLIGENCE_GERMINATED_PROOF_RECONCILED"
    }
    registry["ipep_bible"] = {
        "receipt": "KIMMIE SEED PROOF POINTER RECONCILIATION 026A",
        "revision_id": BIBLE_REVISION,
        "readback": "PASSED_EXACT_HEADING_AND_HASH",
        "heading_readback": BIBLE_HEADING_RANGE,
        "hash_readback": BIBLE_HASH_RANGE,
        "evidence_note_sha256": BIBLE_NOTE_SHA256
    }
    registry.setdefault("latest_cross_lane_review", {})["lane_watch_receipt_026a"] = {
        "result": "NATURE_INTELLIGENCE_GERMINATION_PROOF_REBOUND_TO_IMMUTABLE_EVENT_SNAPSHOTS",
        "receipt_sha256": lane_receipt_sha
    }
    registry.setdefault("lesson_register", []).append({
        "lesson_id": "KIMMIE-LESSON-20260803-003",
        "lesson": "Maturity receipts must bind immutable event snapshots; mutable latest-state files remain monitoring surfaces and cannot serve as permanent evidence anchors.",
        "source_checkpoint": "KSA-20260803-022"
    })
    registry["truth_boundary"] = (
        "KIMMIE-IPEP-001 remains SAPLING. Connector Foundry and Provenance Passport remain SAPLING. "
        "Nature Intelligence remains GERMINATED with immutable event proof and four verified external push-triggered acquisition cycles. "
        "ROOTED is withheld pending at least one schedule-triggered monitoring cycle, controlled recovery and a stable mechanism-translation runtime. "
        "Audio Live Transcription remains SEED/BLOCKED. Identity drift is not detected and no owner decision is required."
    )
    REGISTRY_PATH.write_text(json.dumps(registry, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "RECONCILED",
        "verified_stage": "GERMINATED",
        "registry_version": registry["registry_version"],
        "checkpoint_sha256": checkpoint_sha,
        "lane_receipt_sha256": lane_receipt_sha,
        "health_sha256": health["health_sha256"],
        "acquisition_receipt_sha256": acquisition["receipt_sha256"]
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
