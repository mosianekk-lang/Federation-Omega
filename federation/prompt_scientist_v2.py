"""CFBE Prompt Scientist v2: telemetry-backed prompt-gene evolution."""
from __future__ import annotations


from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Callable, Iterable, Mapping, Sequence


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


IMMUTABLE_GENES = frozenset({
    "OWNER_AUTHORITY", "PROOF_FLOOR", "SECURITY_FLOOR", "PRIVACY_FLOOR",
    "TRUTH_BOUNDARIES", "PROVIDER_NATIVE_PROOF", "ROLLBACK_REQUIREMENTS"
})




class Diagnosis(StrEnum):
    INTENT_DILUTION="INTENT_DILUTION"; EXECUTION_DILUTION="EXECUTION_DILUTION"; CONTEXT_OVERLOAD="CONTEXT_OVERLOAD"
    MISROUTING="MISROUTING"; MISSED_PARALLELISM="MISSED_PARALLELISM"; OVER_PARALLELISM="OVER_PARALLELISM"
    DEPENDENCY_ERROR="DEPENDENCY_ERROR"; REPEATED_FAILURE="REPEATED_FAILURE"; PREMATURE_STOP="PREMATURE_STOP"
    STATUS_THEATRE="STATUS_THEATRE"; PROOF_FAILURE="PROOF_FAILURE"; OWNER_BURDEN="OWNER_BURDEN"
    PROMPT_CONFLICT="PROMPT_CONFLICT"; TOOL_UNDERUSE="TOOL_UNDERUSE"; TOOL_OVERUSE="TOOL_OVERUSE"
    LEARNING_FAILURE="LEARNING_FAILURE"; OUTPUT_BOUNDARY_STOP="OUTPUT_BOUNDARY_STOP"; STALE_CONTINUATION="STALE_CONTINUATION"
    MISSING_RUNTIME_REENTRY="MISSING_RUNTIME_REENTRY"; UNNECESSARY_SERIALIZATION="UNNECESSARY_SERIALIZATION"
    COMMERCIAL_MATURITY_GAP="COMMERCIAL_MATURITY_GAP"




@dataclass(frozen=True, slots=True)
class PromptGenome:
    version: str
    parent_version: str
    genes: Mapping[str, str]
    mutation_plan: tuple[str, ...] = ()
    protected_invariants: frozenset[str] = IMMUTABLE_GENES


    def validate(self) -> "PromptGenome":
        if IMMUTABLE_GENES - self.protected_invariants:
            raise ValueError("IMMUTABLE_GENE_REGRESSION")
        if not self.version or not self.genes:
            raise ValueError("PROMPT_GENOME_INVALID")
        return self




@dataclass(frozen=True, slots=True)
class PromptRunMetrics:
    prompt_version: str
    mission_class: str
    completion_ratio: float = 0.0
    correctness: float = 1.0
    proof_completeness: float = 1.0
    execution_efficiency: float = 1.0
    parallelizable_packets: int = 0
    achieved_parallelism: int = 1
    owner_interventions: int = 0
    unnecessary_questions: int = 0
    recovery_success: float = 1.0
    context_efficiency: float = 1.0
    creative_freedom: float = 1.0
    duplicate_tool_calls: int = 0
    retries: int = 0
    dependency_errors: int = 0
    repeated_failure_fingerprints: int = 0
    unsupported_claims: int = 0
    status_only_output: bool = False
    premature_stop: bool = False
    context_overflow: bool = False
    learning_events_missing: int = 0
    output_boundary_stop: bool = False
    stale_continuation: bool = False
    persistent_runner_available: bool = False
    reentry_enqueued: bool = False
    unnecessary_serialization: int = 0
    commercial_maturity_gap: bool = False




@dataclass(frozen=True, slots=True)
class PromptEvaluation:
    candidate_id: str
    dimensions: Mapping[str, float]
    evidence_refs: tuple[str, ...]
    regression_green: bool = True
    critical_regression: bool = False
    commercial_maturity_regression: bool = False


    @property
    def score(self) -> float:
        return round(sum(float(self.dimensions[k]) * w for k, w in SCORE_WEIGHTS.items()), 3)




@dataclass(frozen=True, slots=True)
class PromotionDecision:
    state: str
    selected_candidate_id: str
    incumbent_score: float
    selected_score: float
    delta: float
    reason: str




