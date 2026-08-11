from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Mapping, Sequence

from evidenceops.innovation_engine.evolution import EvolutionGovernor

from .federation_capability_twin import CapabilityTwin, TwinState
from .federation_evolution_program import AUTHORITY_CEILING, EvolutionStage, SYSTEM_PROFILES
from .federation_evolution_runtime import FailureMemoryEntry, MissionExecutionState
from .federation_maturity_proof import (
    MaturityProofEnvelope,
    StrictMaturity,
    StrictMaturityDecision,
    StrictMaturityGate,
)


REQUIRED_ATTESTATION_CONTROLS = (
    "NCB-003",
    "CAPABILITY_RESOLUTION_GATE",
    "FEDERATION_EVOLUTION_PROGRAM_V1",
    "FEDERATION_EVOLUTION_RUNTIME_V1",
    "STRICT_MATURITY_GATE",
    "SYSTEM_EVOLUTION_PROFILE",
    "CAPABILITY_DIGITAL_TWIN",
    "ROUTE_AND_FAILURE_MEMORY",
)


class ActivationKind(str, Enum):
    NEW_CHAT = "NEW_CHAT"
    RESTORED_CHAT = "RESTORED_CHAT"
    CURRENT_CHAT = "CURRENT_CHAT"
    NON_CHAT_RUNTIME = "NON_CHAT_RUNTIME"


@dataclass(frozen=True)
class RuntimeAttestation:
    invocation_id: str
    system_id: str
    activation_kind: ActivationKind
    observed_at: str
    current_main_sha: str
    startup_block: str
    loaded_controls: tuple[str, ...]
    private_readback_ref: str
    source_readback_ref: str
    mission_restore_ref: str = ""
    capability_twin_ref: str = ""
    external_effect: bool = False
    authority_ceiling: str = AUTHORITY_CEILING

    def validate(self) -> "RuntimeAttestation":
        if self.system_id not in SYSTEM_PROFILES:
            raise ValueError("runtime attestation system must be registered")
        for value in (
            self.invocation_id,
            self.observed_at,
            self.current_main_sha,
            self.startup_block,
            self.private_readback_ref,
            self.source_readback_ref,
        ):
            if not str(value).strip():
                raise ValueError("runtime attestation has missing required field")
        if self.external_effect or self.authority_ceiling != AUTHORITY_CEILING:
            raise ValueError("runtime attestation cannot expand authority or create external effects")
        return self

    @property
    def missing_controls(self) -> tuple[str, ...]:
        loaded = set(self.loaded_controls)
        return tuple(item for item in REQUIRED_ATTESTATION_CONTROLS if item not in loaded)

    @property
    def qualifies_stage16(self) -> bool:
        self.validate()
        if self.activation_kind not in {ActivationKind.NEW_CHAT, ActivationKind.RESTORED_CHAT, ActivationKind.NON_CHAT_RUNTIME}:
            return False
        if self.missing_controls:
            return False
        if self.activation_kind == ActivationKind.RESTORED_CHAT and not self.mission_restore_ref.strip():
            return False
        if not self.capability_twin_ref.strip():
            return False
        return True


@dataclass(frozen=True)
class RegressionCase:
    regression_id: str
    failure_fingerprint: str
    injected_condition: str
    expected_behavior: str
    prohibited_behavior: str
    proof_source: str
    rollback_required: bool = True

    def validate(self) -> "RegressionCase":
        if not all(
            value.strip()
            for value in (
                self.regression_id,
                self.failure_fingerprint,
                self.injected_condition,
                self.expected_behavior,
                self.prohibited_behavior,
                self.proof_source,
            )
        ):
            raise ValueError("regression case is incomplete")
        return self


class AutonomousRegressionPlanner:
    """Stage 17 planning layer; execution remains in the admitted test/runtime surfaces."""

    behavior_map: Mapping[str, tuple[str, str]] = {
        "INVALID_ARGUMENT_OR_SCHEMA": (
            "discover current schema and retry a corrected or materially different route",
            "declare objective incapability from the invalid call",
        ),
        "STALE_BASE_HEAD_REJECTED": (
            "preserve the rejection, recut from current main, reapply bounded delta and rerun full admission",
            "weaken ancestry enforcement or force the stale branch",
        ),
        "PHOENIX_EXPORT_REGRESSION": (
            "repair implementation or test-contract mismatch and rerun the same Phoenix gate",
            "disable Phoenix export purity",
        ),
        "CONNECTOR_STATE_STALE": (
            "reprobe current connector state and refresh the capability twin",
            "reuse stale capability state as current truth",
        ),
        "DIAGNOSIS_SUBSTITUTION": (
            "convert the discovered defect into repair work and continue the parent mission",
            "end the mission after explaining the defect",
        ),
    }

    def from_failure(self, entry: FailureMemoryEntry) -> RegressionCase:
        entry.validate()
        base = entry.fingerprint.split(":", 1)[0]
        expected, prohibited = self.behavior_map.get(
            base,
            (
                "preserve failure evidence, classify it, repair or reroute and verify readback",
                "repeat the unchanged failure or declare false completion",
            ),
        )
        digest = sha256(entry.fingerprint.encode("utf-8")).hexdigest()[:8]
        return RegressionCase(
            regression_id=f"REG-{digest}",
            failure_fingerprint=entry.fingerprint,
            injected_condition=entry.fingerprint,
            expected_behavior=expected,
            prohibited_behavior=prohibited,
            proof_source=entry.repair_proof_ref,
        ).validate()

    def build_suite(self, entries: Sequence[FailureMemoryEntry]) -> tuple[RegressionCase, ...]:
        cases = tuple(self.from_failure(entry) for entry in entries)
        if not cases:
            raise ValueError("autonomous regression suite requires at least one failure memory entry")
        return cases


