from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile" / "fuse-mobile"


def read(relative: str) -> str:
    return (MOBILE / relative).read_text(encoding="utf-8")


def test_anthropic_v4_extends_genome_to_128_unique_genes() -> None:
    sources = "\n".join([
        read("src/anthropicCfbe.ts"),
        read("src/anthropicCfbeV2.ts"),
        read("src/anthropicCfbeV3.ts"),
        read("src/anthropicCfbeV4.ts"),
    ])
    ids = re.findall(r'id: "(ANTH-\d{3})"', sources)
    assert len(ids) == 128
    assert len(set(ids)) == 128
    assert ids == [f"ANTH-{number:03d}" for number in range(1, 129)]


def test_anthropic_v4_contains_recursive_improvement_primitives() -> None:
    source = read("src/anthropicCfbeV4.ts")
    required = {
        "deriveOutcomeInnovationSeed",
        "selectOnDemandTools",
        "formSpecialistAgentCell",
        "computeBlastRadiusBudget",
        "scoreInnovationCandidate",
        "rankInnovationCandidates",
        "runGeneralizationCourt",
        "compileRegressionCase",
        "harnessSimplificationCandidates",
        "compatibleDiffusionDecision",
        "anthropicV4Disposition",
    }
    for name in required:
        assert f"function {name}" in source


def test_success_and_failure_both_trigger_innovation_sequences() -> None:
    source = read("src/anthropicCfbeV4.ts")
    assert 'observation.kind === "SUCCESS"' in source
    assert 'observation.kind === "FAILURE"' in source
    assert "SUCCESS-MINE" in source
    assert "FAILURE-FORGE" in source
    assert "extract-success-invariant" in source
    assert "generate-harder-holdout" in source
    assert "reproduce-failure" in source
    assert "isolate-root-cause" in source
    assert "generate-repair-hypotheses" in source
    assert "persist-regression-oracle-if-proven" in source


def test_v4_promotion_is_proof_and_generalization_gated() -> None:
    source = read("src/anthropicCfbeV4.ts")
    for marker in [
        "quality-regression",
        "safety-regression",
        "holdout-below-floor",
        "adversarial-below-floor",
        "rollback-unproven",
        "readback-unproven",
    ]:
        assert marker in source
    assert "candidateCount <= 0" in source
    assert "courtPassed" in source
    assert 'return "PROMOTE_INTERNAL"' in source


def test_alpha_omega_formation_engine_compiles_bounded_agent_cells() -> None:
    source = read("src/alphaOmegaFormationEvolution.ts")
    assert "AO-FORMATION-EVOLUTION-1.0" in source
    assert "DEFAULT_SPRINT_BUDGET_MINUTES = 55" in source
    assert "DEFAULT_MAX_PARALLEL_AGENTS = 6" in source
    assert "compileAlphaOmegaFormationEvolution" in source
    assert "formSpecialistAgentCell" in source
    for role in [
        "ROOT_CAUSE_ANALYST",
        "REPRODUCTION_ENGINEER",
        "REPAIR_ARCHITECT",
        "REGRESSION_ENGINEER",
        "COUNTERFACTUAL_CHALLENGER",
        "SUCCESS_PATTERN_MINER",
        "GENERALIZATION_CHALLENGER",
        "SIMPLIFICATION_ENGINEER",
        "BENCHMARK_ENGINEER",
        "DIFFUSION_ANALYST",
        "SAFETY_PROOF_CRITIC",
    ]:
        assert role in source


def test_alpha_omega_engine_never_converts_success_into_terminal_stagnation() -> None:
    source = read("src/alphaOmegaFormationEvolution.ts")
    for marker in [
        "capture-success-invariant",
        "generate-harder-success-challenger",
        "search-harness-simplification",
        "evaluate-compatible-learning-diffusion",
    ]:
        assert marker in source


def test_alpha_omega_engine_recycles_failed_courts_into_new_innovation() -> None:
    source = read("src/alphaOmegaFormationEvolution.ts")
    for marker in [
        "mine-court-failure-or-gap",
        "trigger-new-innovation-seed",
        "generate-next-challenger",
        "repeat-court-with-frozen-oracles",
    ]:
        assert marker in source
    assert "reproduce-again" in source
    assert "generate-new-causal-hypotheses" in source
    assert "falsify-each-hypothesis" in source
    assert "build-root-cause-repair" in source


def test_alpha_omega_engine_holds_owner_boundary_effects() -> None:
    source = read("src/alphaOmegaFormationEvolution.ts")
    for marker in [
        "external-effect",
        "provider-authority-change",
        "credential-scope-change",
        "recurring-cost",
        "irreversible-mutation",
        "OWNER_GATE",
        "hold-external-effect",
    ]:
        assert marker in source


def test_alpha_omega_engine_requires_evidence_before_formation() -> None:
    source = read("src/alphaOmegaFormationEvolution.ts")
    assert "EVOLUTION_EVIDENCE_REQUIRED" in source
    assert "proofRequiredBeforePromotion" in source
    assert "exact-source-state" in source
    assert "independent-readback" in source
    assert "no-safety-regression" in source
    assert "rollback-or-restorable-preimage" in source


def test_recursive_improvement_sources_embed_no_permission_bypass() -> None:
    joined = "\n".join([
        read("src/anthropicCfbeV4.ts"),
        read("src/alphaOmegaFormationEvolution.ts"),
    ])
    assert "dangerously-skip-permissions" not in joined
    assert "skip-permissions" not in joined
