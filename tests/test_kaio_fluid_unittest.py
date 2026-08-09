import unittest
from datetime import datetime, timezone

from kaio_fluid.abstraction import ProblemAbstractionEngine
from kaio_fluid.causal import CausalClaim, CausalTimeLockGuard, TimedFact
from kaio_fluid.compiler import CognitiveCompiler
from kaio_fluid.dependency import DependencyCentrality, DependencyNode
from kaio_fluid.discovery import DiscoveryEngine
from kaio_fluid.engine import KaioFluidEngine
from kaio_fluid.epistemic_engineering import EpistemicEngineering, ExpectedRecord
from kaio_fluid.evolution import CandidateImprovement, EvolutionGovernor
from kaio_fluid.immune import CognitiveImmuneSystem
from kaio_fluid.lab import SyntheticProblemLaboratory
from kaio_fluid.lineage import LineageGraph, LineageNode
from kaio_fluid.models import EvidenceItem, EvidenceState, ProblemContext
from kaio_fluid.promotion import PromotionGovernor, PromotionReceipt
from kaio_fluid.strategy import StrategyOption


class KaioFluidFederationTests(unittest.TestCase):
    def test_compiler_is_internal_and_scales_to_novel_stakes(self):
        plan = CognitiveCompiler().compile(ProblemContext(
            objective="novel high stakes problem",
            stakes=0.95, uncertainty=0.9, novelty=0.95, irreversibility=0.85,
        ))
        self.assertEqual("DEEP_SYNTHESIS", plan.mode.value)
        self.assertEqual("A1_INTERNAL", plan.authority_ceiling)
        self.assertFalse(plan.external_effect)

    def test_derivative_corroboration_is_detected(self):
        findings = CognitiveImmuneSystem().scan_evidence((
            EvidenceItem("E1", EvidenceState.VERIFIED, "doc", "origin", 0.95, 1.0),
            EvidenceItem("E2", EvidenceState.SUPPORTED, "summary", "origin", 0.8, 0.8),
        ))
        self.assertTrue(any(f.code == "DERIVATIVE_CORROBORATION" for f in findings))

    def test_lineage_cycle_fails_closed_and_change_propagates(self):
        graph = LineageGraph()
        for node in (
            LineageNode("E", "EVIDENCE", "VERIFIED"),
            LineageNode("P", "PROPOSITION", "SUPPORTED"),
            LineageNode("D", "DECISION", "INTERNAL"),
        ):
            graph.add_node(node)
        graph.link("E", "P")
        graph.link("P", "D")
        self.assertEqual(("E",), graph.source_roots("D"))
        self.assertEqual(("D", "P"), graph.affected_descendants("E"))
        with self.assertRaises(ValueError):
            graph.link("D", "E")

    def test_time_lock_blocks_hindsight_and_missing_mechanism(self):
        guard = CausalTimeLockGuard()
        cause = TimedFact("C", datetime(2026, 2, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc), "VERIFIED")
        outcome = TimedFact("O", datetime(2026, 1, 20, tzinfo=timezone.utc), datetime(2026, 1, 15, tzinfo=timezone.utc), "VERIFIED")
        decision = datetime(2026, 1, 10, tzinfo=timezone.utc)
        self.assertTrue(guard.hindsight_violation(cause, decision))
        self.assertFalse(guard.causal_claim_allowed(CausalClaim("C", "O", None), cause=cause, outcome=outcome))

    def test_dependency_centrality_prioritizes_unlock_leverage(self):
        graph = DependencyCentrality(
            (DependencyNode("A", True, 0.4), DependencyNode("B", True, 0.9), DependencyNode("C"), DependencyNode("D")),
            (("A", "C"), ("C", "D"), ("B", "D")),
        )
        self.assertEqual("A", graph.ranked_blockers()[0][0])

    def test_discovery_can_trigger_paradigm_escape(self):
        engine = DiscoveryEngine()
        ranked = engine.representation_tournament(
            temporal_density=0.2, dependency_density=0.4, causal_uncertainty=0.95,
            strategic_interaction=0.3, element_structure=0.5,
        )
        self.assertEqual("CAUSAL", ranked[0].name)
        self.assertTrue(engine.paradigm_escape_needed(
            exception_count=2, failed_predictions=2, unresolved_contradictions=1, reasoning_debt=1,
        ))

    def test_evolution_cannot_self_expand_authority(self):
        decision = EvolutionGovernor().evaluate(CandidateImprovement(
            "C", 0.2, 0.1, 0.1, 0.0, authority_expansion=True,
        ))
        self.assertFalse(decision.promote)
        self.assertIn("AUTHORITY_EXPANSION_FORBIDDEN", decision.reasons)

    def test_promotion_cannot_jump_to_operational(self):
        ok, failures = PromotionGovernor().validate(PromotionReceipt(
            capability_id="KAIO-FI", from_state="DESIGN_ONLY", to_state="OPERATIONAL_VERIFIED",
            deterministic_tests=True, rollback_proven=False, target_readback=False,
            health_check=False, persistence_check=False, provider_receipt=False,
        ))
        self.assertFalse(ok)
        self.assertIn("STATE_JUMP_NOT_ALLOWED", failures)

    def test_epistemic_engineering_requires_expected_records(self):
        records = (
            ExpectedRecord("approval", "request", "request receipt", True, True),
            ExpectedRecord("approval", "decision", "decision receipt", True, False),
        )
        self.assertFalse(EpistemicEngineering().proof_ready_process(records))

    def test_integrated_engine_remains_proof_bound(self):
        ctx = ProblemContext(
            objective="resolve unfamiliar blocked matter",
            stakes=0.9, uncertainty=0.85, novelty=0.9, irreversibility=0.8,
            evidence=(EvidenceItem("E1", EvidenceState.VERIFIED, "source", "L1", 0.95, 1.0),),
            constraints=("record unavailable",), assumptions=("record is necessary",),
        )
        result = KaioFluidEngine().run(
            ctx,
            strategy_options=(
                StrategyOption("direct", {"W1": 8, "W2": -4}, 0.3, 0.2),
                StrategyOption("substitute", {"W1": 6, "W2": 4}, 0.8, 0.8),
            ),
            causal_uncertainty=0.95,
        )
        self.assertFalse(result.plan.external_effect)
        self.assertEqual("A1_INTERNAL", result.plan.authority_ceiling)
        self.assertEqual("substitute", result.strategy.name)

    def test_synthetic_lab_has_full_25_case_baseline_and_passes(self):
        results = SyntheticProblemLaboratory().run()
        self.assertEqual(25, len(results))
        self.assertEqual(25, len({result.name for result in results}))
        self.assertTrue(all(result.passed for result in results), results)


if __name__ == "__main__":
    unittest.main()
