from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from causal import CausalDecisionEngine, CausalEdge, Intervention
from runtime import digest, utc_now


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    engine = CausalDecisionEngine()
    engine.add_edge(CausalEdge("quota_exhaustion", "provider_errors", 0.9, 0.95, ("provider-receipt",)))
    engine.add_edge(CausalEdge("provider_errors", "job_failures", 0.8, 0.9, ("runtime-receipt",)))
    engine.add_intervention(Intervention("retry-jobs", "job_failures", 0.2, 0.05, 0.45, 1.0))
    engine.add_intervention(Intervention("failover-provider", "quota_exhaustion", 0.85, 0.25, 0.15, 0.95))
    engine.register_hypothesis("quota_root", 0.5)

    ranked = engine.rank_interventions("job_failures")
    posterior = engine.update_hypothesis("quota_root", 0.9, 0.2)
    counterfactual = engine.counterfactual("failover-provider", 100)
    measurement = engine.measure_effect("failover-provider", 100, 12)

    gates = {
        "causal_graph": engine.upstream_causes("job_failures") == {"provider_errors", "quota_exhaustion"},
        "symptom_fix_rejected": engine.is_symptom_only("retry-jobs", "job_failures"),
        "root_intervention_ranked_first": ranked[0]["intervention"]["intervention_id"] == "failover-provider",
        "hypothesis_confidence_updated": posterior > 0.8,
        "counterfactual_planning": counterfactual["predicted_after"] < 20,
        "repair_effect_measured": measurement["effective"] and measurement["actual_effect"] > 0.8,
    }
    receipt = {
        "status": "CAUSAL_DECISION_INTELLIGENCE_VERIFIED" if all(gates.values()) else "CAUSAL_DECISION_INTELLIGENCE_FAILED",
        "generated_at": utc_now(),
        "gates": gates,
        "ranked_interventions": ranked,
        "posterior": posterior,
        "counterfactual": counterfactual,
        "measurement": measurement,
        "truth_boundary": {
            "github_actions_execution": True,
            "provider_neutral_causal_model": True,
            "live_intervention_execution": False,
            "automatic_real_world_causality_proven": False,
        },
    }
    receipt["sha256"] = digest(receipt)
    (out / "sol-61-causal-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(gates.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
