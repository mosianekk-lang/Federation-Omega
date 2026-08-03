from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from mission_autonomy import MissionAutonomyEngine, MissionGoal, WorkUnit, digest
from runtime import utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    engine = MissionAutonomyEngine(MissionGoal("mission-proof", "close with proof", ("provider-proof",)))
    engine.decompose([
        WorkUnit("discover", "discover", required_receipts=("provider-proof",), priority=90),
        WorkUnit("analyse", "analyse", dependencies=("discover",), priority=80),
        WorkUnit("blocked-route", "blocked route", blocked=True),
    ])
    ready = engine.ready()
    selected = engine.optimise(2)
    engine.mark_verified("discover", {"provider-proof": {"run": "github-actions"}})
    after_discovery = engine.ready()
    engine.mark_verified("analyse", {})
    substitute = engine.substitute_blocked(
        "blocked-route",
        WorkUnit("alternate-route", "alternate route", substitute_for="blocked-route"),
    )
    engine.mark_verified("alternate-route", {"provider-proof": {"run": "github-actions"}})
    closure = engine.evaluate_closure()

    failure_engine = MissionAutonomyEngine(MissionGoal("mission-failure", "replan", ("proof",)))
    failure_engine.decompose([WorkUnit("primary", "primary", required_receipts=("proof",))])
    repair = failure_engine.replan_failed("primary", WorkUnit("repair-primary", "repair"))
    refused = failure_engine.evaluate_closure()

    gates = {
        "goal_decomposition": len(engine.plan.units) == 4,
        "dependency_scheduling": ready[0]["work_id"] == "discover" and after_discovery[0]["work_id"] == "analyse",
        "multi_workstream_optimisation": selected == ["discover"],
        "completion_contract_inheritance": "provider-proof" in substitute["required_receipts"] and "proof" in repair["required_receipts"],
        "blocked_path_substitution": engine.plan.units["blocked-route"]["status"] == "SUBSTITUTED",
        "dynamic_replanning": engine.plan.revision == 2 and failure_engine.plan.revision == 2,
        "proof_based_closure": closure["state"] == "PROOF_CLOSED",
        "false_closure_refusal": refused["state"] == "OPEN" and bool(refused["missing_receipts"]),
    }
    receipt = {
        "status": "END_TO_END_MISSION_AUTONOMY_VERIFIED" if all(gates.values()) else "END_TO_END_MISSION_AUTONOMY_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "closure": closure,
        "history_hash": digest(engine.history),
        "truth_boundary": {
            "github_actions_execution": True,
            "provider_neutral_mission_engine": True,
            "continuous_external_execution": False,
            "live_provider_actions": False,
            "owner_reserved_actions_bypassed": False,
        },
    }
    receipt["sha256"] = digest(receipt)
    (out / "sol-61-mission-autonomy-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "mission-closure-receipt.json").write_text(json.dumps(closure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
