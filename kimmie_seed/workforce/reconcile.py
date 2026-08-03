#!/usr/bin/env python3
"""Reconcile the verified Kimmie Seed 199-role workforce into canonical state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO / "kimmie_seed" / "registry.json"
WORKFORCE_RECEIPT_PATH = REPO / "kimmie_seed" / "workforce" / "receipts" / "latest_workforce_receipt.json"
ASSIGNMENTS_PATH = REPO / "kimmie_seed" / "workforce" / "deployment" / "current_assignments.json"
CHECKPOINT_PATH = REPO / "kimmie_seed" / "checkpoints" / "KSA-20260803-023.json"
LANE_RECEIPT_PATH = REPO / "evidenceops" / "innovation_engine" / "receipts" / "lane-watch-receipt-027.json"

DEPLOYMENT_COMMIT = "462546b11664e8d9395eee8c39ef8e62e5cd55d3"
BIBLE_REVISION = "AIroW37RZJT3qOIFhlaAq99q1XSKaV34WFPoUEA2oj0NGoIjlB4lxkNjULivRnO1lIoqtcE1-ucN2LLN87bXtJCaGpokPYwqaCvLwNaatLA"
BIBLE_NOTE_SHA256 = "32c3eeeed2ac32bc84e140dbb16d9855b09ee52a6b3e1be4dc2f1add278cbcaf"
BIBLE_HEADING_RANGE = {"start_index": 112748, "end_index": 112802, "tab_id": "t.0"}
BIBLE_HASH_RANGE = {"start_index": 114845, "end_index": 114909, "tab_id": "t.0"}


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
    workforce = json.loads(WORKFORCE_RECEIPT_PATH.read_text(encoding="utf-8"))
    assignments = json.loads(ASSIGNMENTS_PATH.read_text(encoding="utf-8"))

    assert registry["seed_id"] == "KIMMIE-IPEP-001"
    assert registry["current_verified_stage"] == "SAPLING"
    assert registry["identity_drift"] == "NONE_DETECTED"

    assert workforce["status"] == "PASS"
    assert workforce["workforce_id"] == "KIMMIE-SEED-199"
    assert workforce["bot_count"] == 199
    assert workforce["assignment_count"] == 199
    assert workforce["unique_bot_ids"] == 199
    assert workforce["unique_collision_keys"] == 199
    assert workforce["independent_verifier_count"] == 48
    assert assignments["status"] == "DEPLOYED_PACKET_BOUND"
    assert assignments["assignment_count"] == 199
    assert assignments["deployment_sha256"] == workforce["deployment_sha256"]

    stages = {item["lane_id"]: item["verified_stage"] for item in registry["child_lanes"]}
    assert stages["LANE-CONNECTOR-FOUNDRY"] == "SAPLING"
    assert stages["LANE-PROVENANCE-PASSPORT"] == "SAPLING"
    assert stages["LANE-KIMMIE-NATURE-INTELLIGENCE"] == "GERMINATED"
    assert stages["LANE-AUDIO-LIVE-TRANSCRIPTION"] == "SEED"

    checkpoint = {
        "checkpoint_id": "KSA-20260803-023",
        "observed_at": "2026-08-03T08:06:03+02:00",
        "seed_id": registry["seed_id"],
        "root_stage": registry["current_verified_stage"],
        "event": "KIMMIE_SEED_199_BOT_WORKFORCE_DEPLOYED",
        "workforce_id": workforce["workforce_id"],
        "deployment_commit": DEPLOYMENT_COMMIT,
        "workforce_receipt_id": workforce["receipt_id"],
        "workforce_receipt_sha256": workforce["receipt_sha256"],
        "manifest_sha256": workforce["manifest_sha256"],
        "deployment_sha256": workforce["deployment_sha256"],
        "bot_count": workforce["bot_count"],
        "assignment_count": workforce["assignment_count"],
        "unique_bot_ids": workforce["unique_bot_ids"],
        "unique_collision_keys": workforce["unique_collision_keys"],
        "independent_verifier_count": workforce["independent_verifier_count"],
        "authority_boundary": "A0_OR_REVERSIBLE_A1_ONLY",
        "root_promotion": "NONE",
        "child_promotion": "NONE",
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
        "truth_boundary": workforce["proof_boundary"],
    }
    checkpoint_sha = write_hashed(CHECKPOINT_PATH, checkpoint, "checkpoint_sha256")

    lane_receipt = {
        "receipt_id": "LANE-WATCH-RECEIPT-027",
        "observed_at": "2026-08-03T08:06:03+02:00",
        "event": "KIMMIE_SEED_199_BOT_WORKFORCE_DEPLOYED",
        "seed_id": registry["seed_id"],
        "workforce_id": workforce["workforce_id"],
        "deployment_commit": DEPLOYMENT_COMMIT,
        "workforce_receipt_path": "kimmie_seed/workforce/receipts/latest_workforce_receipt.json",
        "workforce_receipt_sha256": workforce["receipt_sha256"],
        "assignments_path": "kimmie_seed/workforce/deployment/current_assignments.json",
        "deployment_sha256": workforce["deployment_sha256"],
        "checkpoint_path": "kimmie_seed/checkpoints/KSA-20260803-023.json",
        "checkpoint_sha256": checkpoint_sha,
        "ipep_bible": {
            "receipt": "EVIDENCE NOTE — KIMMIE SEED 199-BOT WORKFORCE DEPLOYED",
            "revision_id": BIBLE_REVISION,
            "heading_readback": BIBLE_HEADING_RANGE,
            "hash_readback": BIBLE_HASH_RANGE,
            "evidence_note_sha256": BIBLE_NOTE_SHA256,
        },
        "root_promotion": "NONE",
        "child_promotion": "NONE",
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
        "status": "PASS",
    }
    lane_receipt_sha = write_hashed(LANE_RECEIPT_PATH, lane_receipt, "receipt_sha256")

    registry["registry_version"] = "1.13.0"
    registry["updated_at"] = "2026-08-03T08:08:00+02:00"
    registry["workforce"] = {
        "workforce_id": workforce["workforce_id"],
        "state": "DEPLOYED_PACKET_BOUND",
        "external_workflow": ".github/workflows/kimmie-seed-199-bot-workforce.yml",
        "deployment_commit": DEPLOYMENT_COMMIT,
        "manifest_path": "kimmie_seed/workforce/bot_manifest_199.json",
        "manifest_sha256": workforce["manifest_sha256"],
        "assignments_path": "kimmie_seed/workforce/deployment/current_assignments.json",
        "deployment_sha256": workforce["deployment_sha256"],
        "receipt_path": "kimmie_seed/workforce/receipts/latest_workforce_receipt.json",
        "receipt_sha256": workforce["receipt_sha256"],
        "bot_count": 199,
        "assignment_count": 199,
        "unique_collision_keys": 199,
        "independent_verifier_count": 48,
        "authority": "A0_OR_REVERSIBLE_A1_ONLY",
        "completion_credit": "PROHIBITED_UNTIL_PROOF_AND_READBACK",
        "runtime_boundary": "LOGICAL_PACKET_BOUND_ROLES_VERIFIED; 199_SIMULTANEOUS_PROVIDER_MODEL_PROCESSES_NOT_CLAIMED",
        "maintenance_owner": "mosianekk-lang",
    }
    registry["latest_review"] = {
        "checkpoint_path": "kimmie_seed/checkpoints/KSA-20260803-023.json",
        "checkpoint_sha256": checkpoint_sha,
        "lane_receipt_path": "evidenceops/innovation_engine/receipts/lane-watch-receipt-027.json",
        "lane_receipt_sha256": lane_receipt_sha,
        "deployment_commit": DEPLOYMENT_COMMIT,
        "root_promotion": "NONE",
        "child_promotion": "NONE",
        "material_change": True,
        "qualifying_notification_event": False,
        "notification": "KIMMIE_199_BOT_WORKFORCE_DEPLOYED",
    }
    registry["ipep_bible"] = {
        "receipt": "EVIDENCE NOTE — KIMMIE SEED 199-BOT WORKFORCE DEPLOYED",
        "revision_id": BIBLE_REVISION,
        "readback": "PASSED_EXACT_HEADING_AND_HASH",
        "heading_readback": BIBLE_HEADING_RANGE,
        "hash_readback": BIBLE_HASH_RANGE,
        "evidence_note_sha256": BIBLE_NOTE_SHA256,
    }
    registry.setdefault("latest_cross_lane_review", {})["lane_watch_receipt_027"] = {
        "result": "KIMMIE_SEED_199_ROLE_WORKFORCE_EXTERNALLY_DEPLOYED_PACKET_BOUND_NO_MATURITY_PROMOTION",
        "receipt_sha256": lane_receipt_sha,
    }

    lesson_id = "KIMMIE-LESSON-20260803-004"
    if not any(item.get("lesson_id") == lesson_id for item in registry.setdefault("lesson_register", [])):
        registry["lesson_register"].append({
            "lesson_id": lesson_id,
            "lesson": "Large bot counts improve quality only when every role has a unique packet, bounded authority, lease, collision key, proof duty and independent verification path; role count alone is not execution evidence.",
            "source_checkpoint": "KSA-20260803-023",
        })

    registry["truth_boundary"] = (
        "KIMMIE-IPEP-001 remains SAPLING. Connector Foundry and Provenance Passport remain SAPLING. "
        "Nature Intelligence remains GERMINATED; its ROOTED gate still requires schedule-triggered monitoring, controlled recovery and stable mechanism translation. "
        "Audio Live Transcription remains SEED/BLOCKED. A 199-role governed workforce is externally deployed and packet-bound with 48 independent verifier roles. "
        "This proves logical role orchestration, not 199 simultaneous provider-backed model inference processes. Identity drift is not detected and no owner decision is required."
    )

    REGISTRY_PATH.write_text(
        json.dumps(registry, separators=(",", ":"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": "RECONCILED",
        "registry_version": registry["registry_version"],
        "checkpoint_sha256": checkpoint_sha,
        "lane_receipt_sha256": lane_receipt_sha,
        "workforce_receipt_sha256": workforce["receipt_sha256"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
