from __future__ import annotations

"""FUSE Formation Power Inheritance v2.

Additive composition layer over existing FUSE organs. It does not create a new
controller, scheduler, authority root, provider runtime, truth root, memory root
or proof root. It makes the already-existing Formation/CFBE/Agentic Frontier/
Autonomic Mission/OmniSurface mechanisms inheritable by every FUSE workflow.

The module is planning-only: no provider calls, credentials, spend, external
effects or self-certification.
"""

from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable, Sequence

from benchmarking.cfbe_omega.n_omega_agentic_frontier_v1 import (
    AgenticFrontierCompiler,
    MissionProfile,
)
from formation_omega.autonomic_fabric import (
    ActionCandidate,
    AuthorityCeiling,
    FailureForecast,
    FailureHorizon,
    MissionSwarmPlanner,
    ProofDirectedScheduler,
    SwarmRole,
)
from federation.formation_cyber_investigative_engine_v1 import FormationCyberInvestigativeEngine
from federation.formation_network_intelligence_v1 import FormationNetworkIntelligence
from federation.formation_surface_load_balancer_v1 import (
    FormationSurfaceLoadBalancer,
    FormationWorkPackage,
    SurfaceFormationPlan,
    SurfaceRuntimeState,
    WorkKind,
)

SCHEMA = "FUSE_FORMATION_POWER_INHERITANCE_V2"
VERSION = "2.0.0"
CONTRACT_ID = "FUSE-FORMATION-POWER-002"


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: object) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


class FormationPowerMode(StrEnum):
    FAST = "FAST"
    FUSION = "FUSION"
    ADVERSARIAL = "ADVERSARIAL"
    FORMATION = "FORMATION"
    DEEP = "DEEP"
    LIVE = "LIVE"
    CHAMPION_TOURNAMENT = "CHAMPION_TOURNAMENT"


class WorkflowClass(StrEnum):
    GENERAL = "GENERAL"
    RESEARCH = "RESEARCH"
    ENGINEERING = "ENGINEERING"
    CREATIVE = "CREATIVE"
    EVIDENCE = "EVIDENCE"
    AUTOMATION = "AUTOMATION"
    CLOUD_RUNTIME = "CLOUD_RUNTIME"
    WINDOWS_DEVICE = "WINDOWS_DEVICE"
    COMMUNICATIONS = "COMMUNICATIONS"
    RELEASE = "RELEASE"
    LONG_RUNNING = "LONG_RUNNING"


@dataclass(frozen=True, slots=True)
class WorkflowFormationSpec:
    workflow_id: str
    objective: str
    workflow_class: WorkflowClass = WorkflowClass.GENERAL
    domains: frozenset[str] = frozenset({"ORCHESTRATION", "EVALUATION", "ROUTING"})
    long_running: bool = False
    multi_agent: bool = False
    tool_heavy: bool = False
    code_execution: bool = False
    browser_or_computer: bool = False
    legacy_ui: bool = False
    customer_facing: bool = False
    consequential: bool = False
    requires_memory: bool = False
    requires_dynamic_models: bool = False
    requires_release: bool = False
    requires_adaptive_effort: bool = True
    requires_cross_window_context: bool = False
    requires_dynamic_tools: bool = False
    requires_portable_skills: bool = False
    requires_persistent_agent: bool = False
    requires_adaptive_computer_use: bool = False
    requires_hypothesis_evolution: bool = False
    requires_strict_self_verification: bool = True
    requires_harness_simplification: bool = False
    requires_artifact_production: bool = False
    requires_local_multimodal: bool = False
    live: bool = False
    champion_tournament: bool = False
    requested_mode: FormationPowerMode | None = None
    max_parallel: int = 4
    total_cost_ceiling: float = 10.0
    exploration_budget_fraction: float = 0.05

    def validate(self) -> "WorkflowFormationSpec":
        if not self.workflow_id.strip() or not self.objective.strip():
            raise ValueError("FORMATION_POWER_WORKFLOW_ID_AND_OBJECTIVE_REQUIRED")
        if self.max_parallel < 1:
            raise ValueError("FORMATION_POWER_MAX_PARALLEL_INVALID")
        if self.total_cost_ceiling < 0:
            raise ValueError("FORMATION_POWER_COST_CEILING_INVALID")
        if not 0.0 <= self.exploration_budget_fraction <= 0.20:
            raise ValueError("FORMATION_POWER_EXPLORATION_BUDGET_INVALID")
        return self