@dataclass(frozen=True)
class PrePromotionDecision:
    decision: str
    baseline_score: float
    candidate_score: float
    gain: float
    hard_regressions: tuple[str, ...]
    reasons: tuple[str, ...]
    next_action: str


class EvolutionGovernorBridge:
    """Stage 18 pre-gate that reuses the existing EvolutionGovernor metric contract.

    It does not create a parallel promotion authority. Passing means forward the
    candidate into the existing hash-linked EvolutionGovernor ledger/evaluation path.
    """

    weights = dict(EvolutionGovernor.default_weights)
    hard_metrics = tuple(EvolutionGovernor.hard_metrics)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _score(self, metrics: Mapping[str, float]) -> float:
        total = sum(self.weights.values())
        return sum(self.weights[name] * self._clamp(metrics.get(name, 0.0)) for name in self.weights) / total

    def evaluate(
        self,
        *,
        baseline_metrics: Mapping[str, float],
        candidate_metrics: Mapping[str, float],
        minimum_gain: float = 0.02,
        regression_passed: bool,
        rollback_available: bool,
    ) -> PrePromotionDecision:
        missing = tuple(sorted(set(self.weights) - set(candidate_metrics)))
        hard = tuple(
            metric
            for metric in self.hard_metrics
            if self._clamp(candidate_metrics.get(metric, 0.0)) < self._clamp(baseline_metrics.get(metric, 0.0))
        )
        baseline_score = self._score(baseline_metrics)
        candidate_score = self._score(candidate_metrics)
        gain = candidate_score - baseline_score
        reasons: list[str] = []
        if missing:
            reasons.append("MISSING_METRICS:" + ",".join(missing))
        if hard:
            reasons.append("HARD_REGRESSION:" + ",".join(hard))
        if gain < minimum_gain:
            reasons.append(f"GAIN_BELOW_THRESHOLD:{gain:.6f}<{minimum_gain:.6f}")
        if not regression_passed:
            reasons.append("REGRESSION_PROOF_REQUIRED")
        if not rollback_available:
            reasons.append("ROLLBACK_REQUIRED")
        decision = "FORWARD_TO_EXISTING_EVOLUTION_GOVERNOR" if not reasons else "REJECT_PREPROMOTION"
        return PrePromotionDecision(
            decision=decision,
            baseline_score=round(baseline_score, 8),
            candidate_score=round(candidate_score, 8),
            gain=round(gain, 8),
            hard_regressions=hard,
            reasons=tuple(reasons),
            next_action=(
                "CALL_EXISTING_EVOLUTION_GOVERNOR_WITH_HASH_LINKED_CANDIDATE"
                if not reasons
                else "REPAIR_CANDIDATE_AND_RETEST"
            ),
        )


@dataclass(frozen=True)
class CapabilityGap:
    system_id: str
    missing_role: str
    current_twin_state: TwinState
    reason: str
    proof_ref: str

    def validate(self) -> "CapabilityGap":
        if self.system_id not in SYSTEM_PROFILES:
            raise ValueError("capability gap system must be registered")
        if not self.missing_role.strip() or not self.reason.strip() or not self.proof_ref.strip():
            raise ValueError("capability gap is incomplete")
        return self


@dataclass(frozen=True)
class CapabilityFormationPlan:
    build_id: str
    system_id: str
    missing_role: str
    required_components: tuple[str, ...]
    qualification_sequence: tuple[str, ...]
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False
    rollback_required: bool = True
    provider_effects_separately_authorized: bool = True


