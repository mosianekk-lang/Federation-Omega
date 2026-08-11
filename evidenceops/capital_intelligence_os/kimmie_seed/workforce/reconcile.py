#!/usr/bin/env python3
"""Bind the final stable Kimmie Seed 199-role workforce proof into canonical state."""

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

DEPLOYMENT_COMMIT = "7beb4bdfc95f6b92c08ffc14929593958c0c3797"
TRIGGER_REPAIR_COMMIT = "fbee376da48cd4f2068f86c69f7ba2b3888f3574"
BIBLE_REVISION = "AIroW34RKg6sTgbfenJZUXjwR2RU1e0KR-2xT4tbnh1tozIyIDkq1FTDfQ7PlDpcMgZtrEUZZlzFX67Die5aP-pgPIOIM8tCYpQL-neKiQo"
BIBLE_NOTE_SHA256 = "f0b8b8c51831b6d06b595f2fa5665d95bf4402b21834b97cd0012dc950ebca74"
BIBLE_HEADING_RANGE = {"start_index": 114912, "end_index": 114983, "tab_id": "t.0"}
BIBLE_HASH_RANGE = {"start_index": 117498, "end_index": 117562, "tab_id": "t.0"}
OBSERVED_AT = "2026-08-03T08:10:51+02:00"


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

    expected = {
        "status": "PASS",
        "workforce_id": "KIMMIE-SEED-199",
        "bot_count": 199,
        "assignment_count": 199,
        "unique_bot_ids": 199,
        "unique_collision_keys": 199,
        "independent_verifier_count": 48,
        "manifest_sha256": "298b0690a9e611057d5f2536d8108aa49027aad8777afc7aa9e01b089d994068",
        "deployment_sha256": "4c40def99c751f2a2d4298ca34f22027e84c77d09e5fc1af12e3a7abe7e05722",
        "receipt_sha256": "7c200bb7d817286363bb1812c061f8c99fc52e0f5961332696ced6aa7f6443a8",
        "receipt_id": "KIMMIE-199-WORKFORCE-20260803T061051145399_0000",
    }
    for key, value in expected.items():
        assert workforce[key] == value, f"{key}:{workforce[key]}!={value}"

    assert assignments["status"] == "DEPLOYED_PACKET_BOUND"
    assert assignments["assignment_count"] == 199
    assert assignments["deployment_sha256"] == workforce["deployment_sha256"]
    assert len(assignments["assignments"]) == 199
    assert len({item["bot_id"] for item in assignments["assignments"]}) == 199
    assert len({item["lease"]["collision_key"] for item in assignments["assignments"]}) == 199
    assert all(item["completion_credit"] == "PROHIBITED_UNTIL_PROOF_AND_READBACK" for item in assignments["assignments"])

    stages = {item["lane_id"]: item["verified_stage"] for item in registry["child_lanes"]}
    assert stages == {
        "LANE-CONNECTOR-FOUNDRY": "SAPLING",
        "LANE-PROVENANCE-PASSPORT": "SAPLING",
        "LANE-KIMMIE-NATURE-INTELLIGENCE": "GERMINATED",
        "LANE-AUDIO-LIVE-TRANSCRIPTION": "SEED",
    }

    checkpoint = {
        "checkpoint_id": "KSA-20260803-023",
        "observed_at": OBSERVED_AT,
        "seed_id": registry["seed_id"],
        "root_stage": registry["current_verified_stage"],
        "event": "KIMMIE_SEED_199_BOT_WORKFORCE_DEPLOYED_AND_RECONCILED",
        "workforce_id": workforce["workforce_id"],
        "deployment_commit": DEPLOYMENT_COMMIT,
        "trigger_repair_commit": TRIGGER_REPAIR_COMMIT,
        "workforce_receipt_id": workforce["receipt_id"],
        "workforce_receipt_sha256": workforce["receipt_sha256"],
        "manifest_sha256": workforce["manifest_sha256"],
        "deployment_sha256": workforce["deployment_sha256"],
        "bot_count": 199,
        "assignment_count": 199,
        "unique_bot_ids": 199,
        "unique_collision_keys": 199,
        "independent_verifier_count": 48,
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
        "observed_at": OBSERVED_AT,
        "event": "KIMMIE_SEED_199_BOT_WORKFORCE_DEPLOYED_AND_RECONCILED",
        "seed_id": registry["seed_id"],
        "workforce_id": workforce["workforce_id"],
        "deployment_commit": DEPLOYMENT_COMMIT,
        "trigger_repair_commit": TRIGGER_REPAIR_COMMIT,
        "workforce_receipt_path": "kimmie_seed/workforce/receipts/latest_workforce_receipt.json",
        "workforce_receipt_sha256": workforce["receipt_sha256"],
        "assignments_path": "kimmie_seed/workforce/deployment/current_assignments.json",
        "deployment_sha256": workforce["deployment_sha256"],
        "checkpoint_path": "kimmie_seed/checkpoints/KSA-20260803-023.json",
        "checkpoint_sha256": checkpoint_sha,
        "ipep_bible": {
            "receipt": "EVIDENCE NOTE — KIMMIE SEED 199-BOT WORKFORCE PROOF RECONCILIATION 027A",
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
    registry["updated_at"] = "2026-08-03T08:12:00+02:00"
    registry["workforce"] = {
        "workforce_id": workforce["workforce_id"],
        "state": "DEPLOYED_PACKET_BOUND",
        "external_workflow": ".github/workflows/kimmie-seed-199-bot-workforce.yml",
        "deployment_commit": DEPLOYMENT_COMMIT,
        "trigger_repair_commit": TRIGGER_REPAIR_COMMIT,
        "manifest_path": "kimmie_seed/workforce/bot_manifest_199.json",
        "manifest_sha256": workforce["manifest_sha256"],
        "assignments_path": "kimmie_seed/workforce/deployment/current_assignments.json",
        "deployment_sha256": workforce["deployment_sha256"],
        "receipt_path": "kimmie_seed/workforce/receipts/latest_workforce_receipt.json",
        "receipt_sha256": workforce["receipt_sha256"],
        "bot_count": 199,
        "assignment_count": 199,
        "unique_bot_ids": 199,
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
        "trigger_repair_commit": TRIGGER_REPAIR_COMMIT,
        "root_promotion": "NONE",
        "child_promotion": "NONE",
        "material_change": True,
        "qualifying_notification_event": False,
        "notification": "KIMMIE_199_BOT_WORKFORCE_DEPLOYED_AND_RECONCILED",
    }
    registry["ipep_bible"] = {
        "receipt": "KIMMIE SEED 199-BOT WORKFORCE PROOF RECONCILIATION 027A",
        "revision_id": BIBLE_REVISION,
        "readback": "PASSED_EXACT_HEADING_AND_HASH",
        "heading_readback": BIBLE_HEADING_RANGE,
        "hash_readback": BIBLE_HASH_RANGE,
        "evidence_note_sha256": BIBLE_NOTE_SHA256,
    }
    registry.setdefault("latest_cross_lane_review", {})["lane_watch_receipt_027"] = {
        "result": "KIMMIE_SEED_199_ROLE_WORKFORCE_EXTERNALLY_DEPLOYED_AND_PROOF_RECONCILED_NO_MATURITY_PROMOTION",
        "receipt_sha256": lane_receipt_sha,
    }

    lessons = registry.setdefault("lesson_register", [])
    lesson_rows = [
        {
            "lesson_id": "KIMMIE-LESSON-20260803-004",
            "lesson": "Large bot counts improve quality only when every role has a unique packet, bounded authority, lease, collision key, proof duty and independent verification path; role count alone is not execution evidence.",
            "source_checkpoint": "KSA-20260803-023",
        },
        {
            "lesson_id": "KIMMIE-LESSON-20260803-005",
            "lesson": "Generated proof and reconciliation outputs must be excluded from deployment trigger filters to prevent self-triggering cycles and stale canonical pointers.",
            "source_checkpoint": "KSA-20260803-023",
        },
    ]
    known = {item.get("lesson_id") for item in lessons}
    lessons.extend(item for item in lesson_rows if item["lesson_id"] not in known)

    registry["truth_boundary"] = (
        "KIMMIE-IPEP-001 remains SAPLING. Connector Foundry and Provenance Passport remain SAPLING. "
        "Nature Intelligence remains GERMINATED; its ROOTED gate still requires schedule-triggered monitoring, controlled recovery and stable mechanism translation. "
        "Audio Live Transcription remains SEED/BLOCKED. A 199-role governed workforce is externally deployed and packet-bound with 48 independent verifier roles. "
        "This proves logical role orchestration, not 199 simultaneous provider-backed model inference processes. Identity drift is not detected and no owner decision is required."
    )

    REGISTRY_PATH.write_text(json.dumps(registry, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
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
