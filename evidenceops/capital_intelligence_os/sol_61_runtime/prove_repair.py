from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from repair import AutonomousRepairFabric, RepairCandidate, digest
from runtime import utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    fabric = AutonomousRepairFabric(recurrence_threshold=3)
    candidate = RepairCandidate(
        repair_id="repair-transient-backoff",
        incident_class="TRANSIENT",
        change_set=("increase-backoff", "add-jitter"),
        expected_effects={"error_rate": 0.20, "success_rate": 0.10},
        rollback_steps=("restore-backoff", "remove-jitter"),
    )

    recurrence = [fabric.record_failure("TRANSIENT", "provider-503") for _ in range(3)][-1]
    ranked = fabric.synthesise("TRANSIENT", "provider-503", [candidate])
    shadow = fabric.shadow_execute(candidate, lambda _: {"passed": True, "error_rate": 0.01})
    differential = fabric.differential_validate(
        {"latency_ms": 100.0, "cost": 1.0},
        {"latency_ms": 102.0, "cost": 1.01},
        {"latency_ms": 5.0, "cost": 0.05},
    )
    rollback = fabric.rehearse_rollback(candidate, lambda steps: len(steps) == 2)
    canary = fabric.canary_validate(
        {"error_rate": 0.01, "success_rate": 0.995},
        {"error_rate": ("LTE", 0.05), "success_rate": ("GTE", 0.98)},
    )
    receipt = fabric.evaluate_promotion(
        candidate,
        shadow=shadow,
        differential=differential,
        rollback=rollback,
        canary=canary,
        proposer="planner",
        executor="worker",
        certifier="auditor",
    )
    promotion = fabric.promote(candidate, receipt)

    controller = RepairCandidate(
        repair_id="controller-policy-change",
        incident_class="LOGIC",
        change_set=("change-controller-policy",),
        expected_effects={"reliability": 0.1},
        rollback_steps=("restore-controller-policy",),
        risk="HIGH",
        controller_change=True,
    )
    controller_denied = fabric.evaluate_promotion(
        controller,
        shadow=shadow,
        differential=differential,
        rollback=rollback,
        canary=canary,
        proposer="planner",
        executor="worker",
        certifier="auditor",
    )

    gates = {
        "recurrence_detection": recurrence["recurrent"],
        "repair_plan_synthesis": ranked[0].repair_id == candidate.repair_id,
        "shadow_execution": shadow["passed"] and not shadow["mutated_live_state"],
        "differential_validation": differential["passed"],
        "rollback_rehearsal": rollback["passed"],
        "canary_validation": canary["passed"],
        "proof_carrying_promotion": receipt.state == "PROMOTION_ELIGIBLE" and promotion["state"] == "PROMOTED",
        "controller_self_modification_guard": controller_denied.state == "PROMOTION_DENIED",
    }
    result = {
        "status": "AUTONOMOUS_REPAIR_RECOVERY_VERIFIED" if all(gates.values()) else "AUTONOMOUS_REPAIR_RECOVERY_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "promotion": promotion,
        "truth_boundary": {
            "github_actions_execution": True,
            "provider_neutral_repair_fabric": True,
            "live_provider_repair_execution": False,
            "continuous_autonomous_repair": False,
            "controller_self_modification_without_owner": False,
        },
    }
    result["sha256"] = digest(result)
    (out / "sol-61-repair-receipt.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "promotion-receipt.json").write_text(json.dumps(promotion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
