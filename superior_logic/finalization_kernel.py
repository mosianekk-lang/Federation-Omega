from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping

from .architecture_genome import ArchitectureGenome, ArchitecturePattern, ArchitectureRequirement, core_ai_patterns
from .engineering_runtime import (
    AutonomousCapabilityClosure,
    ClosureCandidate,
    CodingFleetPlanner,
    FleetTask,
    PreparedWorkspaceForge,
    RepoGraph,
    SpecialistRole,
    WorkspaceMode,
)
from .opportunity_adapter import EngineeringOpportunityAdapter, MissionProfile


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class FinalizationDirective:
    mission_id: str
    base_revision: str
    objective: str
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    risk: str = "HIGH"
    unknown_count: int = 0
    estimated_tasks: int = 0
    external_effects: bool = False
    authority_ready: bool = True
    independent_verification_required: bool = True


@dataclass(frozen=True, slots=True)
class FinalizationBlueprint:
    mission_id: str
    repo_graph_sha256: str
    architecture_patterns: tuple[str, ...]
    architecture_residual: tuple[str, ...]
    workspace_id: str
    fleet_plan_sha256: str
    closure_action: str
    closure_residual: tuple[str, ...]
    required_final_proofs: tuple[str, ...]
    blueprint_sha256: str
    engineering_shape: str = "PLAN_ACT"


