from __future__ import annotations

"""Ω-CIVILIZATION capability compounding, anti-entropy and succession."""

from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from .contracts import CivitasError, FitnessVector, digest, safe_id
from .metabolism import EntropyAssessment, FeatureRent, FederationMetabolism


class CompoundingStage(str, Enum):
    NEED = "NEED"
    DISCOVER = "DISCOVER"
    COMPOSE = "COMPOSE"
    BUILD = "BUILD"
    TEST = "TEST"
    SHADOW = "SHADOW"
    MEASURE = "MEASURE"
    GENERALIZE = "GENERALIZE"
    DIFFUSE = "DIFFUSE"
    IMPROVE_IMPROVEMENT = "IMPROVE_IMPROVEMENT"
    CLOSED_VERIFIED = "CLOSED_VERIFIED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"


COMPOUNDING_ORDER = (
    CompoundingStage.NEED,
    CompoundingStage.DISCOVER,
    CompoundingStage.COMPOSE,
    CompoundingStage.BUILD,
    CompoundingStage.TEST,
    CompoundingStage.SHADOW,
    CompoundingStage.MEASURE,
    CompoundingStage.GENERALIZE,
    CompoundingStage.DIFFUSE,
    CompoundingStage.IMPROVE_IMPROVEMENT,
    CompoundingStage.CLOSED_VERIFIED,
)
COMPOUNDING_RANK = {stage: index for index, stage in enumerate(COMPOUNDING_ORDER)}


@dataclass(frozen=True)
class CompoundingCycle:
    cycle_id: str
    need: str
    stage: CompoundingStage
    capability_ids: tuple[str, ...]
    proof_refs: tuple[str, ...]
    rollback_ready: bool = False
    regression_passed: bool = False
    independent_assurance: bool = False
    measured_value: float | None = None
    generalized_gene_ref: str = ""
    receiver_proof_refs: tuple[str, ...] = ()
    improvement_mechanism_proof: str = ""
    external_effects: int = 0

    def validate(self) -> "CompoundingCycle":
        safe_id(self.cycle_id, "cycle_id")
        if not self.need.strip() or not self.proof_refs:
            raise ValueError("cycle need and proof required")
        if self.external_effects:
            raise CivitasError("compounding cycle cannot execute external effects")
        return self


@dataclass(frozen=True)
class AntiEntropyReport:
    cycle_id: str
    baseline: FitnessVector
    candidate: FitnessVector
    capability_gain: float
    complexity_delta: float
    owner_load_delta: float
    harmonic_delta: float
    hard_veto_pass: bool
    disposition: str
    material_regressions: tuple[str, ...]
    external_effects: int = 0

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True)
class SuccessionPlan:
    plan_id: str
    predecessor_id: str
    successor_id: str
    archive_refs: tuple[str, ...]
    rollback_refs: tuple[str, ...]
    successor_proof_refs: tuple[str, ...]
    shadow_passed: bool
    independent_assurance: bool
    value_positive: bool
    rollback_passed: bool
    observation_window_complete: bool
    predecessor_deletion_permitted: bool = False
    external_effects: int = 0

    def validate(self) -> "SuccessionPlan":
        safe_id(self.plan_id, "plan_id")
        safe_id(self.predecessor_id, "predecessor_id")
        safe_id(self.successor_id, "successor_id")
        if self.predecessor_id == self.successor_id:
            raise ValueError("predecessor and successor must differ")
        if not self.archive_refs or not self.rollback_refs or not self.successor_proof_refs:
            raise ValueError("archive, rollback and successor proof required")
        if self.predecessor_deletion_permitted or self.external_effects:
            raise CivitasError("succession is archive-first and cannot delete or execute")
        return self


@dataclass(frozen=True)
class SuccessionDecision:
    plan_id: str
    disposition: str
    serving_cutover_eligible: bool
    predecessor_retirement_eligible: bool
    archive_first: bool
    deletion_permitted: bool
    explanation: str
    proof_refs: tuple[str, ...]
    external_effects: int = 0


