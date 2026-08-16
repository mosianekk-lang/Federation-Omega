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
    NodeState,
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


def test_event_bus_is_idempotent():
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
    assert calls == ["E1"]


def test_three_layer_state_preserves_history_after_projection_change():
    fabric = StateFabric()
    fabric.append_event("CCMA", {"event_id": "E1", "event_truth": "transmitted"})
    fabric.project(
        "CCMA", value="TRANSMITTED", source="provider-A", verified_at="t1", status="VERIFIED"
    )
    fabric.project(
        "CCMA", value="ACKNOWLEDGED", source="provider-B", verified_at="t2", status="VERIFIED"
    )
    record = fabric.get("CCMA")
    assert record is not None
    assert record.immutable_events[0]["event_truth"] == "transmitted"
    assert record.current_projection["value"] == "ACKNOWLEDGED"


def test_blocked_lane_does_not_freeze_independent_node():
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
    assert [node.node_id for node in graph.ready_nodes("M1")] == ["B"]


def test_proof_downgrade_finds_transitive_dependants():
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
    affected = graph.downgrade("S", new_status=TruthState.CONTRADICTED, confidence=0.1)
    assert {node.proof_node_id for node in affected} == {"P", "A"}


def test_resource_market_selects_minimum_strong_route():
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
    assert market.best([weak, strong], request).resource_id == "gmail"


def test_semantic_firewall_rejects_generic_transport_success():
    gate = SemanticReadbackFirewall()
    assert gate.evaluate(transport_ok=True, semantic_match=False) == "SEMANTIC_FAILURE"
    assert gate.evaluate(transport_ok=False, semantic_match=False) == "TRANSPORT_FAILURE"
    assert gate.evaluate(transport_ok=True, semantic_match=True) == "SUCCESS"


def test_boundary_becomes_engineering_build():
    engine = BoundaryBuildEngine()
    assert engine.classify("MISSING_CONNECTOR") == "UNRESOLVED_ENGINEERING_BUILD"
    assert engine.classify("SEMANTIC_FAILURE") == "UNRESOLVED_ENGINEERING_BUILD"


def test_learning_ledger_is_hash_linked_and_tamper_evident():
    ledger = LearningLedger()
    ledger.append(LearningEvent("C1", "task", "SUCCESS", "done"))
    ledger.append(LearningEvent("C2", "task2", "FAILURE", "failed"))
    assert ledger.verify() is True
    ledger._records[0]["event"]["actual_result"] = "tampered"  # deliberate fixture corruption
    assert ledger.verify() is False


def test_policy_candidate_promotes_only_when_fitter():
    incumbent = PerformanceVector(quality=5, reliability=5, proof=5, speed=3, latency_cost=5)
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
    assert result["promote"] is True
    assert result["delta"] > 0


def test_attention_governor_suppresses_self_resolvable_interrupt():
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
    assert governor.should_interrupt(low) is False
    assert governor.should_interrupt(high) is True


def test_marginal_information_gate_freezes_low_value_retrieval_for_internal_task():
    gate = MarginalInformationGainGate()
    score = gate.score(
        expected_information_gain=0.1,
        decision_impact=0.2,
        latency=1.0,
        owner_burden=1.0,
        duplication_cost=1.0,
    )
    assert gate.should_verify(score, consequential=False) is False
    assert gate.should_verify(score, consequential=True) is True


def test_entropy_controller_merges_duplicate_component():
    component = ArchitectureComponent(
        component_id="duplicate-watcher",
        unique_function=False,
        usage=0.8,
        overlap=0.95,
        maintenance_cost=0.8,
        owner_value=0.5,
    )
    assert EntropyController().classify(component) == "MERGE"


def test_restore_acceptance_remains_source_scoped():
    acceptance = AOHarmonicV3().restore_acceptance_test()
    assert acceptance["status"] == "SOURCE_IMPLEMENTED"
    assert acceptance["runtime_verified"] is False
    assert acceptance["external_effect_default"] is False


def test_v3_synthetic_reference_benchmark_beats_v2_reference():
    result = run_benchmark()
    assert result["truth_boundary"].startswith("SYNTHETIC_DETERMINISTIC")
    assert result["v3_wins"] is True
    assert result["delta"] > 0
