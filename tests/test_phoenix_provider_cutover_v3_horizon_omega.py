import unittest

from ao_harmonic_v3.horizon import HorizonOmega


class HorizonOmegaTests(unittest.TestCase):
    def setUp(self):
        self.engine = HorizonOmega()

    def test_consequential_floor_is_ten(self):
        depth = self.engine.adaptive_depth(
            consequential=True,
            consequence=0.0,
            uncertainty=0.0,
            dependency_density=0.0,
            adversarial_complexity=0.0,
        )
        self.assertGreaterEqual(depth, 10)

    def test_depth_extends_beyond_legacy_ten(self):
        depth = self.engine.adaptive_depth(
            consequential=True,
            consequence=1.0,
            uncertainty=1.0,
            dependency_density=1.0,
            adversarial_complexity=1.0,
        )
        self.assertGreater(depth, 10)
        self.assertLessEqual(depth, self.engine.MAX_DEPTH)

    def test_simulation_has_required_core_lanes(self):
        run = self.engine.simulate(
            objective="Protect the mission while preserving options",
            profile="TEST",
            consequential=True,
            evidence_dependencies=["primary record"],
            cross_lane_risks=["waiver", "remedy loss"],
        )
        kinds = [node.kind for node in run.nodes[:10]]
        self.assertEqual(kinds, [
            "OBJECTIVE",
            "GATE",
            "MOST_LIKELY_RESPONSE",
            "STRONGEST_PIVOT",
            "DECISION_MAKER_TWIN",
            "EVIDENCE_AHEAD",
            "COLLATERAL_EFFECTS",
            "COUNTERMOVE",
            "WORST_CASE_RECOVERY",
            "PIVOT_TRIGGER",
        ])
        self.assertEqual(run.truth_class, "SIMULATION_HYPOTHESIS")

    def test_route_failure_stays_internal_when_alternative_exists(self):
        self.assertFalse(self.engine.should_surface_route_failure(
            objective_exhausted=False,
            owner_only=False,
            material_strategy_change=False,
        ))

    def test_route_failure_surfaces_only_at_objective_or_owner_boundary(self):
        self.assertTrue(self.engine.should_surface_route_failure(objective_exhausted=True))
        self.assertTrue(self.engine.should_surface_route_failure(objective_exhausted=False, owner_only=True))
        self.assertTrue(self.engine.should_surface_route_failure(
            objective_exhausted=False,
            material_strategy_change=True,
        ))

    def test_reroute_prefers_strong_proof_and_low_owner_burden(self):
        route = self.engine.reroute([
            {
                "name": "route-a",
                "available": True,
                "authorised": True,
                "proof_strength": 0.5,
                "reversibility": 0.8,
                "information_gain": 0.7,
                "owner_burden": 0.2,
            },
            {
                "name": "route-b",
                "available": True,
                "authorised": True,
                "proof_strength": 0.95,
                "reversibility": 0.9,
                "information_gain": 0.8,
                "owner_burden": 0.05,
            },
        ])
        self.assertEqual(route["name"], "route-b")

    def test_requested_depth_cannot_reduce_consequential_floor(self):
        depth = self.engine.adaptive_depth(
            consequential=True,
            requested_depth=3,
            consequence=0.0,
            uncertainty=0.0,
            dependency_density=0.0,
            adversarial_complexity=0.0,
        )
        self.assertGreaterEqual(depth, 10)


if __name__ == "__main__":
    unittest.main()
