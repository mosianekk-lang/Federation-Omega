from __future__ import annotations

import unittest

from .cognitive_precision import CognitivePrecisionKernel


class CognitivePrecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kernel = CognitivePrecisionKernel()

    def test_contradicted_attractive_route_is_downgraded(self) -> None:
        ranked = self.kernel.rank_routes([
            {"route_id": "A", "support": 0.95, "contradiction": 0.85, "evidence_quality": 0.90, "information_gain": 0.80, "decision_impact": 0.90},
            {"route_id": "B", "support": 0.78, "contradiction": 0.08, "evidence_quality": 0.85, "information_gain": 0.70, "decision_impact": 0.85},
        ])
        self.assertEqual(ranked[0].route_id, "B")

    def test_high_information_reversible_test_wins(self) -> None:
        result = self.kernel.select_next_test([
            {"experiment_id": "EXPENSIVE", "expected_information_gain": 0.90, "decision_sensitivity": 0.90, "resolution_probability": 0.80, "reversibility": 0.80, "cost": 0.90, "time": 0.80, "risk": 0.40, "owner_attention": 0.40},
            {"experiment_id": "CHEAP", "expected_information_gain": 0.75, "decision_sensitivity": 0.90, "resolution_probability": 0.90, "reversibility": 1.00, "cost": 0.10, "time": 0.10, "risk": 0.05, "owner_attention": 0.05},
        ])
        selected = result["output"]["selected_experiment"]
        self.assertEqual(selected["experiment_id"], "CHEAP")

    def test_open_high_severity_falsifier_blocks_convergence(self) -> None:
        decision = self.kernel.compile_decision(candidates=[{
            "route_id": "X", "support": 0.95, "contradiction": 0.02, "evidence_quality": 0.95,
            "decision_impact": 0.95, "information_gain": 0.90, "replication": 0.90, "independence": 0.90,
            "falsifiers": [{"description": "Primary record contradicts X", "severity": "HIGH", "resolved": False}],
        }])
        self.assertEqual(decision["convergence"]["state"], "HOLD_FOR_HIGH_INFORMATION_TEST")
        self.assertIsNone(decision["selected_route"])

    def test_shared_dependency_single_point_is_detected(self) -> None:
        decision = self.kernel.compile_decision(candidates=[
            {"route_id": "A", "support": 0.80, "evidence_quality": 0.80, "dependencies": ["SRC1", "ASSUMPTION"]},
            {"route_id": "B", "support": 0.75, "evidence_quality": 0.75, "dependencies": ["SRC2", "ASSUMPTION"]},
            {"route_id": "C", "support": 0.70, "evidence_quality": 0.70, "dependencies": ["SRC3", "ASSUMPTION"]},
        ])
        self.assertIn("ASSUMPTION", decision["dependency_risk"]["universal_single_points"])

    def test_overload_requires_checkpoint_and_compression(self) -> None:
        load = self.kernel.cognitive_load({
            "path_count": 12, "contradiction_count": 9, "stale_fact_count": 7,
            "owner_corrections": 3, "retrievals": 18, "unresolved_dependencies": 7,
        })
        self.assertEqual(load["state"], "CHECKPOINT_AND_COMPRESS")

    def test_strong_stable_route_can_converge(self) -> None:
        decision = self.kernel.compile_decision(candidates=[
            {
                "route_id": "STRONG", "support": 0.95, "contradiction": 0.01, "evidence_quality": 0.95,
                "information_gain": 0.85, "decision_impact": 0.95, "reversibility": 0.90,
                "dependency_diversity": 0.90, "owner_burden": 0.05, "latency": 0.05, "risk": 0.05,
                "replication": 0.90, "independence": 0.90,
                "scenario_scores": {"base": 0.90, "adverse": 0.84, "supportive": 0.94},
            },
            {"route_id": "WEAK", "support": 0.45, "contradiction": 0.20, "evidence_quality": 0.50, "information_gain": 0.40, "decision_impact": 0.50, "risk": 0.30, "owner_burden": 0.30},
        ])
        self.assertEqual(decision["convergence"]["state"], "READY_TO_ACT_WITHIN_AUTHORITY")
        self.assertEqual(decision["selected_route"], "STRONG")


if __name__ == "__main__":
    unittest.main()
