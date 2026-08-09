from kaio_fluid import (
    CognitiveCompiler,
    CognitiveImmuneSystem,
    CognitiveMode,
    EvidenceState,
    FluidIntelligenceCore,
    ProblemContext,
)
from kaio_fluid.lab import SyntheticProblemLaboratory
from kaio_fluid.models import EvidenceItem, PredictionLedger


def test_high_stakes_novel_problem_compiles_to_deep_synthesis():
    plan = CognitiveCompiler().compile(
        ProblemContext(
            objective="novel high-stakes problem",
            stakes=0.95,
            uncertainty=0.9,
            novelty=0.95,
            irreversibility=0.85,
        )
    )
    assert plan.mode == CognitiveMode.DEEP_SYNTHESIS
    assert plan.authority_ceiling == "A1_INTERNAL"
    assert plan.external_effect is False
    assert "ROLLBACK_CHECK" in plan.primitives


def test_derivative_sources_do_not_masquerade_as_independent():
    items = (
        EvidenceItem("E1", EvidenceState.VERIFIED, "doc", "origin", 0.95, 1.0),
        EvidenceItem("E2", EvidenceState.SUPPORTED, "summary", "origin", 0.85, 0.8),
    )
    findings = CognitiveImmuneSystem().scan_evidence(items)
    assert any(f.code == "DERIVATIVE_CORROBORATION" for f in findings)


def test_information_gain_prioritizes_hidden_assumptions():
    ctx = ProblemContext(
        objective="resolve blocked route",
        stakes=0.7,
        uncertainty=0.8,
        novelty=0.7,
        irreversibility=0.4,
        constraints=("missing X",),
        assumptions=("X is necessary",),
    )
    priorities = FluidIntelligenceCore().information_gain_priority(ctx)
    assert priorities[0].startswith("VERIFY_ASSUMPTION")


def test_prediction_calibration_is_outcome_bound():
    ledger = PredictionLedger()
    ledger.record("A", 0.9, "true")
    ledger.record("B", 0.8, "false")
    assert ledger.calibration_error() == 0.45


def test_synthetic_lab_passes_baseline_cases():
    results = SyntheticProblemLaboratory().run()
    assert results
    assert all(result.passed for result in results)
