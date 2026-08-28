from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence

from .commercial_value import ValueGateDecision, ValueGateState


class ProductionConvergenceState(str, Enum):
    HOLD_SOURCE_CI = "HOLD_SOURCE_CI"
    HOLD_CONTROL_PLANE = "HOLD_CONTROL_PLANE"
    HOLD_RUNTIME_IDENTITY = "HOLD_RUNTIME_IDENTITY"
    HOLD_PROVIDER_READBACK = "HOLD_PROVIDER_READBACK"
    HOLD_BOUNDED_CANARY = "HOLD_BOUNDED_CANARY"
    HOLD_RECOVERY_PROOF = "HOLD_RECOVERY_PROOF"
    HOLD_REPEATED_COHORT = "HOLD_REPEATED_COHORT"
    HOLD_VALUE_GATE = "HOLD_VALUE_GATE"
    HOLD_ROLLBACK = "HOLD_ROLLBACK"
    HOLD_SOAK = "HOLD_SOAK"
    PROGRESSIVE_EXPANSION_READY = "PROGRESSIVE_EXPANSION_READY"
    FULL_TARGET_ESTATE_PRODUCTION_CANDIDATE = "FULL_TARGET_ESTATE_PRODUCTION_CANDIDATE"


class SurfaceClass(str, Enum):
    CONTROL_STATE = "CONTROL_STATE"
    SOURCE_CI = "SOURCE_CI"
    CREATIVE_TOOL = "CREATIVE_TOOL"
    MODEL_PROVIDER = "MODEL_PROVIDER"
    CLOUD_RUNTIME = "CLOUD_RUNTIME"
    CHANNEL_ACTIVATION = "CHANNEL_ACTIVATION"
    OBSERVABILITY = "OBSERVABILITY"
    LEARNING = "LEARNING"


@dataclass(frozen=True, slots=True)
class SurfaceAdmission:
    surface_id: str
    surface_class: SurfaceClass
    required_for_target: bool
    current: bool
    authority_bound: bool
    provider_native_readback: bool
    semantic_canary: bool
    rollback_or_disable_proven: bool
    proof_ref: str = ""

    @property
    def production_proven(self) -> bool:
        return bool(
            self.current
            and self.authority_bound
            and self.provider_native_readback
            and self.semantic_canary
            and self.rollback_or_disable_proven
            and self.proof_ref.strip()
        )


@dataclass(frozen=True, slots=True)
class ProductionEvidence:
    source_ci_admitted: bool
    control_plane_bound: bool
    runtime_identity_verified: bool
    provider_native_readback: bool
    bounded_creative_canary: bool
    recovery_canary_passed: bool
    repeated_success: bool
    rollback_proven: bool
    soak_passed: bool
    value_gate: ValueGateDecision
    target_surfaces: tuple[SurfaceAdmission, ...]


@dataclass(frozen=True, slots=True)
class ProductionConvergenceDecision:
    state: ProductionConvergenceState
    next_gate: str
    proven_surfaces: tuple[str, ...]
    held_surfaces: tuple[str, ...]
    target_surface_completion: float
    full_target_estate_ready: bool
    reasons: tuple[str, ...]