@dataclass(frozen=True, slots=True)
class FormationPowerPlan:
    schema: str
    version: str
    contract_id: str
    plan_id: str
    workflow_id: str
    workflow_class: str
    mode: str
    selected_gene_ids: tuple[str, ...]
    orchestration: tuple[str, ...]
    swarm_roles: tuple[str, ...]
    selected_action_ids: tuple[str, ...]
    surface_plan: SurfaceFormationPlan
    dynamic_replan_triggers: tuple[str, ...]
    checkpoint_policy: tuple[str, ...]
    learning_fields: tuple[str, ...]
    max_mutating_lanes: int
    external_effect_authorized: bool
    provider_execution_proven: bool
    builder_self_certification_allowed: bool
    creates_new_controller: bool
    creates_new_scheduler: bool
    creates_new_authority_root: bool
    truth_boundary: str

    @property
    def complete(self) -> bool:
        return self.surface_plan.complete and bool(self.selected_gene_ids)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class FormationPowerCompiler:
    """Compose existing formation mechanisms into every FUSE workflow."""

    TRUTH_BOUNDARY = (
        "FORMATION_POWER_COMPILED!=WORKFLOW_EXECUTED!=PROVIDER_EXECUTED"
        "!=EFFECT_READBACK!=INDEPENDENT_JUDGE!=OWNER_VALUE!=COMPLETE"
    )

    REPLAN_TRIGGERS = (
        "OWNER_INTENT_CHANGE",
        "STATE_EPOCH_CHANGE",
        "CAPABILITY_CURRENTNESS_CHANGE",
        "PROOF_LEASE_EXPIRY",
        "PROVIDER_HEALTH_CHANGE",
        "QUOTA_OR_COST_PRESSURE",
        "NEW_MATERIAL_EVIDENCE",
        "CONTRADICTION_OR_JUDGE_REJECTION",
        "ROUTE_FAILURE_OR_NEAR_MISS",
        "CRITICAL_PATH_BLOCKER_CHANGE",
    )

    CHECKPOINT_POLICY = (
        "CHECKPOINT_BEFORE_EXTERNAL_EFFECT",
        "CHECKPOINT_AFTER_VERIFIED_EFFECT",
        "CHECKPOINT_ON_PROVIDER_HANDOFF",
        "CHECKPOINT_ON_LONG_RUNNING_WAIT",
        "RESUME_FROM_CURRENT_STATE_NOT_CHAT_HISTORY",
    )

    LEARNING_FIELDS = (
        "TASK_CLASS",
        "FORMATION_MODE",
        "SELECTED_SURFACES",
        "SELECTED_CAPABILITY_GENES",
        "QUALITY",
        "LATENCY",
        "COST",
        "RELIABILITY",
        "OWNER_BURDEN",
        "FAILURE_FINGERPRINT",
        "CHANGED_MECHANISM",
        "PROOF_FRESHNESS",
        "OWNER_VALUE",
        "VALIDITY_EXPIRY",
    )

    _ROLE_SETS = {
        FormationPowerMode.FAST: (
            SwarmRole.BUILDER,
            SwarmRole.WITNESS,
        ),
        FormationPowerMode.FUSION: (
            SwarmRole.BUILDER,
            SwarmRole.EVIDENCE,
            SwarmRole.FALSIFIER,
            SwarmRole.WITNESS,
        ),
        FormationPowerMode.ADVERSARIAL: (
            SwarmRole.BUILDER,
            SwarmRole.FALSIFIER,
            SwarmRole.EVIDENCE,
            SwarmRole.ROUTE,
            SwarmRole.WITNESS,
        ),
        FormationPowerMode.FORMATION: tuple(SwarmRole),
        FormationPowerMode.DEEP: tuple(SwarmRole),
        FormationPowerMode.LIVE: (
            SwarmRole.BUILDER,
            SwarmRole.SENTINEL,
            SwarmRole.RECOVERY,
            SwarmRole.WITNESS,
        ),
        FormationPowerMode.CHAMPION_TOURNAMENT: (
            SwarmRole.BUILDER,
            SwarmRole.FALSIFIER,
            SwarmRole.EVIDENCE,
            SwarmRole.ROUTE,
            SwarmRole.WITNESS,
        ),
    }

    def __init__(self, surface_balancer: FormationSurfaceLoadBalancer | None = None) -> None:
        self.frontier = AgenticFrontierCompiler()
        self.swarm_planner = MissionSwarmPlanner()
        self.surface_balancer = surface_balancer or FormationSurfaceLoadBalancer()
        self.scheduler = ProofDirectedScheduler(
            authority_ceiling=AuthorityCeiling.A1_INTERNAL,
            allow_external_effects=False,
        )
        self.failure_horizon = FailureHorizon()
        self.network_intelligence = FormationNetworkIntelligence()
        self.cyber_investigative = FormationCyberInvestigativeEngine()

    @staticmethod
    def _mode(spec: WorkflowFormationSpec, package_count: int) -> FormationPowerMode:
        if spec.requested_mode is not None:
            return FormationPowerMode(spec.requested_mode)
        if spec.champion_tournament:
            return FormationPowerMode.CHAMPION_TOURNAMENT
        if spec.live:
            return FormationPowerMode.LIVE
        if spec.consequential:
            return FormationPowerMode.ADVERSARIAL
        if spec.requires_hypothesis_evolution or spec.workflow_class in {
            WorkflowClass.RESEARCH,
            WorkflowClass.EVIDENCE,
        }:
            return FormationPowerMode.DEEP
        if spec.multi_agent or package_count > 1:
            return FormationPowerMode.FORMATION
        if spec.requires_dynamic_models:
            return FormationPowerMode.FUSION
        return FormationPowerMode.FAST

    @staticmethod
    def _mission_profile(spec: WorkflowFormationSpec) -> MissionProfile:
        return MissionProfile(
            mission_id=spec.workflow_id,
            domains=spec.domains,
            long_running=spec.long_running,
            multi_agent=spec.multi_agent,
            tool_heavy=spec.tool_heavy,
            code_execution=spec.code_execution,
            browser_or_computer=spec.browser_or_computer,
            legacy_ui=spec.legacy_ui,
            customer_facing=spec.customer_facing,
            consequential=spec.consequential,
            requires_memory=spec.requires_memory,
            requires_dynamic_models=spec.requires_dynamic_models,
            requires_release=spec.requires_release,
            requires_adaptive_effort=spec.requires_adaptive_effort,
            requires_cross_window_context=spec.requires_cross_window_context,
            requires_dynamic_tools=spec.requires_dynamic_tools,
            requires_portable_skills=spec.requires_portable_skills,
            requires_persistent_agent=spec.requires_persistent_agent,
            requires_adaptive_computer_use=spec.requires_adaptive_computer_use,
            requires_hypothesis_evolution=spec.requires_hypothesis_evolution,
            requires_strict_self_verification=spec.requires_strict_self_verification,
            requires_harness_simplification=spec.requires_harness_simplification,
            requires_artifact_production=spec.requires_artifact_production,
            requires_local_multimodal=spec.requires_local_multimodal,
        )

    @staticmethod
    def _strengthen_packages(
        packages: Sequence[FormationWorkPackage],
        mode: FormationPowerMode,
    ) -> tuple[FormationWorkPackage, ...]:
        if mode not in {
            FormationPowerMode.FUSION,
            FormationPowerMode.ADVERSARIAL,
            FormationPowerMode.CHAMPION_TOURNAMENT,
        }:
            return tuple(packages)
        strengthened: list[FormationWorkPackage] = []
        for package in packages:
            if package.kind is WorkKind.COGNITION:
                strengthened.append(
                    replace(
                        package,
                        require_independent_candidates=True,
                        candidate_count=max(2, package.candidate_count),
                    )
                )
            else:
                strengthened.append(package)
        return tuple(strengthened)

    def _swarm_roles(
        self,
        *,
        spec: WorkflowFormationSpec,
        mode: FormationPowerMode,
        gene_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        all_cells = self.swarm_planner.plan(
            mission_id=spec.workflow_id,
            objective=spec.objective,
            required_capabilities=gene_ids,
        )
        allowed = set(self._ROLE_SETS[mode])
        return tuple(cell.role.value for cell in all_cells if cell.role in allowed)

    def compile(
        self,
        *,
        spec: WorkflowFormationSpec,
        packages: Sequence[FormationWorkPackage],
        runtime_states: Sequence[SurfaceRuntimeState],
        actions: Iterable[ActionCandidate] = (),
        failure_forecasts: Iterable[FailureForecast] = (),
    ) -> FormationPowerPlan:
        spec.validate()
        if not packages:
            raise ValueError("FORMATION_POWER_REQUIRES_AT_LEAST_ONE_WORK_PACKAGE")

        mode = self._mode(spec, len(packages))
        frontier_plan = self.frontier.compile(self._mission_profile(spec))
        strengthened = self._strengthen_packages(packages, mode)

        surface_plan = self.surface_balancer.compile(
            mission_id=spec.workflow_id,
            packages=strengthened,
            runtime_states=runtime_states,
            max_parallel_surfaces=spec.max_parallel,
            total_cost_ceiling=spec.total_cost_ceiling,
        )

        action_wave = self.scheduler.ready_wave(actions, max_parallel=spec.max_parallel)
        preemptions = self.failure_horizon.preempt(failure_forecasts)
        swarm_roles = self._swarm_roles(
            spec=spec,
            mode=mode,
            gene_ids=frontier_plan.selected_gene_ids,
        )

        orchestration = list(frontier_plan.orchestration)
        orchestration.extend(
            [
                "CRITICAL_PATH_FIRST",
                "DISJOINT_READY_LANES_PARALLEL",
                "ONE_MUTATING_LANE",
                "SURFACE_HEALTH_REPLAN",
                "PROOF_DIRECTED_SCHEDULING",
                "SELECTIVE_BLAST_RADIUS_REQUALIFICATION",
                "FEDERATION_LEARNING_POSTPASS",
            ]
        )
        if spec.workflow_class in {WorkflowClass.WINDOWS_DEVICE, WorkflowClass.EVIDENCE} or "NETWORK" in spec.domains or "DEVICE" in spec.domains:
            orchestration.extend([
                "FORMATION_NETWORK_INTELLIGENCE_V1",
                "TEMPORAL_IDENTITY_GRAPH",
                "IP_MAC_EPOCH_SEPARATION",
                "PRIVATE_MAC_CAUTION",
                "PASSIVE_PROTOCOL_EVIDENCE_FUSION",
                "NEXT_BEST_EVIDENCE_PLANNING",
            ])
        if (
            spec.workflow_class in {WorkflowClass.ENGINEERING, WorkflowClass.EVIDENCE, WorkflowClass.WINDOWS_DEVICE}
            or {"CYBER","FORENSICS","SOFTWARE","REVERSE_ENGINEERING","NETWORK","DEVICE"} & set(spec.domains)
        ):
            orchestration.extend([
                "FORMATION_CYBER_INVESTIGATIVE_ENGINE_V1",
                "RIGHTS_AUTHORITY_AND_SCOPE_PREFLIGHT",
                "HISTORICAL_HYPERCUBE_CFBE_REUSE_CENSUS",
                "STATIC_METADATA_DEPENDENCY_AND_INTERFACE_ANALYSIS",
                "CLEAN_ROOM_BEHAVIOURAL_PROTOCOL_INFERENCE_WHEN_AUTHORISED",
                "MECHANISM_EXTRACTION_VENDOR_NOISE_REMOVAL",
                "CAPABILITY_GRAPH_AND_DIGITAL_TWIN",
                "PERSISTENT_FAILURE_FINGERPRINT_AND_WORKAROUND_COMPILATION",
            ])
        if mode in {
            FormationPowerMode.FUSION,
            FormationPowerMode.ADVERSARIAL,
            FormationPowerMode.CHAMPION_TOURNAMENT,
        }:
            orchestration.append("INDEPENDENCE_DOMAIN_ENFORCED")
        if spec.long_running or spec.requires_persistent_agent:
            orchestration.append("DURABLE_CHECKPOINT_RESUME")
        if preemptions:
            orchestration.append("FAILURE_HORIZON_PREEMPTION")

        stable = {
            "workflow_id": spec.workflow_id,
            "mode": mode.value,
            "genes": frontier_plan.selected_gene_ids,
            "swarm_roles": swarm_roles,
            "surface_plan": surface_plan.plan_id,
            "actions": tuple(item.action.action_id for item in action_wave),
            "preemptions": tuple(item.fingerprint for item in preemptions),
        }

        return FormationPowerPlan(
            schema=SCHEMA,
            version=VERSION,
            contract_id=CONTRACT_ID,
            plan_id=f"FUSE-FORMATION-POWER-V2-{_digest(stable)[:24].upper()}",
            workflow_id=spec.workflow_id,
            workflow_class=spec.workflow_class.value,
            mode=mode.value,
            selected_gene_ids=frontier_plan.selected_gene_ids,
            orchestration=tuple(dict.fromkeys(orchestration)),
            swarm_roles=swarm_roles,
            selected_action_ids=tuple(item.action.action_id for item in action_wave),
            surface_plan=surface_plan,
            dynamic_replan_triggers=self.REPLAN_TRIGGERS,
            checkpoint_policy=self.CHECKPOINT_POLICY,
            learning_fields=self.LEARNING_FIELDS,
            max_mutating_lanes=1,
            external_effect_authorized=False,
            provider_execution_proven=False,
            builder_self_certification_allowed=False,
            creates_new_controller=False,
            creates_new_scheduler=False,
            creates_new_authority_root=False,
            truth_boundary=self.TRUTH_BOUNDARY,
        )


__all__ = [
    "FormationPowerCompiler",
    "FormationPowerMode",
    "FormationPowerPlan",
    "WorkflowClass",
    "WorkflowFormationSpec",
]
