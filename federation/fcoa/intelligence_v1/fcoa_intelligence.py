from __future__ import annotations

"""FCOA Formation + Hyper-Intelligence + Autonomous Improvement binding v1.

Additive intelligence layer for the existing FCOA-OMEGA identity. It composes
Formation Power planning with HIPB runtime hooks and the existing ten-iteration
autonomous-improvement worker. It creates no scheduler, authority root, truth
root, memory root, proof root, provider authority, or external effect.
"""

from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

from formation_omega.autonomic_fabric import ActionCandidate, FailureForecast
from federation.formation_power_inheritance_v2 import (
    FormationPowerCompiler,
    FormationPowerPlan,
    WorkflowFormationSpec,
)
from federation.formation_surface_load_balancer_v1 import (
    FormationWorkPackage,
    SurfaceRuntimeState,
)


SCHEMA = "FCOA_FORMATION_HYPER_AUTOIMPROVE_BINDING_V1"
VERSION = "1.0.0"
CONTRACT_ID = "FCOA-INTELLIGENCE-001"


@dataclass(frozen=True, slots=True)
class FCOAIntelligencePlan:
    schema: str
    version: str
    contract_id: str
    workflow_id: str
    formation_plan_id: str
    formation_mode: str
    selected_gene_ids: tuple[str, ...]
    formation_orchestration: tuple[str, ...]
    hipb_contract_id: str
    hipb_runtime_module: str
    sovereign_hook_phases: tuple[str, ...]
    autonomous_improvement_contract: str
    autonomous_improvement_worker: str
    autonomous_improvement_iterations: int
    improvement_promotion_requires: str
    improvement_tie_behavior: str
    persistent_learning_receivers: tuple[str, ...]
    max_mutating_lanes: int
    external_effect_authorized: bool
    provider_execution_proven: bool
    builder_self_certification_allowed: bool
    creates_new_controller: bool
    creates_new_scheduler: bool
    creates_new_authority_root: bool
    truth_boundary: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class FCOAIntelligenceBinding:
    """Compile FCOA work through Formation and require HIPB/improvement runtime."""

    TRUTH_BOUNDARY = (
        "FCOA_INTELLIGENCE_BOUND!=FCOA_WORKFLOW_EXECUTED!=HIPB_RUNTIME_CONSUMED"
        "!=TEN_ITERATION_IMPROVEMENT_EXECUTED!=MATCHED_PERFORMANCE_PROVEN"
        "!=PROVIDER_EFFECT_VERIFIED!=INDEPENDENT_JUDGE!=OWNER_VALUE!=COMPLETE"
    )

    PERSISTENT_LEARNING_RECEIVERS = (
        "FUSE_WORK_PLANE",
        "FAILURE_MEMORY",
        "ROUTE_MEMORY",
        "FEDERATION_LEARNING",
        "ARTIFACT_PROVENANCE",
        "PROOFOS_JUDGE",
    )

    def __init__(self, formation: FormationPowerCompiler | None = None) -> None:
        self.formation = formation or FormationPowerCompiler()

    def compile(
        self,
        *,
        spec: WorkflowFormationSpec,
        packages: Sequence[FormationWorkPackage],
        runtime_states: Sequence[SurfaceRuntimeState],
        actions: Iterable[ActionCandidate] = (),
        failure_forecasts: Iterable[FailureForecast] = (),
    ) -> FCOAIntelligencePlan:
        formation_plan: FormationPowerPlan = self.formation.compile(
            spec=spec,
            packages=packages,
            runtime_states=runtime_states,
            actions=actions,
            failure_forecasts=failure_forecasts,
        )
        return FCOAIntelligencePlan(
            schema=SCHEMA,
            version=VERSION,
            contract_id=CONTRACT_ID,
            workflow_id=spec.workflow_id,
            formation_plan_id=formation_plan.plan_id,
            formation_mode=formation_plan.mode,
            selected_gene_ids=formation_plan.selected_gene_ids,
            formation_orchestration=formation_plan.orchestration,
            hipb_contract_id="FUSE-HIPB-001",
            hipb_runtime_module="fuse_runtime/hyper_intelligence_performance_v1.mjs",
            sovereign_hook_phases=("PRE_COMPILE", "PRE_EFFECT", "POST_EFFECT"),
            autonomous_improvement_contract="FUSE_AUTONOMOUS_IMPROVEMENT_LOOP_V1",
            autonomous_improvement_worker="fuse_runtime/autonomous_improvement_loop_v1.mjs",
            autonomous_improvement_iterations=10,
            improvement_promotion_requires=(
                "MATCHED_NONREGRESSION_PROOF_READBACK_ROLLBACK_AND_PROVENANCE"
            ),
            improvement_tie_behavior="KEEP_CURRENT_CHAMPION",
            persistent_learning_receivers=self.PERSISTENT_LEARNING_RECEIVERS,
            max_mutating_lanes=formation_plan.max_mutating_lanes,
            external_effect_authorized=False,
            provider_execution_proven=False,
            builder_self_certification_allowed=False,
            creates_new_controller=False,
            creates_new_scheduler=False,
            creates_new_authority_root=False,
            truth_boundary=self.TRUTH_BOUNDARY,
        )


__all__ = [
    "CONTRACT_ID",
    "FCOAIntelligenceBinding",
    "FCOAIntelligencePlan",
    "SCHEMA",
    "VERSION",
]
