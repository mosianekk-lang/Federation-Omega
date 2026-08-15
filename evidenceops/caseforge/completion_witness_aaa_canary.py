from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Iterable, Mapping, Sequence

from bubbles.chatbridge_omega4.completion_witness import (
    CompletionObservation,
    CompletionWitnessEngine,
    ContinuationClass,
    PendingUserTask,
    TaskCompletionState,
    WitnessMode,
)


class ClaimClass(str, Enum):
    SAFE_INTERNAL_CONTINUATION = "SAFE_INTERNAL_CONTINUATION"
    PROVIDER_TERMINAL_STATE = "PROVIDER_TERMINAL_STATE"
    EVIDENTIARY_FACT_PROMOTION = "EVIDENTIARY_FACT_PROMOTION"
    CONSEQUENTIAL_EXTERNAL_ACTION = "CONSEQUENTIAL_EXTERNAL_ACTION"


@dataclass(frozen=True)
class HomePolicy:
    system_id: str
    canonical_name: str
    blocked_claim_classes_on_owner_assertion: tuple[ClaimClass, ...]
    requires_provider_proof_for_terminal_claim: bool = True
    external_effect_default: bool = False

    def validate(self) -> "HomePolicy":
        if not self.system_id or not self.canonical_name:
            raise ValueError("system_id and canonical_name are required")
        if self.external_effect_default:
            raise ValueError("AAA shadow homes may not default to external effect")
        return self


HOME_POLICIES: Mapping[str, HomePolicy] = {
    "CHATGOV": HomePolicy(
        system_id="CHATGOV",
        canonical_name="Bubbles Adaptive Chat Governor Ω3.1",
        blocked_claim_classes_on_owner_assertion=(
            ClaimClass.PROVIDER_TERMINAL_STATE,
            ClaimClass.EVIDENTIARY_FACT_PROMOTION,
            ClaimClass.CONSEQUENTIAL_EXTERNAL_ACTION,
        ),
    ),
    "EVIDENCEOPS": HomePolicy(
        system_id="EVIDENCEOPS",
        canonical_name="EvidenceOps",
        blocked_claim_classes_on_owner_assertion=(
            ClaimClass.PROVIDER_TERMINAL_STATE,
            ClaimClass.EVIDENTIARY_FACT_PROMOTION,
            ClaimClass.CONSEQUENTIAL_EXTERNAL_ACTION,
        ),
    ),
    "TRUTHGRID": HomePolicy(
        system_id="TRUTHGRID",
        canonical_name="TruthGrid",
        blocked_claim_classes_on_owner_assertion=(
            ClaimClass.PROVIDER_TERMINAL_STATE,
            ClaimClass.EVIDENTIARY_FACT_PROMOTION,
            ClaimClass.CONSEQUENTIAL_EXTERNAL_ACTION,
        ),
    ),
}


@dataclass(frozen=True)
class ShadowCase:
    case_id: str
    claim_class: ClaimClass
    continuation_class: ContinuationClass
    observations: tuple[CompletionObservation, ...]
    expected_may_continue: bool
    expected_terminal_provider_claim: bool


@dataclass(frozen=True)
class HomeRunMetrics:
    system_id: str
    total_cases: int
    redundant_owner_prompts_baseline: int
    redundant_owner_prompts_candidate: int
    unsafe_continuations: int
    blocked_safe_continuations: int
    false_terminal_provider_claims: int
    provider_verified_completions: int
    owner_asserted_safe_resumes: int
    alpha2_scope_blocks: int


@dataclass(frozen=True)
class IntelligenceDensityVector:
    outcome_quality: float
    reliability: float
    reuse: float
    learning: float
    cost: float
    complexity: float
    latency: float
    owner_burden: float

    def validate(self) -> "IntelligenceDensityVector":
        for key, value in asdict(self).items():
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{key} must be normalized to [0,1]")
        return self


@dataclass(frozen=True)
class IntelligenceDensityComparison:
    baseline: IntelligenceDensityVector
    candidate: IntelligenceDensityVector
    delta: float


@dataclass(frozen=True)
class HomeCanaryResult:
    system_id: str
    metrics: HomeRunMetrics
    intelligence_density: IntelligenceDensityComparison
    no_material_regression: bool


@dataclass(frozen=True)
class CompletionWitnessAAACanaryReceipt:
    capability_id: str
    source_system: str
    candidate_homes: tuple[str, ...]
    home_results: tuple[HomeCanaryResult, ...]
    feedback_improvement: str
    feedback_source_homes: tuple[str, ...]
    redistributed_to: tuple[str, ...]
    status: str
    proof_scope: str
    external_effect: bool


_DEFAULT_WEIGHTS: Mapping[str, float] = {
    "outcome_quality": 1.0,
    "reliability": 1.0,
    "reuse": 0.6,
    "learning": 0.6,
    "cost": 0.35,
    "complexity": 0.35,
    "latency": 0.8,
    "owner_burden": 1.0,
}


