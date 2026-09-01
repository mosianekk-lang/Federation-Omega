from __future__ import annotations

import sqlite3
import unittest

from superior_logic.capability_graph import CapabilityGraph, CapabilityGraphError, CapabilityNode
from superior_logic.convergence import ConstitutionalConvergence
from superior_logic.digital_twin import CounterfactualController, FederationDigitalTwin, Intervention
from superior_logic.execution_fabric import HyperperformanceExecutionFabric
from superior_logic.hyperperformance import HyperperformanceError, ParallelLaneScheduler
from superior_logic.mission_ir import EffectClass, MissionCompileError, MissionIRCompiler
from superior_logic.provider_attestations import ProviderAttestation, ProviderAttestationStore
from superior_logic.shadow_evolution import OpportunityScanner, OutcomeSample, ShadowEvolutionLab


class MissionIRTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = ConstitutionalConvergence().compile_mission(
            mission_id="m-hyper",
            objective="reach verified target",
            source_version="src-1",
            initial_state={"ready": False},
            target_state={"ready": True},
        )

    def test_compile_is_deterministic_and_topological(self) -> None:
        compiler = MissionIRCompiler()
        mission = compiler.compile(
            self.contract,
            (
                {
                    "transition_id": "discover",
                    "description": "discover evidence",
                    "required_capabilities": ("SEARCH",),
                    "expected_value": 0.8,
                    "uncertainty_reduction": 0.9,
                    "speculative_allowed": True,
                },
                {
                    "transition_id": "verify",
                    "description": "verify evidence",
                    "dependencies": ("discover",),
                    "required_capabilities": ("VERIFY",),
                    "expected_value": 1.0,
                },
            ),
        )
        self.assertEqual(mission.topological_order(), ("discover", "verify"))
        self.assertEqual(len(mission.compiled_sha256), 64)
        self.assertEqual(mission.ready_transitions()[0].transition_id, "discover")

    def test_cycle_is_rejected(self) -> None:
        with self.assertRaisesRegex(MissionCompileError, "CYCLE"):
            MissionIRCompiler().compile(
                self.contract,
                (
                    {"transition_id": "a", "description": "a", "dependencies": ("b",)},
                    {"transition_id": "b", "description": "b", "dependencies": ("a",)},
                ),
            )

    def test_speculative_mutation_is_rejected(self) -> None:
        with self.assertRaisesRegex(MissionCompileError, "SPECULATIVE_MUTATION"):
            MissionIRCompiler().compile(
                self.contract,
                (
                    {
                        "transition_id": "write",
                        "description": "write provider state",
                        "effect_class": EffectClass.REVERSIBLE_EFFECT.value,
                        "speculative_allowed": True,
                    },
                ),
            )


class CapabilityAndParallelismTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = ConstitutionalConvergence().compile_mission(
            mission_id="m-parallel",
            objective="parallel verified work",
            source_version="src-2",
            initial_state={"complete": False},
            target_state={"complete": True},
        )
        self.graph = CapabilityGraph(
            (
                CapabilityNode(
                    capability_id="local-search-fast",
                    capability="SEARCH",
                    operation="SEARCH",
                    provider="LOCAL",
                    surface="CACHE",
                    success_rate=0.98,
                    proof_quality=0.95,
                    latency_ms=250,
                    concurrency_limit=8,
                ),
                CapabilityNode(
                    capability_id="local-search-shadow",
                    capability="SEARCH",
                    operation="SEARCH",
                    provider="LOCAL",
                    surface="INDEX",
                    success_rate=0.96,
                    proof_quality=0.96,
                    latency_ms=300,
                    concurrency_limit=8,
                ),
                CapabilityNode(
                    capability_id="local-verify",
                    capability="VERIFY",
                    operation="VERIFY",
                    provider="LOCAL",
                    surface="PROOFOS",
                    success_rate=0.99,
                    proof_quality=1.0,
                    latency_ms=300,
                    concurrency_limit=8,
                ),
                CapabilityNode(
                    capability_id="write-a",
                    capability="WRITE_A",
                    operation="WRITE_A",
                    provider="LOCAL",
                    surface="STATE",
                    mutating=True,
                    reversible=True,
                    conflict_domains=("state:shared",),
                ),
                CapabilityNode(
                    capability_id="write-b",
                    capability="WRITE_B",
                    operation="WRITE_B",
                    provider="LOCAL",
                    surface="STATE",
                    mutating=True,
                    reversible=True,
                    conflict_domains=("state:shared",),
                ),
            )
        )

    def test_attestation_required_route_fails_closed_until_fresh(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            store = ProviderAttestationStore(connection)
            graph = CapabilityGraph(
                (
                    CapabilityNode(
                        capability_id="gemini-route",
                        capability="GEMINI_INFERENCE",
                        operation="INFER",
                        provider="GOOGLE",
                        surface="GEMINI_VERTEX",
                        attestation_required=True,
                    ),
                )
            )
            self.assertEqual(graph.candidates("GEMINI_INFERENCE", now_epoch=150, attestation_store=store), ())
            store.put(
                ProviderAttestation.build(
                    attestation_id="att-1",
                    provider="GOOGLE",
                    surface="GEMINI_VERTEX",
                    subject="runtime",
                    state="INFERENCE_VERIFIED_SCOPED",
                    capabilities=("GEMINI_INFERENCE",),
                    observed_at_epoch=100,
                    expires_at_epoch=200,
                    evidence_refs=("provider:run-1",),
                    source_revision="src",
                )
            )
            route = graph.best_route("GEMINI_INFERENCE", now_epoch=150, attestation_store=store)
            self.assertEqual(route.attestation_id, "att-1")
            with self.assertRaises(CapabilityGraphError):
                graph.best_route("GEMINI_INFERENCE", now_epoch=201, attestation_store=store)
        finally:
            connection.close()

    def test_parallel_scheduler_uses_critical_path_voi_and_read_race(self) -> None:
        mission = MissionIRCompiler().compile(
            self.contract,
            (
                {
                    "transition_id": "research",
                    "description": "parallel research",
                    "required_capabilities": ("SEARCH",),
                    "expected_value": 1.0,
                    "uncertainty_reduction": 0.9,
                    "estimated_latency_ms": 1000,
                    "speculative_allowed": True,
                },
                {
                    "transition_id": "proof",
                    "description": "independent proof",
                    "required_capabilities": ("VERIFY",),
                    "expected_value": 1.0,
                    "uncertainty_reduction": 0.7,
                    "estimated_latency_ms": 900,
                },
                {
                    "transition_id": "finish",
                    "description": "finish",
                    "dependencies": ("research", "proof"),
                    "required_capabilities": ("VERIFY",),
                    "expected_value": 1.0,
                },
            ),
        )
        plan = ParallelLaneScheduler(max_lanes=4).plan(
            mission, self.graph, now_epoch=100
        )
        self.assertEqual({lane.transition_id for lane in plan.lanes}, {"research", "proof"})
        self.assertGreater(plan.theoretical_speedup, 1.0)
        research = next(lane for lane in plan.lanes if lane.transition_id == "research")
        self.assertEqual(research.execution_mode, "SPECULATIVE_READ_RACE")

    def test_conflict_domain_blocks_parallel_mutations(self) -> None:
        mission = MissionIRCompiler().compile(
            self.contract,
            (
                {
                    "transition_id": "write-a",
                    "description": "write a",
                    "required_capabilities": ("WRITE_A",),
                    "effect_class": EffectClass.REVERSIBLE_EFFECT.value,
                    "expected_value": 2.0,
                    "conflict_domains": ("state:shared",),
                },
                {
                    "transition_id": "write-b",
                    "description": "write b",
                    "required_capabilities": ("WRITE_B",),
                    "effect_class": EffectClass.REVERSIBLE_EFFECT.value,
                    "expected_value": 1.8,
                    "conflict_domains": ("state:shared",),
                },
            ),
        )
        plan = ParallelLaneScheduler(max_lanes=4).plan(mission, self.graph, now_epoch=100)
        self.assertEqual(len(plan.lanes), 1)
        self.assertTrue(plan.lanes[0].mutating)
        self.assertEqual(plan.lanes[0].execution_mode, "NORMAL")

    def test_hedging_and_work_stealing_remain_safe(self) -> None:
        mission = MissionIRCompiler().compile(
            self.contract,
            (
                {
                    "transition_id": "research",
                    "description": "research",
                    "required_capabilities": ("SEARCH",),
                    "expected_value": 1.0,
                    "speculative_allowed": True,
                },
                {
                    "transition_id": "proof",
                    "description": "proof",
                    "required_capabilities": ("VERIFY",),
                    "expected_value": 1.0,
                },
            ),
        )
        scheduler = ParallelLaneScheduler(max_lanes=4)
        plan = scheduler.plan(mission, self.graph, now_epoch=100)
        research = next(lane for lane in plan.lanes if lane.transition_id == "research")
        self.assertTrue(
            scheduler.should_hedge(
                research,
                elapsed_ms=5000,
                p95_latency_ms=2000,
                alternate_route_count=1,
                budget_available=True,
            )
        )
        assignments = scheduler.work_steal(plan.lanes, ("worker-2", "worker-1"))
        self.assertEqual(len(assignments), 2)
        winner = scheduler.first_semantically_verified(
            (
                {"route_id": "slow", "semantic_verified": True, "proof_valid": True, "provider_effect_performed": False, "completed_at_ms": 200},
                {"route_id": "fast", "semantic_verified": True, "proof_valid": True, "provider_effect_performed": False, "completed_at_ms": 100},
            )
        )
        self.assertEqual(winner["route_id"], "fast")


class TwinEvolutionAndFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = ConstitutionalConvergence().compile_mission(
            mission_id="m-twin",
            objective="make ready",
            source_version="src-3",
            initial_state={"ready": False},
            target_state={"ready": True},
        )
        self.mission = MissionIRCompiler().compile(
            self.contract,
            ({"transition_id": "inspect", "description": "inspect", "expected_value": 1.0},),
        )

    def test_counterfactual_twin_never_performs_provider_effect(self) -> None:
        twin = FederationDigitalTwin()
        twin.project_mission(self.mission)
        ranked = CounterfactualController(twin).rank(
            self.mission,
            (
                Intervention(
                    intervention_id="make-ready",
                    description="hypothetically make ready",
                    state_patch={"mission:m-twin": {"ready": True}},
                    expected_value=1.0,
                    uncertainty_reduction=0.5,
                    risk=0.1,
                    cost=0.1,
                    latency_ms=100,
                    reversible=True,
                    provider_effect_required=True,
                ),
            ),
        )
        self.assertEqual(ranked[0].intervention_id, "make-ready")
        self.assertEqual(ranked[0].target_match_ratio, 1.0)
        self.assertTrue(all(item.provider_effect_performed is False for item in ranked))

    def test_shadow_challenger_needs_empirical_threshold(self) -> None:
        lab = ShadowEvolutionLab()
        for index in range(5):
            lab.record(OutcomeSample("champion", 0.70, 0.80, 2000, 1.0, 1.0, independent_source=f"c{index%2}"))
        for index in range(29):
            lab.record(OutcomeSample("challenger", 0.95, 0.95, 400, 0.2, 0.0, independent_source=f"s{index%2}"))
        early = lab.evaluate(champion_id="champion", challenger_id="challenger", min_samples=30)
        self.assertFalse(early.promote)
        lab.record(OutcomeSample("challenger", 0.95, 0.95, 400, 0.2, 0.0, independent_source="s1"))
        mature = lab.evaluate(champion_id="champion", challenger_id="challenger", min_samples=30)
        self.assertTrue(mature.promote)
        self.assertGreater(mature.relative_gain, 0.05)

    def test_opportunity_scanner_discovers_repeated_and_slow_work(self) -> None:
        events = (
            {"latency_ms": 6000, "owner_interventions": 1, "status": "OK", "operation_signature": "read:x"},
            {"latency_ms": 7000, "owner_interventions": 0, "status": "TIMEOUT", "operation_signature": "read:x"},
            {"latency_ms": 100, "owner_interventions": 1, "status": "OK", "operation_signature": "read:x"},
        )
        ids = {item.opportunity_id for item in OpportunityScanner().scan(events)}
        self.assertTrue({"OPP-LATENCY-HEDGE", "OPP-OWNER-BURDEN", "OPP-FAILURE-ROUTE", "OPP-MEMOIZE-REPEAT"}.issubset(ids))

    def test_execution_fabric_preserves_single_authority_hierarchy(self) -> None:
        graph = CapabilityGraph()
        fabric = HyperperformanceExecutionFabric(graph)
        receipt = fabric.compile_and_plan(
            self.contract,
            ({"transition_id": "inspect", "description": "inspect", "expected_value": 1.0},),
            now_epoch=100,
        )
        architecture = fabric.architecture_receipt()
        self.assertFalse(receipt.provider_effect_performed)
        self.assertEqual(architecture["mission_semantic_owner"], "SLOS")
        self.assertEqual(architecture["transaction_kernel_owner"], "SOL_6_2_KERNEL")
        self.assertEqual(architecture["provider_effect_owner"], "SOVARA")
        self.assertFalse(architecture["speculative_provider_mutation"])


if __name__ == "__main__":
    unittest.main()
