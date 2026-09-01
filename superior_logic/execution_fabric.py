from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .capability_graph import CapabilityGraph
from .convergence import ConstitutionalConvergence, MissionIntentContract
from .digital_twin import CounterfactualController, FederationDigitalTwin, Intervention, SimulationResult
from .hyperperformance import ParallelLaneScheduler, ParallelPlan
from .mission_ir import MissionIR, MissionIRCompiler, TransitionSpec
from .provider_attestations import ProviderAttestationStore
from .shadow_evolution import ShadowEvolutionLab


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class FabricPlanReceipt:
    mission_ir: MissionIR
    parallel_plan: ParallelPlan
    twin_snapshot_sha256: str
    receipt_sha256: str
    provider_effect_performed: bool = False


class HyperperformanceExecutionFabric:
    """Single SLOS planning facade over SOL-safe hyperperformance primitives.

    This object does not create a second mission authority or provider executor.
    It compiles SLOS mission intent, resolves currently admissible capabilities,
    builds a safe parallel plan and updates the side-effect-free digital twin.
    Actual effects still require the SOL 6.2 transaction kernel and SOVARA.
    """

    def __init__(
        self,
        capability_graph: CapabilityGraph,
        *,
        attestation_store: ProviderAttestationStore | None = None,
        scheduler: ParallelLaneScheduler | None = None,
        twin: FederationDigitalTwin | None = None,
        evolution_lab: ShadowEvolutionLab | None = None,
        convergence: ConstitutionalConvergence | None = None,
    ) -> None:
        self.capability_graph = capability_graph
        self.attestation_store = attestation_store
        self.scheduler = scheduler or ParallelLaneScheduler()
        self.twin = twin or FederationDigitalTwin()
        self.evolution_lab = evolution_lab or ShadowEvolutionLab()
        self.convergence = convergence or ConstitutionalConvergence()
        self.compiler = MissionIRCompiler()

    def compile_and_plan(
        self,
        contract: MissionIntentContract,
        transitions: Sequence[TransitionSpec | Mapping[str, Any]],
        *,
        now_epoch: int,
        completed_transition_ids: Sequence[str] = (),
        authority_ceiling: str = "MISSION_SCOPED",
        budgets: Mapping[str, float] | None = None,
    ) -> FabricPlanReceipt:
        if self.convergence.owner_for("MISSION_SEMANTICS") != "SLOS":
            raise RuntimeError("SLOS_MISSION_AUTHORITY_LOST")
        mission = self.compiler.compile(
            contract,
            transitions,
            authority_ceiling=authority_ceiling,
            budgets=budgets,
        )
        self.twin.project_mission(mission)
        plan = self.scheduler.plan(
            mission,
            self.capability_graph,
            completed_transition_ids=completed_transition_ids,
            now_epoch=now_epoch,
            attestation_store=self.attestation_store,
        )
        twin_snapshot = self.twin.snapshot()
        body = {
            "schema": "SLOS_HYPERPERFORMANCE_FABRIC_PLAN_V1",
            "mission_id": mission.mission_id,
            "mission_ir_sha256": mission.compiled_sha256,
            "lane_ids": [item.lane_id for item in plan.lanes],
            "deferred_transition_ids": list(plan.deferred_transition_ids),
            "algorithm": plan.algorithm,
            "twin_snapshot_sha256": twin_snapshot["snapshot_sha256"],
            "mission_semantic_owner": "SLOS",
            "transaction_kernel": "SOL_6_2_KERNEL",
            "provider_effect_plane": "SOVARA",
            "provider_effect_performed": False,
        }
        return FabricPlanReceipt(
            mission_ir=mission,
            parallel_plan=plan,
            twin_snapshot_sha256=twin_snapshot["snapshot_sha256"],
            receipt_sha256=_digest(body),
            provider_effect_performed=False,
        )

    def rank_counterfactuals(
        self,
        mission: MissionIR,
        interventions: Sequence[Intervention],
    ) -> tuple[SimulationResult, ...]:
        return CounterfactualController(self.twin).rank(mission, interventions)

    def architecture_receipt(self) -> dict[str, Any]:
        base = self.convergence.architecture_receipt()
        return base | {
            "schema": "SLOS_HYPERPERFORMANCE_EXECUTION_FABRIC_V1",
            "mission_compiler": "MISSION_IR_V1",
            "capability_graph": "SLOS_CAPABILITY_GRAPH_V1",
            "parallel_scheduler": "CP_VOI_BOUNDED_BEAM_V1",
            "digital_twin": "FEDERATION_DIGITAL_TWIN_V1",
            "shadow_evolution": "GOVERNED_CHAMPION_CHALLENGER",
            "speculative_provider_mutation": False,
            "provider_effect_performed": False,
        }


__all__ = ["FabricPlanReceipt", "HyperperformanceExecutionFabric"]
