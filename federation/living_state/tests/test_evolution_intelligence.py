from __future__ import annotations

import unittest

from federation.living_state.evolution_intelligence import (
    FederationEvolutionIntelligence, FitnessVector, MissionAttentionSignal,
    run_evolution_intelligence_canary,
)
from federation.living_state.world_model import (
    ContextState, EdgeKind, LearningClass, LivingWorldModel, NodeKind, ProofMaturity,
    Provenance, RouteTelemetry, WorldEdge, WorldNode, learning_event,
)

NOW = "2026-08-28T05:00:00+00:00"


def base_model() -> LivingWorldModel:
    m = LivingWorldModel()
    p = Provenance("s", "p", NOW, ProofMaturity.DETERMINISTIC_TESTED, 3600, .9)
    for node in (
        WorldNode("provider:P", NodeKind.PROVIDER, "P", "READY", {}, p),
        WorldNode("capability:C", NodeKind.CAPABILITY, "C", "ACTIVE", {}, p),
        WorldNode("mission:M", NodeKind.MISSION, "M", "ACTIVE", {}, p),
    ):
        m.observe_node(node)
    m.observe_edge(WorldEdge("e1", "capability:C", "provider:P", EdgeKind.DEPENDS_ON, p))
    m.observe_edge(WorldEdge("e2", "mission:M", "capability:C", EdgeKind.DEPENDS_ON, p))
    return m


class EvolutionIntelligenceTests(unittest.TestCase):
    def test_counterfactual_dependency_blast_radius(self):
        result = FederationEvolutionIntelligence(base_model()).dependency_impact(("provider:P",))
        self.assertIn("capability:C", result.impacted_capabilities)
        self.assertIn("mission:M", result.impacted_missions)
        self.assertTrue(result.topology_only); self.assertFalse(result.causal_claim)

    def test_unknown_counterfactual_node_fails_closed(self):
        with self.assertRaises(Exception):
            FederationEvolutionIntelligence(base_model()).dependency_impact(("missing",))

    def test_fragility_ranking_surfaces_provider(self):
        ranking = FederationEvolutionIntelligence(base_model()).fragility_ranking()
        self.assertEqual(ranking[0]["node_id"], "provider:P")
        self.assertEqual(ranking[0]["mission_exposure"], 1)

    def test_pareto_frontier_drops_dominated_route(self):
        m = base_model()
        for i in range(3):
            m.observe_route_telemetry(RouteTelemetry("A", "M", NOW, True, 10, .1, .1, .9, .9, .1, ("FD1",), f"a{i}"))
            m.observe_route_telemetry(RouteTelemetry("B", "M", NOW, False, 1000, 5, 5, .2, .2, 5, ("FD2",), f"b{i}"))
        ids = {x.route_id for x in FederationEvolutionIntelligence(m).route_pareto_frontier()}
        self.assertIn("A", ids); self.assertNotIn("B", ids)

    def test_calibration_uses_observed_outcomes(self):
        m = base_model()
        for i, success in enumerate((1,1,0,1)):
            m.observe_route_telemetry(RouteTelemetry("A", "M", NOW, bool(success), 1,0,0,1,1,0,("FD",),f"p{i}"))
        report = FederationEvolutionIntelligence(m).calibration()[0]
        self.assertEqual(report.samples, 4)
        self.assertAlmostEqual(report.observed_rate, .75)

    def test_attention_allocation_preserves_reserve(self):
        intel = FederationEvolutionIntelligence(base_model())
        allocation = intel.allocate_attention((
            MissionAttentionSignal("HIGH",1,1,1,1,1,1,0),
            MissionAttentionSignal("LOW",.1,.1,.1,.1,.1,.1,0),
        ))
        self.assertEqual(allocation[0].mission_id, "HIGH")
        self.assertLess(sum(x.share for x in allocation), 1.0)

    def test_attention_invalid_budget_fails(self):
        with self.assertRaises(ValueError):
            FederationEvolutionIntelligence(base_model()).allocate_attention((MissionAttentionSignal("M",1,1,1,1,1,1,0),), total_budget=2)

    def test_immune_scan_detects_repeated_near_miss(self):
        m = base_model()
        m.observe_learning(learning_event(learning_class=LearningClass.NEAR_MISS, fingerprint="NEARMISS", observed_at=NOW, matter_scope="GLOBAL", route_id="R", signal="s", diagnosis="d", hypothesis="h", test_ref="t", result_ref="r", proof_refs=("p",), recurrence=2, independent_evidence=True))
        signals = FederationEvolutionIntelligence(m).immune_scan(now=NOW)
        self.assertTrue(any(x.signal_class == "REPEATED_NEAR_MISS" for x in signals))
        self.assertTrue(all(not x.external_effect for x in signals))

    def test_immune_scan_detects_context_exhaustion(self):
        m = base_model(); m.observe_context(ContextState("C",950,1000,0,0,source_refs=("s",)))
        self.assertTrue(any(x.signal_class == "CONTEXT_EXHAUSTION" for x in FederationEvolutionIntelligence(m).immune_scan(now=NOW)))

    def test_genome_candidates_are_shadow_only(self):
        m = base_model(); m.observe_context(ContextState("C",950,1000,0,0))
        candidates = FederationEvolutionIntelligence(m).genome_candidates(now=NOW)
        self.assertTrue(candidates)
        self.assertTrue(all(x.disposition == "SHADOW_EXPERIMENT_ONLY" for x in candidates))

    def test_fitness_vector_not_scalar_only(self):
        fitness = FederationEvolutionIntelligence(base_model()).fitness_vector(now=NOW)
        self.assertGreaterEqual(fitness.measured_dimensions, 4)
        self.assertGreaterEqual(fitness.harmonic_fitness, 0)

    def test_goodhart_gate_blocks_large_non_target_regression(self):
        intel = FederationEvolutionIntelligence(base_model())
        base = FitnessVector(.7,.7,.7,.7,.7,.7,.9,.5,8)
        bad = FitnessVector(.9,.2,.2,.7,.7,.7,.9,.5,8)
        gate = intel.anti_goodhart_gate(baseline=base, candidate=bad, claimed_target_improvement="proof")
        self.assertFalse(gate["passed"])
        self.assertIn("freshness", gate["material_regressions"])

    def test_goodhart_gate_allows_balanced_improvement(self):
        intel = FederationEvolutionIntelligence(base_model())
        base = FitnessVector(.7,.7,.7,.7,.7,.7,.9,.5,8)
        good = FitnessVector(.8,.75,.7,.72,.7,.72,.9,.6,8)
        self.assertTrue(intel.anti_goodhart_gate(baseline=base, candidate=good, claimed_target_improvement="proof")["passed"])

    def test_canary(self):
        result = run_evolution_intelligence_canary()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["count"], 15)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["external_effects"], 0)


if __name__ == "__main__":
    unittest.main()