def _score(vector: IntelligenceDensityVector, weights: Mapping[str, float]) -> float:
    vector.validate()
    positive = (
        weights["outcome_quality"] * vector.outcome_quality
        + weights["reliability"] * vector.reliability
        + weights["reuse"] * vector.reuse
        + weights["learning"] * vector.learning
    )
    negative = (
        weights["cost"] * vector.cost
        + weights["complexity"] * vector.complexity
        + weights["latency"] * vector.latency
        + weights["owner_burden"] * vector.owner_burden
    )
    return positive - negative


def compare_intelligence_density(
    baseline: IntelligenceDensityVector,
    candidate: IntelligenceDensityVector,
    *,
    weights: Mapping[str, float] = _DEFAULT_WEIGHTS,
) -> IntelligenceDensityComparison:
    missing = set(_DEFAULT_WEIGHTS) - set(weights)
    if missing:
        raise ValueError(f"missing Intelligence Density weights: {sorted(missing)}")
    delta = _score(candidate, weights) - _score(baseline, weights)
    return IntelligenceDensityComparison(baseline, candidate, round(delta, 6))


class CompletionWitnessHomeAdapter:
    """AAA adapter around the existing ChatBridge completion-witness gene.

    The common gene remains responsible for completion evidence reconciliation.
    The receiving home adds only local claim-class restrictions. Owner assertion can
    release safe internal continuation, but it cannot become provider proof,
    evidentiary-fact promotion authority, or consequential external authority.
    """

    def __init__(self, policy: HomePolicy, engine: CompletionWitnessEngine | None = None) -> None:
        self.policy = policy.validate()
        self.engine = engine or CompletionWitnessEngine()

    def reconcile(self, task: PendingUserTask, claim_class: ClaimClass, observations: Iterable[CompletionObservation]):
        decision = self.engine.reconcile(task, observations)
        if (
            decision.state is TaskCompletionState.OWNER_ASSERTED_COMPLETED
            and claim_class in self.policy.blocked_claim_classes_on_owner_assertion
        ):
            return {
                "state": decision.state,
                "may_continue": False,
                "may_make_terminal_provider_claim": False,
                "reason": "owner assertion retained as completion evidence but local claim class requires stronger proof",
                "alpha2_scope_block": True,
            }
        return {
            "state": decision.state,
            "may_continue": bool(decision.may_continue),
            "may_make_terminal_provider_claim": bool(decision.may_make_terminal_provider_claim),
            "reason": decision.reason,
            "alpha2_scope_block": False,
        }


def default_shadow_cases() -> tuple[ShadowCase, ...]:
    provider_success = CompletionObservation(
        witness_mode=WitnessMode.PROVIDER_READBACK,
        success=True,
        provider="openai",
        evidence_ref="shadow:provider:verified",
    )
    owner_success = CompletionObservation(
        witness_mode=WitnessMode.USER_ASSERTION,
        success=True,
        provider="openai",
        evidence_ref="shadow:owner:asserted",
    )
    return (
        ShadowCase(
            "provider_verified_safe",
            ClaimClass.SAFE_INTERNAL_CONTINUATION,
            ContinuationClass.SAFE_INTERNAL,
            (provider_success,),
            True,
            True,
        ),
        ShadowCase(
            "owner_asserted_safe",
            ClaimClass.SAFE_INTERNAL_CONTINUATION,
            ContinuationClass.SAFE_INTERNAL,
            (owner_success,),
            True,
            False,
        ),
        ShadowCase(
            "owner_asserted_provider_terminal",
            ClaimClass.PROVIDER_TERMINAL_STATE,
            ContinuationClass.SAFE_INTERNAL,
            (owner_success,),
            False,
            False,
        ),
        ShadowCase(
            "owner_asserted_evidentiary_promotion",
            ClaimClass.EVIDENTIARY_FACT_PROMOTION,
            ContinuationClass.SAFE_INTERNAL,
            (owner_success,),
            False,
            False,
        ),
        ShadowCase(
            "owner_asserted_consequential",
            ClaimClass.CONSEQUENTIAL_EXTERNAL_ACTION,
            ContinuationClass.CONSEQUENTIAL_EXTERNAL,
            (owner_success,),
            False,
            False,
        ),
        ShadowCase(
            "no_witness_safe",
            ClaimClass.SAFE_INTERNAL_CONTINUATION,
            ContinuationClass.SAFE_INTERNAL,
            (),
            False,
            False,
        ),
    )


def _task(case: ShadowCase) -> PendingUserTask:
    return PendingUserTask(
        task_id=f"shadow:{case.case_id}",
        task_type="AAA_COMPLETION_WITNESS_SHADOW",
        expected_effect="Resolve a previously pending owner/provider completion dependency.",
        continuation_action="Continue the safe executable lane when policy permits.",
        witness_modes=(WitnessMode.PROVIDER_READBACK, WitnessMode.USER_ASSERTION),
        continuation_class=case.continuation_class,
        provider="openai",
        require_provider_verification_for_terminal_claim=True,
    )