def _surface_partition(surfaces: Sequence[SurfaceAdmission]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    proven = tuple(sorted(item.surface_id for item in surfaces if item.production_proven))
    held = tuple(sorted(item.surface_id for item in surfaces if not item.production_proven))
    return proven, held


def _target_completion(surfaces: Sequence[SurfaceAdmission]) -> float:
    required = [item for item in surfaces if item.required_for_target]
    if not required:
        return 0.0
    return sum(item.production_proven for item in required) / len(required)


def evaluate_production_convergence(evidence: ProductionEvidence) -> ProductionConvergenceDecision:
    """Evaluate the next production gate without manufacturing deployment authority.

    A single provider or surface win never becomes an estate-wide claim. Progressive
    expansion is allowed once the shared production kernel has provider/recovery/value
    proof, while FULL_TARGET_ESTATE requires every declared target surface to carry
    same-surface authority, semantic readback and rollback/disable proof.
    """

    surfaces = evidence.target_surfaces
    proven, held = _surface_partition(surfaces)
    completion = _target_completion(surfaces)
    common = dict(
        proven_surfaces=proven,
        held_surfaces=held,
        target_surface_completion=completion,
        full_target_estate_ready=False,
    )

    if not evidence.source_ci_admitted:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_SOURCE_CI,
            "EXACT_HEAD_SOURCE_CI_ADMISSION",
            reasons=("SOURCE_CI_REQUIRED",),
            **common,
        )
    if not evidence.control_plane_bound:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_CONTROL_PLANE,
            "KDV_FEDERATION_CONTROL_PLANE_READBACK",
            reasons=("CONTROL_PLANE_BINDING_REQUIRED",),
            **common,
        )
    if not evidence.runtime_identity_verified:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_RUNTIME_IDENTITY,
            "CURRENT_RUNTIME_IDENTITY_AND_AUTHORITY_READBACK",
            reasons=("RUNTIME_IDENTITY_REQUIRED",),
            **common,
        )
    if not evidence.provider_native_readback:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_PROVIDER_READBACK,
            "BOUNDED_PROVIDER_NATIVE_SEMANTIC_READBACK",
            reasons=("PROVIDER_NATIVE_READBACK_REQUIRED",),
            **common,
        )
    if not evidence.bounded_creative_canary:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_BOUNDED_CANARY,
            "END_TO_END_CREATIVE_CANARY",
            reasons=("CREATIVE_BEHAVIOR_CANARY_REQUIRED",),
            **common,
        )
    if not evidence.recovery_canary_passed:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_RECOVERY_PROOF,
            "FORCED_FAILURE_AND_RECOVERY_CANARY",
            reasons=("RECOVERY_PROOF_REQUIRED",),
            **common,
        )
    if not evidence.repeated_success:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_REPEATED_COHORT,
            "REPEATED_PRODUCTION_COHORT",
            reasons=("REPEATED_SUCCESS_REQUIRED",),
            **common,
        )
    if evidence.value_gate.state is not ValueGateState.PRODUCTION_VALUE_CANDIDATE:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_VALUE_GATE,
            "COMMERCIAL_OPERATIONAL_USABILITY_VALUE_GATE",
            reasons=(f"VALUE_GATE:{evidence.value_gate.state.value}",),
            **common,
        )
    if not evidence.rollback_proven:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_ROLLBACK,
            "ROLLBACK_DISABLE_RESTORE_DRILL",
            reasons=("ROLLBACK_PROOF_REQUIRED",),
            **common,
        )
    if not evidence.soak_passed:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.HOLD_SOAK,
            "SLO_COST_VALUE_SOAK",
            reasons=("SOAK_REQUIRED",),
            **common,
        )

    required = [item for item in surfaces if item.required_for_target]
    required_ready = bool(required) and all(item.production_proven for item in required)
    if not required_ready:
        return ProductionConvergenceDecision(
            ProductionConvergenceState.PROGRESSIVE_EXPANSION_READY,
            "ADMIT_NEXT_HELD_TARGET_SURFACE_WITH_SAME_SURFACE_PROOF",
            proven_surfaces=proven,
            held_surfaces=held,
            target_surface_completion=completion,
            full_target_estate_ready=False,
            reasons=("SHARED_KERNEL_VALUE_PROVEN", "TARGET_SURFACES_REMAIN_HELD"),
        )

    return ProductionConvergenceDecision(
        ProductionConvergenceState.FULL_TARGET_ESTATE_PRODUCTION_CANDIDATE,
        "OWNER_PRODUCTION_RELEASE_OR_EXISTING_AUTHORITY_GATE",
        proven_surfaces=proven,
        held_surfaces=held,
        target_surface_completion=completion,
        full_target_estate_ready=True,
        reasons=("ALL_DECLARED_TARGET_SURFACES_PROVEN", "SHARED_VALUE_AND_SOAK_PROVEN"),
    )


def next_surface_to_admit(surfaces: Iterable[SurfaceAdmission]) -> str | None:
    """Choose a deterministic next held target, preferring control/runtime before channels."""

    priority = {
        SurfaceClass.CONTROL_STATE: 0,
        SurfaceClass.SOURCE_CI: 1,
        SurfaceClass.CLOUD_RUNTIME: 2,
        SurfaceClass.OBSERVABILITY: 3,
        SurfaceClass.MODEL_PROVIDER: 4,
        SurfaceClass.CREATIVE_TOOL: 5,
        SurfaceClass.LEARNING: 6,
        SurfaceClass.CHANNEL_ACTIVATION: 7,
    }
    held = [item for item in surfaces if item.required_for_target and not item.production_proven]
    if not held:
        return None
    held.sort(key=lambda item: (priority[item.surface_class], item.surface_id))
    return held[0].surface_id
