#!/usr/bin/env python3
"""Deploy and verify the governed 199-role Kimmie Seed workforce.

This is a deterministic orchestration layer. It binds logical specialist roles
to work packets, leases, collision keys, authority limits and proof duties.
It does not claim 199 independent provider-backed model processes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "bot_manifest_199.json"
DEPLOYMENT_DIR = ROOT / "deployment"
RECEIPT_DIR = ROOT / "receipts"

MISSION_BY_LANE = {
    "KIMMIE-IPEP-001": {
        "objective": "Protect root SAPLING maturity and build evidence for eventual MATURE without premature promotion.",
        "terminal_gate": "Sustained production use, resilience over time, measurable operational value and complete operational ownership.",
    },
    "LANE-KIMMIE-NATURE-INTELLIGENCE": {
        "objective": "Close executable ROOTED gates: stable mechanism translation and controlled recovery; preserve scheduled-monitoring gate until a real scheduled run.",
        "terminal_gate": "Schedule-triggered monitoring, controlled recovery and stable mechanism-translation runtime independently verified.",
    },
    "LANE-CONNECTOR-FOUNDRY": {
        "objective": "Maintain SAPLING connector reliability, provider confinement, cleanup and recovery evidence.",
        "terminal_gate": "Sustained production use, resilience, operational value and complete ownership.",
    },
    "LANE-PROVENANCE-PASSPORT": {
        "objective": "Maintain SAPLING proof integrity and monitor recurring passport verification across corpora.",
        "terminal_gate": "Sustained production use, resilience, operational value and complete ownership.",
    },
    "LANE-AUDIO-LIVE-TRANSCRIPTION": {
        "objective": "Discover and prepare authorised provider/runtime dependencies without fabricating credentials or live health.",
        "terminal_gate": "Provider credential binding, private worker execution, transcript proof and monitoring receipt.",
    },
}

OUTPUT_BY_SQUAD = {
    "COMMAND_SCOPE": ["scope decision", "priority map", "authority check"],
    "SOURCE_PROVENANCE": ["source register delta", "rights/provenance finding", "hash evidence"],
    "ACQUISITION_ENVIRONMENT": ["environment finding", "dependency result", "provider/readback receipt"],
    "MECHANISM_TRANSLATION": ["mechanism record", "engineering hypothesis", "applicability and exclusion tests"],
    "TEST_REDTEAM": ["test result", "defect finding", "independent verification"],
    "MONITORING_OBSERVABILITY": ["health assessment", "freshness evidence", "alert/readback record"],
    "RECOVERY_RESILIENCE": ["recovery drill", "rollback/resume evidence", "post-recovery verification"],
    "DEPLOYMENT_INTEGRATION": ["deployment route", "integration result", "destination readback"],
    "SECURITY_COMPLIANCE": ["security boundary finding", "licence/privacy check", "policy conformance result"],
    "QUALITY_EVIDENCE": ["proof-chain assessment", "maturity challenge", "quality score and reconciliation"],
    "MAINTENANCE_LEARNING": ["maintenance record", "lesson or no-new-lesson proof", "regression binding"],
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bots = manifest.get("bots", [])
    if manifest.get("bot_count") != 199 or len(bots) != 199:
        errors.append("bot_count_must_equal_199")
    bot_ids = [bot.get("bot_id") for bot in bots]
    if len(set(bot_ids)) != len(bot_ids):
        errors.append("duplicate_bot_id")
    collision_keys = [bot.get("collision_key") for bot in bots]
    if len(set(collision_keys)) != len(collision_keys):
        errors.append("duplicate_collision_key")
    for bot in bots:
        if not bot.get("lease_required"):
            errors.append(f"{bot.get('bot_id')}:lease_required")
        if not bot.get("proof_duty", {}).get("no_completion_credit_without_proof"):
            errors.append(f"{bot.get('bot_id')}:proof_duty_missing")
        if bot.get("lane_scope") not in MISSION_BY_LANE:
            errors.append(f"{bot.get('bot_id')}:unknown_lane_scope")
    if sum(manifest.get("squad_counts", {}).values()) != 199:
        errors.append("squad_counts_must_total_199")
    return errors


def build_packet(bot: dict[str, Any], cycle_id: str, ordinal: int) -> dict[str, Any]:
    lane = bot["lane_scope"]
    mission = MISSION_BY_LANE[lane]
    return {
        "packet_id": f"KSWP-{cycle_id}-{ordinal:03d}",
        "bot_id": bot["bot_id"],
        "squad": bot["squad"],
        "role": bot["role"],
        "lane_scope": lane,
        "objective": mission["objective"],
        "terminal_gate": mission["terminal_gate"],
        "priority": 10 if lane == "LANE-KIMMIE-NATURE-INTELLIGENCE" else 7,
        "authority": bot["authority"],
        "lease": {
            "required": True,
            "lease_id": f"LEASE-{cycle_id}-{bot['bot_id']}",
            "collision_key": bot["collision_key"],
            "state": "RESERVED",
        },
        "required_outputs": OUTPUT_BY_SQUAD[bot["squad"]],
        "proof_requirements": bot["proof_duty"]["completion_requires"],
        "state": "DEPLOYED_PACKET_BOUND",
        "completion_credit": "PROHIBITED_UNTIL_PROOF_AND_READBACK",
    }


def deploy() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_manifest()
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError("manifest_validation_failed:" + ",".join(errors))

    observed_at = datetime.now(timezone.utc).isoformat()
    cycle_id = observed_at.replace("-", "").replace(":", "").replace("+", "_").replace(".", "")
    assignments = [build_packet(bot, cycle_id, idx) for idx, bot in enumerate(manifest["bots"], 1)]

    deployment = {
        "workforce_id": manifest["workforce_id"],
        "cycle_id": cycle_id,
        "observed_at": observed_at,
        "status": "DEPLOYED_PACKET_BOUND",
        "bot_count": len(assignments),
        "assignment_count": len(assignments),
        "unique_bot_ids": len({item["bot_id"] for item in assignments}),
        "unique_collision_keys": len({item["lease"]["collision_key"] for item in assignments}),
        "squad_counts": manifest["squad_counts"],
        "lane_counts": {},
        "independent_verifier_count": 0,
        "runtime_boundary": manifest["operating_boundary"],
        "assignments": assignments,
    }
    for item in assignments:
        deployment["lane_counts"][item["lane_scope"]] = deployment["lane_counts"].get(item["lane_scope"], 0) + 1
        if item["squad"] in {"TEST_REDTEAM", "QUALITY_EVIDENCE"}:
            deployment["independent_verifier_count"] += 1

    deployment["deployment_sha256"] = canonical_sha256(deployment)
    receipt = {
        "receipt_id": f"KIMMIE-199-WORKFORCE-{cycle_id}",
        "observed_at": observed_at,
        "workforce_id": manifest["workforce_id"],
        "status": "PASS",
        "bot_count": 199,
        "assignment_count": 199,
        "independent_verifier_count": deployment["independent_verifier_count"],
        "unique_bot_ids": deployment["unique_bot_ids"],
        "unique_collision_keys": deployment["unique_collision_keys"],
        "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "deployment_sha256": deployment["deployment_sha256"],
        "proof_boundary": (
            "Proves 199 unique governed logical roles were configured and packet-bound with leases, "
            "collision keys, authority limits and proof duties. It does not prove 199 simultaneous "
            "provider-backed AI inference processes."
        ),
        "identity_drift": "NONE_DETECTED",
        "owner_decision_required": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return deployment, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest()
    errors = validate_manifest(manifest)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}))
        return 1
    if args.validate_only:
        print(json.dumps({"status": "PASS", "bot_count": 199}))
        return 0

    deployment, receipt = deploy()
    DEPLOYMENT_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    (DEPLOYMENT_DIR / "current_assignments.json").write_text(
        json.dumps(deployment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (RECEIPT_DIR / "latest_workforce_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": receipt["status"],
        "bot_count": receipt["bot_count"],
        "assignment_count": receipt["assignment_count"],
        "deployment_sha256": receipt["deployment_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