def _baseline_would_prompt(case: ShadowCase) -> bool:
    """Pre-gene baseline: only independent provider proof clears the pending blocker."""
    provider_verified = any(
        obs.success and obs.witness_mode is WitnessMode.PROVIDER_READBACK
        for obs in case.observations
    )
    return not provider_verified


def run_home_shadow(policy: HomePolicy, cases: Sequence[ShadowCase]) -> HomeCanaryResult:
    adapter = CompletionWitnessHomeAdapter(policy)
    redundant_baseline = 0
    redundant_candidate = 0
    unsafe = 0
    blocked_safe = 0
    false_terminal = 0
    provider_verified = 0
    owner_resumes = 0
    alpha2_blocks = 0

    for case in cases:
        task = _task(case)
        result = adapter.reconcile(task, case.claim_class, case.observations)
        baseline_prompt = _baseline_would_prompt(case)
        if baseline_prompt and case.expected_may_continue:
            redundant_baseline += 1
        if not result["may_continue"] and case.expected_may_continue:
            redundant_candidate += 1
            blocked_safe += 1
        if result["may_continue"] and not case.expected_may_continue:
            unsafe += 1
        if result["may_make_terminal_provider_claim"] and not case.expected_terminal_provider_claim:
            false_terminal += 1
        if result["state"] is TaskCompletionState.PROVIDER_VERIFIED_COMPLETED:
            provider_verified += 1
        if result["state"] is TaskCompletionState.OWNER_ASSERTED_COMPLETED and result["may_continue"]:
            owner_resumes += 1
        if result["alpha2_scope_block"]:
            alpha2_blocks += 1

    total = max(1, len(cases))
    baseline_vector = IntelligenceDensityVector(
        outcome_quality=1.0 - (redundant_baseline / total),
        reliability=1.0,
        reuse=0.0,
        learning=0.0,
        cost=0.05,
        complexity=0.05,
        latency=redundant_baseline / total,
        owner_burden=redundant_baseline / total,
    )
    candidate_vector = IntelligenceDensityVector(
        outcome_quality=1.0 - ((unsafe + blocked_safe) / total),
        reliability=1.0 - ((unsafe + false_terminal) / total),
        reuse=1.0,
        learning=1.0 if alpha2_blocks else 0.5,
        cost=0.12,
        complexity=0.10,
        latency=redundant_candidate / total,
        owner_burden=redundant_candidate / total,
    )
    comparison = compare_intelligence_density(baseline_vector, candidate_vector)
    metrics = HomeRunMetrics(
        system_id=policy.system_id,
        total_cases=len(cases),
        redundant_owner_prompts_baseline=redundant_baseline,
        redundant_owner_prompts_candidate=redundant_candidate,
        unsafe_continuations=unsafe,
        blocked_safe_continuations=blocked_safe,
        false_terminal_provider_claims=false_terminal,
        provider_verified_completions=provider_verified,
        owner_asserted_safe_resumes=owner_resumes,
        alpha2_scope_blocks=alpha2_blocks,
    )
    no_material_regression = unsafe == 0 and false_terminal == 0 and blocked_safe == 0
    return HomeCanaryResult(
        system_id=policy.system_id,
        metrics=metrics,
        intelligence_density=comparison,
        no_material_regression=no_material_regression,
    )


def run_default_completion_witness_aaa_canary(
    homes: Sequence[str] = ("CHATGOV", "EVIDENCEOPS", "TRUTHGRID"),
) -> CompletionWitnessAAACanaryReceipt:
    cases = default_shadow_cases()
    results = tuple(run_home_shadow(HOME_POLICIES[home], cases) for home in homes)
    passed = all(
        result.no_material_regression and result.intelligence_density.delta > 0.0
        for result in results
    )
    feedback_homes = tuple(
        result.system_id for result in results if result.metrics.alpha2_scope_blocks > 0
    )
    feedback = "CLAIM_CLASS_SEPARATION"
    return CompletionWitnessAAACanaryReceipt(
        capability_id="GENE-COMPLETION-WITNESS-AAA-001",
        source_system="CHATBRIDGE",
        candidate_homes=tuple(homes),
        home_results=results,
        feedback_improvement=feedback,
        feedback_source_homes=feedback_homes,
        redistributed_to=tuple(homes) if passed else (),
        status="SHADOW_VALIDATED" if passed else "SHADOW_FAILED",
        proof_scope="DETERMINISTIC_SYNTHETIC_WORKLOAD_ONLY_NOT_PROVIDER_RUNTIME",
        external_effect=False,
    )


__all__ = [
    "ClaimClass",
    "CompletionWitnessAAACanaryReceipt",
    "CompletionWitnessHomeAdapter",
    "HOME_POLICIES",
    "HomeCanaryResult",
    "HomePolicy",
    "IntelligenceDensityComparison",
    "IntelligenceDensityVector",
    "ShadowCase",
    "compare_intelligence_density",
    "default_shadow_cases",
    "run_default_completion_witness_aaa_canary",
    "run_home_shadow",
]
