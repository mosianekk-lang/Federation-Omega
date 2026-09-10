"""CFBE Prompt Scientist v1.

A bounded orchestration-layer optimizer. It evaluates prompt/instruction
variants from measured execution evidence and may recommend promotion or
rollback. It cannot retrain model weights or weaken constitutional controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable, Mapping

from .cfbe_prompt_compiler_v4 import CONSTITUTIONAL_INVARIANTS, CompilerError


SCHEMA = "CFBE-PROMPT-SCIENTIST-V1"
VERSION = "1.0.0"

SCORE_WEIGHTS: Mapping[str, int] = {
    "completion": 25,
    "correctness": 20,
    "proof": 15,
    "execution_efficiency": 10,
    "parallel_utilization": 10,
    "owner_burden": 5,
    "recovery": 5,
    "context_efficiency": 5,
    "creative_freedom": 5,
}

MISSION_PROFILES = frozenset(
    {
        "BUILD",
        "DEBUG",
        "REFACTOR",
        "RESEARCH",
        "CFBE_HARVEST",
        "SECURITY",
        "TEST",
        "DEPLOY",
        "INCIDENT_RECOVERY",
        "PROVIDER_INTEGRATION",
        "DOCUMENT_EVIDENCE",
        "MOBILE",
        "CLOUD",
        "ARCHITECTURE",
    }
)


class Diagnosis(StrEnum):
    INTENT_DILUTION = "INTENT_DILUTION"
    EXECUTION_DILUTION = "EXECUTION_DILUTION"
    CONTEXT_OVERLOAD = "CONTEXT_OVERLOAD"
    MISROUTING = "MISROUTING"
    MISSED_PARALLELISM = "MISSED_PARALLELISM"
    OVER_PARALLELISM = "OVER_PARALLELISM"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    REPEATED_FAILURE = "REPEATED_FAILURE"
    PREMATURE_STOP = "PREMATURE_STOP"
    STATUS_THEATRE = "STATUS_THEATRE"
    PROOF_FAILURE = "PROOF_FAILURE"
    OWNER_BURDEN = "OWNER_BURDEN"
    PROMPT_CONFLICT = "PROMPT_CONFLICT"
    TOOL_UNDERUSE = "TOOL_UNDERUSE"
    TOOL_OVERUSE = "TOOL_OVERUSE"
    LEARNING_FAILURE = "LEARNING_FAILURE"


@dataclass(frozen=True, slots=True)
class PromptRunMetrics:
    prompt_version: str
    mission_class: str
    task_complexity: int = 1
    packets_created: int = 1
    parallelizable_packets: int = 0
    achieved_parallelism: int = 1
    tool_calls: int = 0
    duplicate_tool_calls: int = 0
    retries: int = 0
    owner_interventions: int = 0
    unnecessary_questions: int = 0
    prompt_conflicts: int = 0
    dependency_errors: int = 0
    repeated_failure_fingerprints: int = 0
    context_overflow: bool = False
    premature_stop: bool = False
    status_only_output: bool = False
    unsupported_claims: int = 0
    learning_events_missing: int = 0

    def validate(self) -> "PromptRunMetrics":
        if self.mission_class not in MISSION_PROFILES:
            raise CompilerError("UNKNOWN_MISSION_PROFILE")
        integer_fields = (
            self.task_complexity,
            self.packets_created,
            self.parallelizable_packets,
            self.achieved_parallelism,
            self.tool_calls,
            self.duplicate_tool_calls,
            self.retries,
            self.owner_interventions,
            self.unnecessary_questions,
            self.prompt_conflicts,
            self.dependency_errors,
            self.repeated_failure_fingerprints,
            self.unsupported_claims,
            self.learning_events_missing,
        )
        if any(isinstance(value, bool) or value < 0 for value in integer_fields):
            raise CompilerError("PROMPT_METRICS_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class PromptCandidate:
    candidate_id: str
    mission_profile: str
    parent_version: str
    mutation_plan: tuple[str, ...]
    protected_invariants: frozenset[str] = field(
        default_factory=lambda: CONSTITUTIONAL_INVARIANTS
    )

    def validate(self) -> "PromptCandidate":
        if self.mission_profile not in MISSION_PROFILES:
            raise CompilerError("UNKNOWN_MISSION_PROFILE")
        missing = CONSTITUTIONAL_INVARIANTS - self.protected_invariants
        if missing:
            raise CompilerError(
                "CONSTITUTIONAL_INVARIANT_REGRESSION:" + ",".join(sorted(missing))
            )
        if not self.mutation_plan:
            raise CompilerError("PROMPT_MUTATION_PLAN_REQUIRED")
        return self


@dataclass(frozen=True, slots=True)
class EvaluationDimensions:
    completion: float
    correctness: float
    proof: float
    execution_efficiency: float
    parallel_utilization: float
    owner_burden: float
    recovery: float
    context_efficiency: float
    creative_freedom: float

    def validate(self) -> "EvaluationDimensions":
        for name in SCORE_WEIGHTS:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise CompilerError(f"EVALUATION_{name.upper()}_INVALID")
            if not 0.0 <= float(value) <= 1.0:
                raise CompilerError(f"EVALUATION_{name.upper()}_OUT_OF_RANGE")
        return self

    def score(self) -> float:
        self.validate()
        return round(
            sum(float(getattr(self, name)) * weight for name, weight in SCORE_WEIGHTS.items()),
            3,
        )


@dataclass(frozen=True, slots=True)
class PromptEvaluation:
    candidate_id: str
    dimensions: EvaluationDimensions
    evidence_refs: tuple[str, ...]
    critical_regression: bool = False
    regression_green: bool = True

    @property
    def score(self) -> float:
        return self.dimensions.score()


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    state: str
    selected_candidate_id: str
    incumbent_score: float
    selected_score: float
    delta: float
    reason: str


class PromptScientist:
    @staticmethod
    def diagnose(metrics: PromptRunMetrics) -> tuple[Diagnosis, ...]:
        metrics.validate()
        findings: list[Diagnosis] = []
        if metrics.premature_stop:
            findings.append(Diagnosis.PREMATURE_STOP)
        if metrics.status_only_output:
            findings.append(Diagnosis.STATUS_THEATRE)
        if metrics.unsupported_claims:
            findings.append(Diagnosis.PROOF_FAILURE)
        if metrics.context_overflow:
            findings.append(Diagnosis.CONTEXT_OVERLOAD)
        if metrics.parallelizable_packets >= 2 and metrics.achieved_parallelism <= 1:
            findings.append(Diagnosis.MISSED_PARALLELISM)
        if metrics.parallelizable_packets == 0 and metrics.achieved_parallelism > 1:
            findings.append(Diagnosis.OVER_PARALLELISM)
        if metrics.dependency_errors:
            findings.append(Diagnosis.DEPENDENCY_ERROR)
        if metrics.repeated_failure_fingerprints:
            findings.append(Diagnosis.REPEATED_FAILURE)
        if metrics.duplicate_tool_calls or metrics.retries > max(2, metrics.task_complexity):
            findings.append(Diagnosis.EXECUTION_DILUTION)
        if metrics.duplicate_tool_calls >= 2:
            findings.append(Diagnosis.TOOL_OVERUSE)
        if metrics.tool_calls == 0 and metrics.task_complexity >= 3:
            findings.append(Diagnosis.TOOL_UNDERUSE)
        if metrics.owner_interventions or metrics.unnecessary_questions:
            findings.append(Diagnosis.OWNER_BURDEN)
        if metrics.prompt_conflicts:
            findings.append(Diagnosis.PROMPT_CONFLICT)
        if metrics.learning_events_missing:
            findings.append(Diagnosis.LEARNING_FAILURE)
        return tuple(dict.fromkeys(findings))

    @staticmethod
    def generate_challengers(
        metrics: PromptRunMetrics, diagnoses: Iterable[Diagnosis]
    ) -> tuple[PromptCandidate, ...]:
        metrics.validate()
        diagnoses = tuple(dict.fromkeys(diagnoses))
        base = metrics.prompt_version
        minimum = ["PRESERVE_CONSTITUTION", "APPLY_SMALLEST_CAUSAL_CORRECTION"]
        performance = [
            "PRESERVE_CONSTITUTION",
            "COMPILE_TO_DEPENDENCY_DAG",
            "MAXIMIZE_USEFUL_COLLISION_SAFE_PARALLELISM",
            "MINIMIZE_OWNER_INTERRUPTION",
        ]
        structural = [
            "PRESERVE_CONSTITUTION",
            "SPLIT_COMMON_KERNEL_FROM_MISSION_SPECIALIST",
            "MOVE_DETERMINISTIC_RULES_TO_TESTS_AND_HOOKS",
            "USE_EVALUATOR_GATED_PROMOTION_WITH_ROLLBACK",
        ]
        if Diagnosis.PROOF_FAILURE in diagnoses:
            minimum.append("REQUIRE_PROOF_LADDER_BEFORE_TERMINAL_CLAIM")
            performance.append("FALSIFY_SUCCESS_BEFORE_PROMOTION")
        if Diagnosis.REPEATED_FAILURE in diagnoses:
            minimum.append("OPEN_CIRCUIT_AFTER_REPEATED_FINGERPRINT")
            performance.append("FORCE_MATERIALLY_DIFFERENT_ROUTE")
        if Diagnosis.CONTEXT_OVERLOAD in diagnoses:
            performance.append("MERGE_SUMMARY_AND_PROOF_POINTERS_ONLY")
            structural.append("SPECIALIZE_CONTEXT_BY_MISSION_PROFILE")
        if Diagnosis.MISSED_PARALLELISM in diagnoses:
            performance.append("FAN_OUT_INDEPENDENT_PACKETS_AND_FAN_IN_ON_PROOF")
        if Diagnosis.OWNER_BURDEN in diagnoses:
            minimum.append("DO_NOT_ASK_WHAT_AUTHORIZED_TOOLS_CAN_RESOLVE")
        return (
            PromptCandidate(f"{base}-P1", metrics.mission_class, base, tuple(minimum)),
            PromptCandidate(f"{base}-P2", metrics.mission_class, base, tuple(performance)),
            PromptCandidate(f"{base}-P3", metrics.mission_class, base, tuple(structural)),
        )

    @staticmethod
    def select_for_promotion(*, incumbent: PromptEvaluation, challengers: Iterable[tuple[PromptCandidate, PromptEvaluation]], minimum_score_delta: float = 3.0) -> PromotionDecision:
        if not incumbent.evidence_refs:
            raise CompilerError("INCUMBENT_EVIDENCE_REQUIRED")
        incumbent_score = incumbent.score
        eligible: list[tuple[PromptCandidate, PromptEvaluation]] = []
        for candidate, evaluation in challengers:
            candidate.validate()
            if candidate.candidate_id != evaluation.candidate_id:
                raise CompilerError("CANDIDATE_EVALUATION_ID_MISMATCH")
            if not evaluation.evidence_refs or evaluation.critical_regression or not evaluation.regression_green:
                continue
            if evaluation.score >= incumbent_score + minimum_score_delta:
                eligible.append((candidate, evaluation))
        if not eligible:
            return PromotionDecision("PROMPT_RETAINED", incumbent.candidate_id, incumbent_score, incumbent_score, 0.0, "NO_CHALLENGER_CLEARED_MEASURED_PROMOTION_GATE")
        candidate, evaluation = max(eligible, key=lambda item: (item[1].score, item[0].candidate_id))
        return PromotionDecision("PROMPT_PROMOTED", candidate.candidate_id, incumbent_score, evaluation.score, round(evaluation.score - incumbent_score, 3), "MEASURED_GAIN_WITH_GREEN_REGRESSION_AND_INVARIANTS_PRESERVED")


def score_weight_total() -> int:
    return sum(SCORE_WEIGHTS.values())
