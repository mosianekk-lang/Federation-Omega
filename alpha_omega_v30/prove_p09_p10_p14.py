from __future__ import annotations

import argparse
import json
from pathlib import Path

from .neuro_symbolic import NeuroSymbolicPlanner, PlanConstraints, PlanStep
from .product_discovery import ExperimentContract, ExperimentEvaluator, PainSignal, ProductDiscoveryEngine
from .progressive_delivery import FileRevisionProvider, ProgressiveDeliveryController


def build_proof(workspace: Path) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    provider = FileRevisionProvider(workspace / "delivery")
    controller = ProgressiveDeliveryController(provider)

    baseline = controller.release(
        {"service": "alpha-omega", "version": "1.0.0", "health": "ready"},
        lambda revision, percentage: revision.manifest["health"] == "ready",
    )
    if baseline["status"] != "PROMOTED":
        raise SystemExit("baseline promotion failed")
    candidate = controller.release(
        {"service": "alpha-omega", "version": "1.1.0", "health": "ready"},
        lambda revision, percentage: revision.manifest["health"] == "ready",
    )
    failed = controller.release(
        {"service": "alpha-omega", "version": "1.2.0", "health": "degraded"},
        lambda revision, percentage: percentage < 50,
    )
    if candidate["status"] != "PROMOTED" or failed["status"] != "ROLLED_BACK":
        raise SystemExit("progressive delivery proof failed")
    if not all(candidate[key] for key in ("readback_verified", "health_verified", "rollback_verified", "restoration_verified", "persistence_verified")):
        raise SystemExit("P09 proof gates failed")

    signals = [
        PainSignal("SIG-1", "ict-departments", "manual operational reporting", 12, 120000, 0.9, 0.8, "EVIDENCE-SYNTHETIC-1"),
        PainSignal("SIG-2", "ict-departments", "manual operational reporting", 10, 90000, 0.8, 0.7, "EVIDENCE-SYNTHETIC-2"),
        PainSignal("SIG-3", "legal-operations", "evidence reconciliation", 6, 180000, 0.95, 0.6, "EVIDENCE-SYNTHETIC-3"),
    ]
    hypotheses = ProductDiscoveryEngine().discover(signals)
    top = hypotheses[0]
    experiment = ExperimentEvaluator(workspace / "product_experiment_ledger.jsonl").evaluate(
        ExperimentContract("EXP-1", top.hypothesis_id, "qualified_interest", 0.5, 1000, True, "AUTOMATIC_SANDBOX"),
        observed_metric=0.8,
        actual_cost=0,
        evidence={"source": "synthetic", "hypothesis": top.hypothesis_id},
    )
    if not experiment["validated"] or experiment["market_proof"] != "EXTERNAL_EVIDENCE_REQUIRED":
        raise SystemExit("P10 engine proof failed")

    constraints = PlanConstraints(
        initial_facts=("tests_passed", "authority_valid"),
        required_outcomes=("release_verified",),
        forbidden_effects=("delete_last_good",),
        allowed_authorities=("AUTOMATIC",),
        max_cost=10,
        max_risk=0.5,
    )
    valid_plan = [
        PlanStep("snapshot", "create snapshot", preconditions=("tests_passed",), effects=("snapshot_exists",), cost=1, risk=0.05),
        PlanStep("deploy", "deploy candidate", dependencies=("snapshot",), preconditions=("snapshot_exists", "authority_valid"), effects=("candidate_deployed",), cost=3, risk=0.2),
        PlanStep("verify", "verify release", dependencies=("deploy",), preconditions=("candidate_deployed",), effects=("release_verified",), cost=1, risk=0.05),
    ]
    invalid_plan = [
        PlanStep("unsafe", "delete baseline", effects=("delete_last_good", "release_verified"), cost=0, risk=0.1)
    ]
    planning = NeuroSymbolicPlanner().select({"safe": valid_plan, "unsafe": invalid_plan}, constraints)
    if not planning["valid"] or planning["selected"]["candidate_id"] != "safe":
        raise SystemExit("P14 symbolic verification failed")

    receipt = {
        "programme_id": "AO-V30-SELF-VERIFYING-INSTITUTION",
        "phases": {
            "P09": {
                "status": "REFERENCE_PROVIDER_VERIFIED",
                "provider": "github-actions-artifact-state",
                "baseline": baseline,
                "candidate": candidate,
                "failed_candidate": failed,
                "cloud_run": "PROVIDER_BLOCKED_NO_FRESH_AUTHORITY",
            },
            "P10": {
                "status": "EXPERIMENT_ENGINE_VERIFIED_MARKET_PROOF_REQUIRED",
                "hypotheses": [item.__dict__ for item in hypotheses],
                "experiment": experiment,
            },
            "P14": {
                "status": "SYMBOLIC_CORE_VERIFIED",
                "planning": planning,
                "neural_generator": "UNBOUND_OPTIONAL_PROVIDER",
            },
        },
    }
    (workspace / "p09_p10_p14_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("p09_p10_p14_workspace"))
    args = parser.parse_args()
    print(json.dumps(build_proof(args.workspace), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
