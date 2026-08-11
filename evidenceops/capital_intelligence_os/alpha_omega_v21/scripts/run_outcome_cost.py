from __future__ import annotations

import argparse
import json
from pathlib import Path

from alpha_omega_foundry.outcomes import OutcomeCostGovernor


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="./outcome_cost_workspace")
    args = parser.parse_args()

    governor = OutcomeCostGovernor(Path(args.workspace))
    outcome = governor.verify_outcomes(
        {"availability": 0.99, "completion_rate": 0.9, "proof_quality": 0.95},
        {"availability": 1.0, "completion_rate": 0.96, "proof_quality": 1.0},
    )
    goodhart = governor.goodhart_check(
        {"mission_outcome": outcome["pass"]},
        {"quality_preserved": True, "safety_preserved": True, "truth_boundary_preserved": True},
    )
    cost = governor.evaluate_cost(
        {"compute": 20, "storage": 5, "owner_attention": 1},
        {"compute": 30, "storage": 10, "owner_attention": 4},
    )
    value = governor.value_score(outcome["score"], 1.0, 0.9, 0.1)
    decision = governor.decide(outcome, goodhart, cost, value)
    receipt = governor.record("ALPHA-OMEGA-FOUNDRY-V23", outcome, goodhart, cost, value, decision)
    output = Path(args.workspace) / "outcome_cost_receipt.json"
    output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
