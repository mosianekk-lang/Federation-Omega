from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence


class BenchmarkDimension(str, Enum):
    DIRECTOR_EXPERIENCE = "DIRECTOR_EXPERIENCE"
    MULTISTEP_ORCHESTRATION = "MULTISTEP_ORCHESTRATION"
    REFERENCE_RECREATION = "REFERENCE_RECREATION"
    MULTIMODAL_GENERATION = "MULTIMODAL_GENERATION"
    PROFESSIONAL_FINISHING = "PROFESSIONAL_FINISHING"
    COLLABORATION_REVIEW = "COLLABORATION_REVIEW"
    CROSS_CHANNEL_PACKAGING = "CROSS_CHANNEL_PACKAGING"
    TOOL_ROUTING = "TOOL_ROUTING"
    PRIVATE_SOVEREIGNTY = "PRIVATE_SOVEREIGNTY"
    AUTOMATED_RECOVERY = "AUTOMATED_RECOVERY"
    ADAPTIVE_CAPABILITY_CREATION = "ADAPTIVE_CAPABILITY_CREATION"
    PROOF_AND_READBACK = "PROOF_AND_READBACK"
    OWNER_BURDEN = "OWNER_BURDEN"
    TIME_TO_DELIVERABLE = "TIME_TO_DELIVERABLE"
    VALUE_LEARNING = "VALUE_LEARNING"


class AmbitionClass(str, Enum):
    MATCH_FRONTIER = "MATCH_FRONTIER"
    FRONTIER_PLUS = "FRONTIER_PLUS"
    TEN_X = "TEN_X"


class MetaEvolutionState(str, Enum):
    HOLD_NO_FRONTIER_EVIDENCE = "HOLD_NO_FRONTIER_EVIDENCE"
    HOLD_SCIENTIST_NOT_PREREGISTERED = "HOLD_SCIENTIST_NOT_PREREGISTERED"
    HOLD_CRITICAL_REGRESSION = "HOLD_CRITICAL_REGRESSION"
    SOURCE_EXPERIMENT_READY = "SOURCE_EXPERIMENT_READY"
    HOLD_CI_UNPROVEN = "HOLD_CI_UNPROVEN"
    HOLD_PROVIDER_READBACK_UNPROVEN = "HOLD_PROVIDER_READBACK_UNPROVEN"
    HOLD_REPEATED_SUCCESS_UNPROVEN = "HOLD_REPEATED_SUCCESS_UNPROVEN"
    HOLD_VALUE_UNPROVEN = "HOLD_VALUE_UNPROVEN"
    PROMOTION_CANDIDATE = "PROMOTION_CANDIDATE"


DEFAULT_FRONTIER_SUITES = (
    "ADOBE_CREATIVE_CLOUD_FIREFLY",
    "CANVA_MAGIC_STUDIO",
    "RUNWAY",
    "DAVINCI_RESOLVE",
    "DESCRIPT",
)


@dataclass(frozen=True, slots=True)
class FrontierObservation:
    observation_id: str
    suite_id: str
    dimension: BenchmarkDimension
    capability_score: float
    evidence_ref: str
    checked_at: str
    fresh: bool = True

    def __post_init__(self) -> None:
        if not self.observation_id.strip():
            raise ValueError("observation_id is required")
        if not self.suite_id.strip():
            raise ValueError("suite_id is required")
        if not 0.0 <= float(self.capability_score) <= 5.0:
            raise ValueError("capability_score must be in [0, 5]")
        if not self.evidence_ref.strip():
            raise ValueError("public evidence_ref is required")
        if not self.checked_at.strip():
            raise ValueError("checked_at is required")