class CivilizationFabric:
    """Closed capability-compounding loop with anti-entropy and succession."""

    def __init__(self) -> None:
        self._cycles: dict[str, CompoundingCycle] = {}

    def open_cycle(self, cycle_id: str, need: str, proof_refs: Sequence[str]) -> CompoundingCycle:
        cycle = CompoundingCycle(
            cycle_id,
            need,
            CompoundingStage.NEED,
            (),
            tuple(dict.fromkeys(str(item) for item in proof_refs)),
        ).validate()
        existing = self._cycles.get(cycle_id)
        if existing is not None and existing != cycle:
            raise CivitasError("compounding cycle id collision")
        self._cycles[cycle_id] = cycle
        return cycle

    def cycle(self, cycle_id: str) -> CompoundingCycle:
        if cycle_id not in self._cycles:
            raise CivitasError("unknown compounding cycle")
        return self._cycles[cycle_id]

    def advance(
        self,
        cycle_id: str,
        target: CompoundingStage,
        *,
        proof_refs: Sequence[str],
        capability_ids: Sequence[str] | None = None,
        rollback_ready: bool | None = None,
        regression_passed: bool | None = None,
        independent_assurance: bool | None = None,
        measured_value: float | None = None,
        generalized_gene_ref: str | None = None,
        receiver_proof_refs: Sequence[str] | None = None,
        improvement_mechanism_proof: str | None = None,
        authority_expansion: bool = False,
    ) -> CompoundingCycle:
        current = self.cycle(cycle_id).validate()
        if authority_expansion:
            raise CivitasError("compounding cannot manufacture authority")
        if target in {CompoundingStage.REJECTED, CompoundingStage.QUARANTINED}:
            updated = replace(
                current,
                stage=target,
                proof_refs=tuple(dict.fromkeys(current.proof_refs + tuple(proof_refs))),
            )
            self._cycles[cycle_id] = updated
            return updated
        if current.stage not in COMPOUNDING_RANK or target not in COMPOUNDING_RANK:
            raise CivitasError("unsupported compounding transition")
        if COMPOUNDING_RANK[target] != COMPOUNDING_RANK[current.stage] + 1:
            raise CivitasError("compounding stage skipping/backward transition blocked")
        if not proof_refs:
            raise ValueError("compounding transition requires proof")
        capabilities = current.capability_ids if capability_ids is None else tuple(dict.fromkeys(capability_ids))
        rollback = current.rollback_ready if rollback_ready is None else rollback_ready
        regression = current.regression_passed if regression_passed is None else regression_passed
        assurance = current.independent_assurance if independent_assurance is None else independent_assurance
        value = current.measured_value if measured_value is None else measured_value
        gene = current.generalized_gene_ref if generalized_gene_ref is None else generalized_gene_ref
        receiver_refs = current.receiver_proof_refs if receiver_proof_refs is None else tuple(dict.fromkeys(receiver_proof_refs))
        improvement_ref = current.improvement_mechanism_proof if improvement_mechanism_proof is None else improvement_mechanism_proof
        if target in {CompoundingStage.COMPOSE, CompoundingStage.BUILD} and not capabilities:
            raise CivitasError("compose/build requires capability identities")
        if target == CompoundingStage.TEST and not regression:
            raise CivitasError("test stage requires regression proof")
        if target == CompoundingStage.SHADOW and not rollback:
            raise CivitasError("shadow stage requires rollback readiness")
        if target == CompoundingStage.MEASURE and (value is None or value <= 0 or not assurance):
            raise CivitasError("measure stage requires positive value and independent assurance")
        if target == CompoundingStage.GENERALIZE and not gene:
            raise CivitasError("generalize stage requires sanitized gene reference")
        if target == CompoundingStage.DIFFUSE and not receiver_refs:
            raise CivitasError("diffuse stage requires receiver-local proof references")
        if target == CompoundingStage.IMPROVE_IMPROVEMENT and not improvement_ref:
            raise CivitasError("improvement-mechanism stage requires proof")
        if target == CompoundingStage.CLOSED_VERIFIED and not (
            rollback and regression and assurance and value is not None and value > 0 and gene and receiver_refs and improvement_ref
        ):
            raise CivitasError("closed loop requires rollback, regression, assurance, value, generalization, diffusion and meta-improvement proof")
        updated = replace(
            current,
            stage=target,
            proof_refs=tuple(dict.fromkeys(current.proof_refs + tuple(proof_refs))),
            capability_ids=capabilities,
            rollback_ready=rollback,
            regression_passed=regression,
            independent_assurance=assurance,
            measured_value=value,
            generalized_gene_ref=gene,
            receiver_proof_refs=receiver_refs,
            improvement_mechanism_proof=improvement_ref,
        ).validate()
        self._cycles[cycle_id] = updated
        return updated

    @staticmethod
    def anti_entropy_gate(
        cycle_id: str,
        baseline: FitnessVector,
        candidate: FitnessVector,
        *,
        regression_tolerance: float = 0.08,
    ) -> AntiEntropyReport:
        safe_id(cycle_id, "cycle_id")
        baseline.validate()
        candidate.validate()
        if not 0 <= regression_tolerance <= 1:
            raise ValueError("regression_tolerance must be in [0,1]")
        protected = ("truth", "proof", "safety", "privacy", "owner_control", "continuity", "resilience")
        regressions = tuple(
            name for name in protected
            if getattr(candidate, name) + regression_tolerance < getattr(baseline, name)
        )
        capability_gain = round(
            (
                candidate.quality + candidate.learning + candidate.resilience
                - baseline.quality - baseline.learning - baseline.resilience
            ) / 3,
            8,
        )
        complexity_delta = round(candidate.complexity - baseline.complexity, 8)
        owner_load_delta = round(candidate.owner_load - baseline.owner_load, 8)
        harmonic_delta = round(candidate.harmonic_score - baseline.harmonic_score, 8)
        hard_veto = candidate.hard_veto_pass and not regressions
        compounding_positive = capability_gain > 0 and harmonic_delta >= -regression_tolerance and complexity_delta < capability_gain + 0.10
        disposition = "PASS_ANTI_ENTROPY" if hard_veto and compounding_positive else "HOLD_COMPLEXITY_OR_REGRESSION"
        return AntiEntropyReport(
            cycle_id,
            baseline,
            candidate,
            capability_gain,
            complexity_delta,
            owner_load_delta,
            harmonic_delta,
            hard_veto,
            disposition,
            regressions,
        )

    @staticmethod
    def succession(plan: SuccessionPlan) -> SuccessionDecision:
        plan.validate()
        cutover = all((
            plan.shadow_passed,
            plan.independent_assurance,
            plan.value_positive,
            plan.rollback_passed,
        ))
        retirement = cutover and plan.observation_window_complete
        if not cutover:
            disposition = "HOLD_SUCCESSOR_IN_SHADOW"
            explanation = "successor lacks shadow, assurance, value or rollback proof"
        elif not plan.observation_window_complete:
            disposition = "CUTOVER_ELIGIBLE_RETAIN_PREDECESSOR"
            explanation = "successor may be proposed for reversible cutover; predecessor remains during observation"
        else:
            disposition = "ARCHIVE_AND_RETIREMENT_REVIEW_ELIGIBLE"
            explanation = "observation window passed; archive-first retirement may be separately authorized"
        refs = tuple(sorted(set(plan.archive_refs + plan.rollback_refs + plan.successor_proof_refs)))
        return SuccessionDecision(
            plan.plan_id,
            disposition,
            cutover,
            retirement,
            True,
            False,
            explanation,
            refs,
        )

    @staticmethod
    def feature_rent(feature: FeatureRent) -> EntropyAssessment:
        return FederationMetabolism.feature_rent(feature)

    def closure_receipt(self, cycle_id: str) -> Mapping[str, Any]:
        cycle = self.cycle(cycle_id)
        if cycle.stage != CompoundingStage.CLOSED_VERIFIED:
            raise CivitasError("compounding cycle is not closed verified")
        body = {
            "cycle": asdict(cycle),
            "capability_compounding_loop_closed": True,
            "provider_execution_performed": False,
            "authority_created": False,
            "external_effects": 0,
        }
        return {**body, "receipt_sha256": digest(body)}


__all__ = [
    "CompoundingStage", "CompoundingCycle", "AntiEntropyReport",
    "SuccessionPlan", "SuccessionDecision", "CivilizationFabric",
]
