from kaio_fluid.engine import KaioFluidEngine
from kaio_fluid.models import EvidenceItem, EvidenceState, ProblemContext
from kaio_fluid.strategy import StrategyOption


def test_integrated_cycle_is_bounded_and_proof_aware():
    ctx = ProblemContext(
        objective="resolve an unfamiliar blocked high-stakes matter",
        stakes=0.9,
        uncertainty=0.85,
        novelty=0.9,
        irreversibility=0.8,
        evidence=(
            EvidenceItem("E1", EvidenceState.VERIFIED, "source-a", "L1", 0.95, 1.0),
            EvidenceItem("E2", EvidenceState.SUPPORTED, "source-b", "L2", 0.8, 0.8),
        ),
        constraints=("record X unavailable",),
        assumptions=("record X is necessary",),
    )
    options = (
        StrategyOption("direct", {"W1": 8, "W2": -4}, 0.3, 0.2),
        StrategyOption("proof-substitution", {"W1": 6, "W2": 4}, 0.8, 0.8),
    )
    result = KaioFluidEngine().run(
        ctx,
        actors=("A", "B"),
        dependencies=("D1",),
        unknowns=("who controls X",),
        strategy_options=options,
        causal_uncertainty=0.95,
    )
    assert result.plan.external_effect is False
    assert result.plan.authority_ceiling == "A1_INTERNAL"
    assert result.hypotheses
    assert len(result.reframes) >= 4
    assert result.representations[0].name == "CAUSAL"
    assert result.strategy is not None
    assert result.strategy.name == "proof-substitution"
    assert result.evidence_resilience["independent_lineages"] == 2