@dataclass(frozen=True, slots=True)
class CompositeFrontierPoint:
    dimension: BenchmarkDimension
    frontier_score: float
    suite_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SovaraDimensionState:
    dimension: BenchmarkDimension
    architecture_score: float
    proof_adjusted_score: float
    proof_state: str

    def __post_init__(self) -> None:
        for name in ("architecture_score", "proof_adjusted_score"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 5.0:
                raise ValueError(f"{name} must be in [0, 5]")
        if self.proof_adjusted_score > self.architecture_score:
            raise ValueError("proof_adjusted_score cannot exceed architecture_score")
        if not self.proof_state.strip():
            raise ValueError("proof_state is required")


@dataclass(frozen=True, slots=True)
class FrontierGap:
    dimension: BenchmarkDimension
    frontier_score: float
    architecture_score: float
    proof_adjusted_score: float
    architecture_gap: float
    operational_gap: float
    ambition: AmbitionClass
    frontier_evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TenXTarget:
    metric: str
    baseline: float
    target: float
    higher_is_better: bool
    multiplier: float = 10.0

    @property
    def met_by(self):
        def _met(value: float) -> bool:
            return float(value) >= self.target if self.higher_is_better else float(value) <= self.target
        return _met


@dataclass(frozen=True, slots=True)
class ScientistHypothesis:
    hypothesis_id: str
    statement: str
    predictions: tuple[str, ...]
    falsifiers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OmegaScientistExperiment:
    experiment_id: str
    dimension: BenchmarkDimension
    primary_metric: str
    hypotheses: tuple[ScientistHypothesis, ...]
    benchmark_ids: tuple[str, ...]
    rollback_condition: str
    ambition: AmbitionClass
    ten_x_target: TenXTarget | None
    authority_ceiling: str
    external_effect: bool
    preregistration_sha256: str


@dataclass(frozen=True, slots=True)
class EvolutionEvidence:
    benchmark_refs: tuple[str, ...]
    scientist_preregistered: bool
    deterministic_tests_passed: bool
    ci_admitted: bool
    provider_effect_required: bool
    provider_native_readback: bool
    repeated_success: bool
    value_gain_verified: bool
    critical_regression: bool = False


def _digest(value: object) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(body.encode("utf-8")).hexdigest()


def compile_best_of_breed_frontier(
    observations: Iterable[FrontierObservation],
) -> tuple[CompositeFrontierPoint, ...]:
    """Build a composite frontier from the strongest fresh public evidence per dimension.

    CFBE meta benchmarking compares SOVARA Creative to the best observed capability
    across relevant suites, never to a vendor average. Stale observations are ignored
    rather than silently reused.
    """

    grouped: dict[BenchmarkDimension, list[FrontierObservation]] = {}
    for observation in observations:
        if observation.fresh:
            grouped.setdefault(observation.dimension, []).append(observation)

    points: list[CompositeFrontierPoint] = []
    for dimension, rows in grouped.items():
        best = max(float(row.capability_score) for row in rows)
        leaders = [row for row in rows if float(row.capability_score) == best]
        points.append(
            CompositeFrontierPoint(
                dimension=dimension,
                frontier_score=best,
                suite_ids=tuple(sorted({row.suite_id for row in leaders})),
                evidence_refs=tuple(sorted({row.evidence_ref for row in leaders})),
            )
        )
    return tuple(sorted(points, key=lambda item: item.dimension.value))


def choose_ambition(
    *,
    dimension: BenchmarkDimension,
    quantifiable_ratio_metric: bool,
    material_gap: bool,
) -> AmbitionClass:
    """Choose a truthful ambition instead of applying fake '10x' to every metric."""

    if quantifiable_ratio_metric and material_gap:
        return AmbitionClass.TEN_X
    if material_gap:
        return AmbitionClass.FRONTIER_PLUS
    return AmbitionClass.MATCH_FRONTIER


def calculate_frontier_gaps(
    *,
    frontier: Sequence[CompositeFrontierPoint],
    sovara: Sequence[SovaraDimensionState],
    ratio_dimensions: Iterable[BenchmarkDimension] = (),
) -> tuple[FrontierGap, ...]:
    current = {item.dimension: item for item in sovara}
    ratio_set = set(ratio_dimensions)
    gaps: list[FrontierGap] = []
    for point in frontier:
        state = current.get(point.dimension)
        if state is None:
            architecture = 0.0
            proof_adjusted = 0.0
        else:
            architecture = float(state.architecture_score)
            proof_adjusted = float(state.proof_adjusted_score)
        architecture_gap = max(0.0, point.frontier_score - architecture)
        operational_gap = max(0.0, point.frontier_score - proof_adjusted)
        gaps.append(
            FrontierGap(
                dimension=point.dimension,
                frontier_score=point.frontier_score,
                architecture_score=architecture,
                proof_adjusted_score=proof_adjusted,
                architecture_gap=architecture_gap,
                operational_gap=operational_gap,
                ambition=choose_ambition(
                    dimension=point.dimension,
                    quantifiable_ratio_metric=point.dimension in ratio_set,
                    material_gap=operational_gap > 0.0,
                ),
                frontier_evidence_refs=point.evidence_refs,
            )
        )
    return tuple(sorted(gaps, key=lambda item: (-item.operational_gap, item.dimension.value)))


def build_ten_x_target(
    *,
    metric: str,
    baseline: float,
    higher_is_better: bool,
    multiplier: float = 10.0,
) -> TenXTarget:
    name = metric.strip()
    base = float(baseline)
    mult = float(multiplier)
    if not name:
        raise ValueError("metric is required")
    if base <= 0:
        raise ValueError("10x ratio target requires a positive measured baseline")
    if mult < 10.0:
        raise ValueError("SOVARA Creative meta-evolution uses 10x or greater when a ratio target is invoked")
    target = base * mult if higher_is_better else base / mult
    return TenXTarget(name, base, target, higher_is_better, mult)


def preregister_omega_scientist_experiment(
    *,
    experiment_id: str,
    dimension: BenchmarkDimension,
    primary_metric: str,
    hypotheses: Sequence[ScientistHypothesis],
    benchmark_ids: Sequence[str],
    rollback_condition: str,
    ambition: AmbitionClass,
    ten_x_target: TenXTarget | None = None,
) -> OmegaScientistExperiment:
    """Create a falsifiable, rollback-bound experiment for the Ω-Scientist lane.

    The experiment is internal proposal authority only. It cannot mutate production,
    widen permissions, deploy code or claim provider success.
    """

    eid = experiment_id.strip()
    metric = primary_metric.strip()
    rollback = rollback_condition.strip()
    if not eid or not metric or not rollback:
        raise ValueError("experiment_id, primary_metric and rollback_condition are required")
    if len(hypotheses) < 2:
        raise ValueError("Omega Scientist material experiments require competing hypotheses")
    if not benchmark_ids:
        raise ValueError("at least one frontier benchmark is required")
    ids = [item.hypothesis_id for item in hypotheses]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate hypothesis_id")
    for hypothesis in hypotheses:
        if not hypothesis.statement.strip():
            raise ValueError("hypothesis statement is required")
        if not hypothesis.predictions:
            raise ValueError(f"{hypothesis.hypothesis_id} requires predictions")
        if not hypothesis.falsifiers:
            raise ValueError(f"{hypothesis.hypothesis_id} requires falsifiers")
    if ambition is AmbitionClass.TEN_X and ten_x_target is None:
        raise ValueError("TEN_X experiment requires a measured TenXTarget")

    payload = {
        "experiment_id": eid,
        "dimension": dimension.value,
        "primary_metric": metric,
        "hypotheses": [
            {
                "hypothesis_id": h.hypothesis_id,
                "statement": h.statement,
                "predictions": h.predictions,
                "falsifiers": h.falsifiers,
            }
            for h in hypotheses
        ],
        "benchmark_ids": tuple(benchmark_ids),
        "rollback_condition": rollback,
        "ambition": ambition.value,
        "ten_x_target": ten_x_target,
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
    }
    return OmegaScientistExperiment(
        experiment_id=eid,
        dimension=dimension,
        primary_metric=metric,
        hypotheses=tuple(hypotheses),
        benchmark_ids=tuple(benchmark_ids),
        rollback_condition=rollback,
        ambition=ambition,
        ten_x_target=ten_x_target,
        authority_ceiling="A1_INTERNAL",
        external_effect=False,
        preregistration_sha256=_digest(payload),
    )


def evaluate_meta_evolution(evidence: EvolutionEvidence) -> MetaEvolutionState:
    """Fail closed from benchmark idea through production/value promotion."""

    if not evidence.benchmark_refs:
        return MetaEvolutionState.HOLD_NO_FRONTIER_EVIDENCE
    if not evidence.scientist_preregistered:
        return MetaEvolutionState.HOLD_SCIENTIST_NOT_PREREGISTERED
    if evidence.critical_regression:
        return MetaEvolutionState.HOLD_CRITICAL_REGRESSION
    if not evidence.deterministic_tests_passed:
        return MetaEvolutionState.SOURCE_EXPERIMENT_READY
    if not evidence.ci_admitted:
        return MetaEvolutionState.HOLD_CI_UNPROVEN
    if evidence.provider_effect_required and not evidence.provider_native_readback:
        return MetaEvolutionState.HOLD_PROVIDER_READBACK_UNPROVEN
    if not evidence.repeated_success:
        return MetaEvolutionState.HOLD_REPEATED_SUCCESS_UNPROVEN
    if not evidence.value_gain_verified:
        return MetaEvolutionState.HOLD_VALUE_UNPROVEN
    return MetaEvolutionState.PROMOTION_CANDIDATE
