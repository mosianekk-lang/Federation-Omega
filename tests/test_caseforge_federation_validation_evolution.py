from __future__ import annotations

import unittest

from evidenceops.caseforge.federation_validation import FederationEvaluationContract
from evidenceops.caseforge.federation_validation_evolution import to_evolution_governor_metrics
from evidenceops.innovation_engine.evolution import EvolutionGovernor


class FederationEvaluationEvolutionBridgeTests(unittest.TestCase):
    def test_bridge_matches_existing_evolution_governor_contract(self) -> None:
        contract = FederationEvaluationContract(
            component_id="CASEFORGE-CONTINUITY",
            mission="test continuity",
            hypothesis="recovery is faithful",
            baseline_ref="BASE",
            metrics={
                "canonical_state_accuracy": 0.95,
                "provenance_fidelity": 0.90,
                "stale_memory_rejection": 1.0,
                "context_recovery": 0.92,
                "contradiction_detection": 0.85,
            },
        ).validate()
        metrics = to_evolution_governor_metrics(
            contract,
            reuse=0.8,
            owner_burden_reduction=0.7,
            cost_efficiency=0.75,
        )
        self.assertEqual(set(EvolutionGovernor.default_weights), set(metrics))
        self.assertEqual(0.95, metrics["factual_accuracy"])
        self.assertEqual(0.90, metrics["proof_completeness"])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in metrics.values()))

    def test_security_penalty_is_fail_closed_for_authority_failure(self) -> None:
        contract = FederationEvaluationContract(
            component_id="CASEFORGE-CAPABILITY",
            mission="test capability",
            hypothesis="capability is verified",
            baseline_ref="BASE",
            metrics={"semantic_correctness": 1.0, "provider_readback": 1.0},
            failure_fingerprints=("CAPABILITY_DEGRADED:cloud:AUTHORITY",),
        ).validate()
        metrics = to_evolution_governor_metrics(
            contract,
            reuse=1.0,
            owner_burden_reduction=1.0,
            cost_efficiency=1.0,
        )
        self.assertEqual(0.0, metrics["security"])


if __name__ == "__main__":
    unittest.main()