class PromptScientistV2:
    def diagnose(self, m: PromptRunMetrics) -> tuple[Diagnosis, ...]:
        f: list[Diagnosis] = []
        if m.premature_stop: f.append(Diagnosis.PREMATURE_STOP)
        if m.status_only_output: f.append(Diagnosis.STATUS_THEATRE)
        if m.unsupported_claims: f.append(Diagnosis.PROOF_FAILURE)
        if m.context_overflow: f.append(Diagnosis.CONTEXT_OVERLOAD)
        if m.parallelizable_packets >= 2 and m.achieved_parallelism <= 1: f.append(Diagnosis.MISSED_PARALLELISM)
        if m.parallelizable_packets == 0 and m.achieved_parallelism > 1: f.append(Diagnosis.OVER_PARALLELISM)
        if m.dependency_errors: f.append(Diagnosis.DEPENDENCY_ERROR)
        if m.repeated_failure_fingerprints: f.append(Diagnosis.REPEATED_FAILURE)
        if m.duplicate_tool_calls or m.retries > 2: f.append(Diagnosis.EXECUTION_DILUTION)
        if m.owner_interventions or m.unnecessary_questions: f.append(Diagnosis.OWNER_BURDEN)
        if m.learning_events_missing: f.append(Diagnosis.LEARNING_FAILURE)
        if m.output_boundary_stop: f.append(Diagnosis.OUTPUT_BOUNDARY_STOP)
        if m.stale_continuation: f.append(Diagnosis.STALE_CONTINUATION)
        if m.persistent_runner_available and not m.reentry_enqueued: f.append(Diagnosis.MISSING_RUNTIME_REENTRY)
        if m.unnecessary_serialization: f.append(Diagnosis.UNNECESSARY_SERIALIZATION)
        if m.commercial_maturity_gap: f.append(Diagnosis.COMMERCIAL_MATURITY_GAP)
        return tuple(dict.fromkeys(f))


    def generate_challengers(self, incumbent: PromptGenome, diagnoses: Iterable[Diagnosis]) -> tuple[PromptGenome, ...]:
        incumbent.validate(); diagnoses = tuple(dict.fromkeys(diagnoses))
        base = dict(incumbent.genes)
        def child(suffix: str, mutations: Sequence[str], changes: Mapping[str, str]) -> PromptGenome:
            g = dict(base); g.update(changes)
            return PromptGenome(f"{incumbent.version}-{suffix}", incumbent.version, g, tuple(mutations)).validate()
        p1_changes = {}
        p2_changes = {"DAG_SCHEDULER":"CRITICAL_PATH_PLUS_COLLISION_SAFE_FANOUT", "CONTEXT_COMPILER":"HOT_SET_POINTERS_ONLY"}
        p3_changes = {"OUTPUT_POLICY":"NON_TERMINAL_PROGRESS_CONTINUES", "LEARNING_CALLBACK":"EACH_MATERIAL_CYCLE", "RUNTIME_REENTRY":"PERSIST_OR_RESUME_CAPSULE"}
        if Diagnosis.OUTPUT_BOUNDARY_STOP in diagnoses: p1_changes["OUTPUT_POLICY"] = "NON_TERMINAL_PROGRESS_CONTINUES"
        if Diagnosis.MISSING_RUNTIME_REENTRY in diagnoses: p1_changes["RUNTIME_REENTRY"] = "ENQUEUE_AFTER_CHECKPOINT"
        if Diagnosis.MISSED_PARALLELISM in diagnoses: p2_changes["PARALLELISM_POLICY"] = "MAX_COLLISION_SAFE"
        if Diagnosis.COMMERCIAL_MATURITY_GAP in diagnoses: p2_changes["MATURITY_POLICY"] = "COMMERCIAL_READY_VERIFIED"
        return (
            child("P1", ("MINIMUM_CAUSAL_CORRECTION",), p1_changes),
            child("P2", ("PERFORMANCE_OPTIMIZED",), p2_changes),
            child("P3", ("STRUCTURALLY_DIFFERENT",), p3_changes),
        )


    @staticmethod
    def dimensions_from_metrics(m: PromptRunMetrics) -> dict[str, float]:
        owner = 1.0 / (1.0 + m.owner_interventions + m.unnecessary_questions)
        parallel = 1.0 if m.parallelizable_packets <= 1 else min(1.0, m.achieved_parallelism / max(1, m.parallelizable_packets))
        return {
            "completion": max(0.0, min(1.0, m.completion_ratio)),
            "correctness": max(0.0, min(1.0, m.correctness)),
            "proof": max(0.0, min(1.0, m.proof_completeness)),
            "execution_efficiency": max(0.0, min(1.0, m.execution_efficiency)),
            "parallel_utilization": parallel,
            "owner_burden": owner,
            "recovery": max(0.0, min(1.0, m.recovery_success)),
            "context_efficiency": max(0.0, min(1.0, m.context_efficiency)),
            "creative_freedom": max(0.0, min(1.0, m.creative_freedom)),
        }


    def matched_evaluate(self, genome: PromptGenome, fixtures: Sequence[object], runner: Callable[[PromptGenome, object], PromptRunMetrics], *, evidence_prefix: str) -> PromptEvaluation:
        genome.validate()
        if not fixtures: raise ValueError("MATCHED_FIXTURES_REQUIRED")
        metrics = [runner(genome, f) for f in fixtures]
        dims = {k: sum(self.dimensions_from_metrics(m)[k] for m in metrics)/len(metrics) for k in SCORE_WEIGHTS}
        refs = tuple(f"{evidence_prefix}:{i}" for i in range(len(metrics)))
        critical = any(m.correctness < 1.0 or m.proof_completeness < 1.0 for m in metrics)
        commercial_reg = any(m.commercial_maturity_gap and genome.genes.get("MATURITY_POLICY") == "MVP_ONLY" for m in metrics)
        return PromptEvaluation(genome.version, dims, refs, regression_green=not critical, critical_regression=critical, commercial_maturity_regression=commercial_reg)


    @staticmethod
    def select_for_promotion(incumbent: PromptEvaluation, challengers: Iterable[PromptEvaluation], minimum_score_delta: float = 3.0) -> PromotionDecision:
        eligible = [c for c in challengers if c.evidence_refs and c.regression_green and not c.critical_regression and not c.commercial_maturity_regression and c.score >= incumbent.score + minimum_score_delta]
        if not eligible:
            return PromotionDecision("PROMPT_RETAINED", incumbent.candidate_id, incumbent.score, incumbent.score, 0.0, "NO_CHALLENGER_CLEARED_MEASURED_GATE")
        winner = max(eligible, key=lambda c:(c.score,c.candidate_id))
        return PromotionDecision("PROMPT_PROMOTED", winner.candidate_id, incumbent.score, winner.score, round(winner.score-incumbent.score,3), "MEASURED_GAIN_WITH_GREEN_REGRESSION_AND_COMMERCIAL_FLOORS")
