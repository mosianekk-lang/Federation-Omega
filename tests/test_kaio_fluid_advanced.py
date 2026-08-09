from kaio_fluid.discovery import DiscoveryEngine
from kaio_fluid.epistemic_engineering import EpistemicEngineering, ExpectedRecord
from kaio_fluid.evolution import CandidateImprovement, EvolutionGovernor
from kaio_fluid.metrics import CognitiveHealth
from kaio_fluid.morphogenesis import CognitiveMorphogenesis
from kaio_fluid.models import CognitiveMode, ReasoningPlan
from kaio_fluid.strategy import RobustStrategyEngine, StrategyOption


def test_representation_tournament_prefers_dominant_signal():
    ranked = DiscoveryEngine().representation_tournament(
        temporal_density=0.2,
        dependency_density=0.4,
        causal_uncertainty=0.95,
        strategic_interaction=0.3,
        element_structure=0.5,
    )
    assert ranked[0].name == "CAUSAL"


def test_paradigm_escape_activates_under_model_stress():
    assert DiscoveryEngine().paradigm_escape_needed(
        exception_count=2,
        failed_predictions=2,
        unresolved_contradictions=1,
        reasoning_debt=1,
    )


def test_morphogenesis_uses_independent_topology_for_deep_synthesis():
    plan = ReasoningPlan(
        mode=CognitiveMode.DEEP_SYNTHESIS,
        specialists=("KAIO", "TRUTHGRID", "JFRIE", "RED_TEAM"),
        primitives=("FALSIFICATION",),
        verification_depth=5,
        simulation_depth=4,
        stop_threshold=0.05,
    )
    architecture = CognitiveMorphogenesis().assemble(plan)
    assert architecture.topology == "PARALLEL_INDEPENDENT_PATHS_THEN_JUDGE"
    assert architecture.dissolve_after_task
    assert all(not s.external_effect for s in architecture.specialists)


def test_robust_strategy_prefers_stronger_worst_case():
    options = (
        StrategyOption("A", {"W1": 8, "W2": -5}, 0.4, 0.2),
        StrategyOption("B", {"W1": 5, "W2": 3}, 0.8, 0.7),
    )
    choice = RobustStrategyEngine().robust_choice(options)
    assert choice is not None
    assert choice.name == "B"


def test_evolution_governor_rewards_improvement_without_authority_expansion():
    good = EvolutionGovernor().evaluate(
        CandidateImprovement("C1", 0.1, 0.08, 0.05, -0.03)
    )
    bad = EvolutionGovernor().evaluate(
        CandidateImprovement("C2", 0.2, 0.1, 0.1, 0.0, authority_expansion=True)
    )
    assert good.promote
    assert not bad.promote
    assert "AUTHORITY_EXPANSION_FORBIDDEN" in bad.reasons


def test_epistemic_engineering_detects_missing_expected_record():
    records = (
        ExpectedRecord("approval", "request", "request receipt", True, True),
        ExpectedRecord("approval", "decision", "decision receipt", True, False),
    )
    engine = EpistemicEngineering()
    assert not engine.proof_ready_process(records)
    recs = engine.recommendations(records)
    assert len(recs) == 1
    assert "decision receipt" in recs[0].recommendation


def test_cognitive_health_penalizes_epistemic_debt_and_low_readback():
    good = CognitiveHealth(0.02, 0.98, 0.08, 0.05, 0.1, 0.95)
    weak = CognitiveHealth(0.25, 0.6, 0.35, 0.3, 0.6, 0.4)
    assert good.score() > weak.score()
    assert "completion_readback" in weak.unhealthy_dimensions()