class CapabilityFormationEngine:
    """Stage 19 internal build-plan generator; no provider mutation or authority grant."""

    qualification_sequence = (
        "DESIGN_CONTRACT",
        "IMPLEMENT_A1_INTERNAL_CANDIDATE",
        "UNIT_AND_MUTATION_TEST",
        "CASEFORGE_ADVERSARIAL_TEST",
        "FEDERATION_AIRLOCK_AND_LEAK_GUARD",
        "SHADOW_CANARY_WHERE_AVAILABLE",
        "PROVIDER_READBACK_IF_PROVIDER_BOUND",
        "REGISTER_CAPABILITY_TWIN_AND_ROLLBACK",
    )

    def plan(self, gap: CapabilityGap) -> CapabilityFormationPlan:
        gap.validate()
        components = (
            "OBJECTIVE_CONTRACT",
            "AUTHORITY_BOUNDARY",
            "SEMANTIC_CONTRACT",
            "READBACK_CONTRACT",
            "ROLLBACK_CONTRACT",
            f"DOMAIN_ADAPTER:{gap.system_id}",
        )
        slug = "".join(ch if ch.isalnum() else "-" for ch in gap.missing_role.upper()).strip("-")
        return CapabilityFormationPlan(
            build_id=f"AO-CRA:CAPABILITY:{gap.system_id}:{slug}",
            system_id=gap.system_id,
            missing_role=gap.missing_role,
            required_components=components,
            qualification_sequence=self.qualification_sequence,
        )

    def infer_gap(self, twin: CapabilityTwin, *, required_role: str) -> CapabilityGap | None:
        twin.validate()
        if twin.twin_state in {TwinState.RUNTIME_VERIFIED, TwinState.PROVIDER_VERIFIED}:
            return None
        return CapabilityGap(
            system_id=twin.system_id,
            missing_role=required_role,
            current_twin_state=twin.twin_state,
            reason=f"required role is not runtime/provider verified; twin={twin.twin_state.value}",
            proof_ref=twin.proof_ref,
        ).validate()


@dataclass(frozen=True)
class WeaknessSignal:
    system_id: str
    materiality: float
    recurrence: float
    downstream_impact: float
    proof_gap: float
    owner_burden: float
    proof_ref: str

    def validate(self) -> "WeaknessSignal":
        if self.system_id not in SYSTEM_PROFILES or not self.proof_ref.strip():
            raise ValueError("weakness signal is invalid")
        for name in ("materiality", "recurrence", "downstream_impact", "proof_gap", "owner_burden"):
            if not 0.0 <= float(getattr(self, name)) <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        return self

    @property
    def priority(self) -> float:
        self.validate()
        return round(
            0.30 * self.materiality
            + 0.20 * self.recurrence
            + 0.25 * self.downstream_impact
            + 0.20 * self.proof_gap
            + 0.05 * self.owner_burden,
            8,
        )


@dataclass(frozen=True)
class ControllerAction:
    system_id: str
    action: str
    reason: str
    proof_ref: str
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False


@dataclass(frozen=True)
class DominanceControllerDecision:
    strict_maturity: StrictMaturityDecision
    selected_weakness: WeaknessSignal | None
    next_action: ControllerAction
    dominance_claim_allowed: bool


class AutonomousMaturityDominanceController:
    """Stage 20 decision loop. Source existence is not a durable scheduler.

    The controller may select and describe the next safe internal action. It may not
    claim dominance unless StrictMaturityGate independently authorizes the state.
    External/provider effects remain separately authorized and provider-readback-gated.
    """

    def __init__(self) -> None:
        self.maturity_gate = StrictMaturityGate()

    def choose_weakness(self, signals: Sequence[WeaknessSignal]) -> WeaknessSignal | None:
        if not signals:
            return None
        validated = [signal.validate() for signal in signals]
        return max(validated, key=lambda item: (item.priority, item.system_id))

    def decide(
        self,
        *,
        completed_through: EvolutionStage | None,
        maturity_proof: MaturityProofEnvelope,
        weaknesses: Sequence[WeaknessSignal],
        mission_state: MissionExecutionState,
    ) -> DominanceControllerDecision:
        mission_state.validate()
        maturity = self.maturity_gate.classify(completed_through=completed_through, proof=maturity_proof)
        weakness = self.choose_weakness(weaknesses)

        if mission_state.executable_internal_dependencies > 0:
            action = ControllerAction(
                system_id=weakness.system_id if weakness else "EVIDENCEOPS",
                action="CONTINUE_HIGHEST_VALUE_EXECUTABLE_INTERNAL_REPAIR",
                reason="MISSION_INTERNAL_WORK_REMAINS",
                proof_ref=weakness.proof_ref if weakness else "MISSION_STATE",
            )
        elif weakness is not None:
            action = ControllerAction(
                system_id=weakness.system_id,
                action="RUN_NEXT_REVERSIBLE_EVOLUTION_EXPERIMENT",
                reason=f"WEAKNESS_PRIORITY:{weakness.priority}",
                proof_ref=weakness.proof_ref,
            )
        else:
            action = ControllerAction(
                system_id="EVIDENCEOPS",
                action="RUN_FRESHNESS_AND_REGRESSION_REVALIDATION",
                reason="NO_HIGHER_PRIORITY_INTERNAL_WEAKNESS",
                proof_ref="STRICT_MATURITY_GATE",
            )

        return DominanceControllerDecision(
            strict_maturity=maturity,
            selected_weakness=weakness,
            next_action=action,
            dominance_claim_allowed=maturity.dominance_candidate,
        )


__all__ = [
    "ActivationKind",
    "AutonomousMaturityDominanceController",
    "AutonomousRegressionPlanner",
    "CapabilityFormationEngine",
    "CapabilityFormationPlan",
    "CapabilityGap",
    "ControllerAction",
    "DominanceControllerDecision",
    "EvolutionGovernorBridge",
    "PrePromotionDecision",
    "REQUIRED_ATTESTATION_CONTROLS",
    "RegressionCase",
    "RuntimeAttestation",
    "WeaknessSignal",
]
