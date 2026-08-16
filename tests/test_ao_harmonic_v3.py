import unittest

from ao_harmonic_v3.benchmark import run_benchmark
from ao_harmonic_v3.event_bus import EventBus
from ao_harmonic_v3.evolution import (
    ArchitectureComponent,
    EntropyController,
    HumanAttentionGovernor,
    LearningEvent,
    LearningLedger,
    MarginalInformationGainGate,
    PerformanceVector,
    PolicyEvolution,
)
from ao_harmonic_v3.graphs import MissionGraph, ProofGraph, StateFabric
from ao_harmonic_v3.models import (
    FederationEvent,
    Maturity,
    Mission,
    MissionNode,
    ProofNode,
    ResourceOffer,
    RiskClass,
    TruthState,
)
from ao_harmonic_v3.resource_market import ResourceMarket, ResourceRequest
from ao_harmonic_v3.runtime import (
    AOHarmonicV3,
    BoundaryBuildEngine,
    SemanticReadbackFirewall,
)


class AOHarmonicV3Tests(unittest.TestCase):
    def test_event_bus_is_idempotent(self):
        bus = EventBus()
        calls = []
        bus.subscribe("NEW_EVIDENCE", lambda event: calls.append(event.event_id))
        event = FederationEvent(
            event_id="E1",
            event_type="NEW_EVIDENCE",
            source="fixture",
            workstream="TEST",
            idempotency_key="stable-key",
            timestamp="2026-08-16T00:00:00Z",
        )
        bus.emit(event)
        bus.emit(event)
        self.assertEqual(calls, ["E1"])

    def test_three_layer_state_preserves_history_after_projection_change(self):
        fabric = StateFabric()
        fabric.append_event("CCMA", {"event_id": "E1", "event_truth": "transmitted"})
        fabric.project(
            "CCMA",
            value="TRANSMITTED",
            source="provider-A",
            verified_at="t1",
            status="VERIFIED",
        )
        fabric.project(
            "CCMA",
            value="ACKNOWLEDGED",
            source="provider-B",
            verified_at="t2",
            status="VERIFIED",
        )
        record = fabric.get("CCMA")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.immutable_events[0]["event_truth"], "transmitted")
        self.assertEqual(record.current_projection["value"], "ACKNOWLEDGED")

    def test_blocked_lane_does_not_freeze_independent_node(self):
        graph = MissionGraph()
        mission = Mission(
            mission_id="M1",
            objective="prepare hearing",
            desired_outcome="ready",
            risk_class=RiskClass.HIGH,
        )
        graph.add_mission(mission)
        graph.add_node("M1", MissionNode("A", "wait for reply"))
        graph.add_node("M1", MissionNode("B", "prepare fallback"))
        graph.block_node("M1", "A", "provider pending")
        self.assertEqual([node.node_id for node in graph.ready_nodes("M1")], ["B"])

    def test_proof_downgrade_finds_transitive_dependants(self):
        graph = ProofGraph()
        graph.add(ProofNode("S", "SOURCE", "email", TruthState.VERIFIED, confidence=1.0))
        graph.add(
            ProofNode(
                "P",
                "PROPOSITION",
                "proposition",
                TruthState.VERIFIED,
                confidence=0.9,
                depends_on=["S"],
            )
        )
        graph.add(
            ProofNode(
                "A",
                "ARGUMENT",
                "argument",
                TruthState.INFERENCE,
                confidence=0.7,
                depends_on=["P"],
            )
        )
        affected = graph.downgrade(
            "S", new_status=TruthState.CONTRADICTED, confidence=0.1
        )
        self.assertEqual({node.proof_node_id for node in affected}, {"P", "A"})

    def test_resource_market_selects_minimum_strong_route(self):
        market = ResourceMarket()
        request = ResourceRequest(
            capability="SEARCH_EMAIL",
            semantic_scope="provider-native-mail",
            minimum_maturity=Maturity.DETERMINISTIC_TESTED,
            maximum_owner_burden=1.0,
        )
        weak = ResourceOffer(
            resource_id="weak",
            provider="archive",
            capability="SEARCH_EMAIL",
            semantic_scope="provider-native-mail archive",
            authority_ceiling="A1_READ",
            maturity=Maturity.DETERMINISTIC_TESTED,
            relevance=0.7,
            semantic_fit=0.8,
            freshness=0.4,
            reliability=0.7,
            proof_strength=0.5,
            executability=1.0,
            information_gain=0.6,
            latency=2.0,
            owner_burden=0.5,
            privacy_cost=0.5,
            failure_risk=0.5,
        )
        strong = ResourceOffer(
            resource_id="gmail",
            provider="Gmail",
            capability="SEARCH_EMAIL",
            semantic_scope="provider-native-mail live",
            authority_ceiling="A1_READ",
            maturity=Maturity.OPERATIONAL_VERIFIED,
            relevance=1.0,
            semantic_fit=1.0,
            freshness=1.0,
            reliability=0.98,
            proof_strength=0.95,
            executability=1.0,
            information_gain=0.9,
            latency=0.5,
            owner_burden=0.0,
            privacy_cost=0.2,
            failure_risk=0.1,
        )
        selected = market.best([weak, strong], request)
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected.resource_id, "gmail")

    def test_semantic_firewall_rejects_generic_transport_success(self):
        gate = SemanticReadbackFirewall()
        self.assertEqual(
            gate.evaluate(transport_ok=True, semantic_match=False), "SEMANTIC_FAILURE"
        )
        self.assertEqual(
            gate.evaluate(transport_ok=False, semantic_match=False), "TRANSPORT_FAILURE"
        )
        self.assertEqual(gate.evaluate(transport_ok=True, semantic_match=True), "SUCCESS")

    def test_boundary_becomes_engineering_build(self):
        engine = BoundaryBuildEngine()
        self.assertEqual(
            engine.classify("MISSING_CONNECTOR"), "UNRESOLVED_ENGINEERING_BUILD"
        )
        self.assertEqual(
            engine.classify("SEMANTIC_FAILURE"), "UNRESOLVED_ENGINEERING_BUILD"
        )

    def test_learning_ledger_is_hash_linked_and_tamper_evident(self):
        ledger = LearningLedger()
        ledger.append(LearningEvent("C1", "task", "SUCCESS", "done"))
        ledger.append(LearningEvent("C2", "task2", "FAILURE", "failed"))
        self.assertTrue(ledger.verify())
        ledger._records[0]["event"]["actual_result"] = "tampered"  # deliberate fixture corruption
        self.assertFalse(ledger.verify())

    def test_policy_candidate_promotes_only_when_fitter(self):
        incumbent = PerformanceVector(
            quality=5, reliability=5, proof=5, speed=3, latency_cost=5
        )
        candidate = PerformanceVector(
            quality=5,
            reliability=5,
            proof=5,
            speed=8,
            owner_time_recovered=4,
            simplicity_gain=3,
            latency_cost=1,
        )
        result = PolicyEvolution().compare(incumbent, candidate)
        self.assertTrue(result["promote"])
        self.assertGreater(result["delta"], 0)

    def test_attention_governor_suppresses_self_resolvable_interrupt(self):
        governor = HumanAttentionGovernor()
        low = governor.score(
            urgency=0.4,
            consequence=0.4,
            decision_necessity=0.2,
            owner_exclusivity=0.1,
            self_resolution_capability=0.9,
        )
        high = governor.score(
            urgency=1.0,
            consequence=1.0,
            decision_necessity=1.0,
            owner_exclusivity=1.0,
            self_resolution_capability=0.1,
        )
        self.assertFalse(governor.should_interrupt(low))
        self.assertTrue(governor.should_interrupt(high))

    def test_marginal_information_gate_freezes_low_value_internal_retrieval(self):
        gate = MarginalInformationGainGate()
        score = gate.score(
            expected_information_gain=0.1,
            decision_impact=0.2,
            latency=1.0,
            owner_burden=1.0,
            duplication_cost=1.0,
        )
        self.assertFalse(gate.should_verify(score, consequential=False))
        self.assertTrue(gate.should_verify(score, consequential=True))

    def test_entropy_controller_merges_duplicate_component(self):
        component = ArchitectureComponent(
            component_id="duplicate-watcher",
            unique_function=False,
            usage=0.8,
            overlap=0.95,
            maintenance_cost=0.8,
            owner_value=0.5,
        )
        self.assertEqual(EntropyController().classify(component), "MERGE")

    def test_restore_acceptance_remains_source_scoped(self):
        acceptance = AOHarmonicV3().restore_acceptance_test()
        self.assertEqual(acceptance["status"], "SOURCE_IMPLEMENTED")
        self.assertFalse(acceptance["runtime_verified"])
        self.assertFalse(acceptance["external_effect_default"])

    def test_v3_synthetic_reference_benchmark_beats_v2_reference(self):
        result = run_benchmark()
        self.assertTrue(result["truth_boundary"].startswith("SYNTHETIC_DETERMINISTIC"))
        self.assertTrue(result["v3_wins"])
        self.assertGreater(result["delta"], 0)


if __name__ == "__main__":
    unittest.main()