class SLOSFinalizationKernel:
    """Compile one engineering mission across perception, selection, execution shape and proof.

    The kernel remains a no-effect compiler. vNext R2 adds explicit engineering-shape
    selection while preserving ArchitectureGenome, RepoGraph, workspace, fleet,
    capability-closure and existing proof authorities.
    """

    ENGINEERING_PATTERNS = (
        ArchitecturePattern("REPOGRAPH_ENGINE", ("repository_intelligence", "impact_analysis"), .85, .15, .35, .95, ("INDEX",)),
        ArchitecturePattern("PREPARED_WORKSPACE_FORGE", ("prepared_workspace", "rollback"), .85, .15, .35, .95, ("WORKSPACE",)),
        ArchitecturePattern("CONFLICT_SAFE_CODING_FLEET", ("coding_fleet", "parallelism"), .80, .20, .45, .90, ("SCHEDULER",)),
        ArchitecturePattern("VERIFICATION_SUPERCOURT", ("verification_supercourt", "semantic_readback"), .90, .10, .40, .95, ("ASSURANCE",)),
        ArchitecturePattern("AUTONOMOUS_CAPABILITY_CLOSURE", ("capability_closure", "capability_discovery"), .80, .20, .45, .90, ("FOUNDRY",)),
        ArchitecturePattern("CONTEXT_TOURNAMENT", ("context_selection", "context_budgeting"), .85, .10, .25, .95, ("CONTEXT",)),
        ArchitecturePattern("HARNESS_TOURNAMENT", ("harness_selection", "paired_evaluation"), .85, .10, .30, .95, ("EVALUATION",)),
        ArchitecturePattern("EVOLUTION_LAB", ("evolution_lab", "challenger_generation"), .80, .15, .30, .95, ("EXPERIMENT",)),
        ArchitecturePattern("ENGINEERING_OPPORTUNITY_ADAPTER", ("engineering_shape", "opportunity_ranking"), .90, .10, .20, .95, ("PLANNER",)),
        ArchitecturePattern("ACCEPTANCE_INTEGRITY", ("acceptance_integrity", "independent_acceptance"), .95, .05, .20, .95, ("ASSURANCE",)),
        ArchitecturePattern("SKILLFORGE_V2", ("skill_formation", "skill_replay", "skill_expiry"), .85, .10, .25, .95, ("LEARNING",)),
    )

    def compile(
        self,
        directive: FinalizationDirective,
        *,
        repository_files: Mapping[str, str],
        toolchain: Mapping[str, str],
        dependencies: Mapping[str, str],
        internal_capabilities: Iterable[ClosureCandidate] = (),
        external_capabilities: Iterable[ClosureCandidate] = (),
    ) -> FinalizationBlueprint:
        if not directive.mission_id.strip() or not directive.objective.strip() or not directive.base_revision.strip():
            raise ValueError("mission/base/objective required")
        graph = RepoGraph().build(repository_files)
        requirement = ArchitectureRequirement(
            required_capabilities=directive.required_capabilities,
            optional_capabilities=directive.optional_capabilities,
            max_risk=.5,
            min_proof_strength=.5,
            max_components=6,
        )
        options = ArchitectureGenome().rank(requirement, (*core_ai_patterns(), *self.ENGINEERING_PATTERNS), limit=5)
        if not options:
            raise ValueError("no architecture option")
        best = options[0]
        target_paths = RepoGraph().ranked_context(graph, directive.objective, limit=8)

        inferred_subsystems = tuple(sorted({path.split("/", 1)[0] for path in target_paths if path}))
        estimated_tasks = directive.estimated_tasks if directive.estimated_tasks > 0 else max(1, min(8, len(target_paths) or 1))
        shape = EngineeringOpportunityAdapter().choose_shape(
            MissionProfile(
                mission_id=directive.mission_id,
                changed_paths=tuple(target_paths),
                subsystems=inferred_subsystems,
                risk=directive.risk.upper(),
                unknown_count=max(directive.unknown_count, len(best.residual_gaps)),
                estimated_tasks=estimated_tasks,
                external_effects=directive.external_effects,
                authority_ready=directive.authority_ready,
                independent_verification_required=directive.independent_verification_required,
            )
        )

        workspace = PreparedWorkspaceForge().plan(
            base_revision=directive.base_revision,
            repo_graph_sha256=graph.graph_sha256,
            toolchain=toolchain,
            dependencies=dependencies,
            writable_paths=target_paths or ("superior_logic/",),
            mode=WorkspaceMode.PREPARED,
        )
        fleet = CodingFleetPlanner().plan((
            FleetTask("explore", SpecialistRole.EXPLORER, target_paths, mutation=False, proof_obligations=("REPO_GRAPH",)),
            FleetTask("architect", SpecialistRole.ARCHITECT, target_paths, depends_on=("explore",), mutation=False, proof_obligations=("ARCHITECTURE_OPTION",)),
            FleetTask("implement", SpecialistRole.IMPLEMENTER, target_paths, depends_on=("architect",), mutation=True, proof_obligations=("PATCH_DIGEST", "WORKSPACE_ID")),
            FleetTask("test", SpecialistRole.TESTER, (), depends_on=("implement",), mutation=False, proof_obligations=("SUPERCOURT",)),
            FleetTask("verify", SpecialistRole.VERIFIER, (), depends_on=("test",), mutation=False, proof_obligations=("INDEPENDENT_READBACK",)),
            FleetTask("integrate", SpecialistRole.INTEGRATOR, (), depends_on=("verify",), mutation=False, proof_obligations=("TERMINAL_TRUTH",)),
        ))
        closure = AutonomousCapabilityClosure().decide(
            gap_id=f"{directive.mission_id}:architecture-residual",
            required=best.residual_gaps,
            internal=internal_capabilities,
            external=external_capabilities,
        ) if best.residual_gaps else None
        final_proofs = (
            "SOURCE_ADMISSION", "LEAK_GUARD", "AIRLOCK", "REPOGRAPH", "WORKSPACE_FORGE",
            "CODING_FLEET", "VERIFICATION_SUPERCOURT", "CAPABILITY_CLOSURE", "ROLLBACK",
            "SEMANTIC_READBACK", "INDEPENDENT_ASSURANCE",
        )
        body = {
            "mission_id": directive.mission_id,
            "repo": graph.graph_sha256,
            "architecture": best.pattern_ids,
            "residual": best.residual_gaps,
            "engineering_shape": shape.shape.value,
            "workspace": workspace.workspace_id,
            "fleet": fleet.plan_sha256,
            "closure": closure.action.value if closure else "NOT_REQUIRED",
            "closure_residual": closure.residual if closure else (),
            "proofs": final_proofs,
        }
        return FinalizationBlueprint(
            mission_id=directive.mission_id,
            repo_graph_sha256=graph.graph_sha256,
            architecture_patterns=best.pattern_ids,
            architecture_residual=best.residual_gaps,
            workspace_id=workspace.workspace_id,
            fleet_plan_sha256=fleet.plan_sha256,
            closure_action=closure.action.value if closure else "NOT_REQUIRED",
            closure_residual=closure.residual if closure else (),
            required_final_proofs=final_proofs,
            blueprint_sha256=_sha(body),
            engineering_shape=shape.shape.value,
        )
