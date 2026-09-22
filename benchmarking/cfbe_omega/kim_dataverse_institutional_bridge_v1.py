from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from benchmarking.cfbe_omega.kim_dataverse_autonomic_control_fabric_v1 import AutonomicEvent, AutonomicWave, compile_autonomic_wave
from benchmarking.cfbe_omega.kim_dataverse_institutional_twin_v1 import CapabilityObservation, InstitutionalTwin, build_institutional_twin
from benchmarking.cfbe_omega.kim_dataverse_level7_plus_v1 import Objective, ObjectiveEcologyResult, objective_ecology
from benchmarking.cfbe_omega.kim_dataverse_level8_frontier_v1 import InformationRoute, TimescaleObjective, FrontierPlan, compile_frontier_plan


@dataclass(frozen=True)
class InstitutionalControlSnapshot:
    objective_ecology: ObjectiveEcologyResult
    autonomic_wave: AutonomicWave
    twin: InstitutionalTwin
    frontier_plan: FrontierPlan | None
    execution_authorized: bool
    external_effect_authorized: bool


def compile_institutional_snapshot(
    *,
    objectives: Sequence[Objective],
    events: Sequence[AutonomicEvent],
    capabilities: Sequence[CapabilityObservation],
    frontier_objectives: Sequence[TimescaleObjective] = (),
    information_routes: Sequence[InformationRoute] = (),
) -> InstitutionalControlSnapshot:
    ecology = objective_ecology(objectives)
    wave = compile_autonomic_wave(events)
    twin = build_institutional_twin(capabilities)
    frontier = None
    if frontier_objectives or information_routes:
        frontier = compile_frontier_plan(frontier_objectives, information_routes)
    return InstitutionalControlSnapshot(
        objective_ecology=ecology,
        autonomic_wave=wave,
        twin=twin,
        frontier_plan=frontier,
        execution_authorized=False,
        external_effect_authorized=False,
    )


def snapshot_truth_boundary(snapshot: InstitutionalControlSnapshot) -> Mapping[str, object]:
    return {
        "objective_count": len(snapshot.objective_ecology.ranked_objectives),
        "autonomic_event_count": len(snapshot.autonomic_wave.decisions),
        "capability_count": len(snapshot.twin.capabilities),
        "frontier_plan_present": snapshot.frontier_plan is not None,
        "execution_authorized": snapshot.execution_authorized,
        "external_effect_authorized": snapshot.external_effect_authorized,
        "truth": "INSTITUTIONAL_CONTROL_SNAPSHOT_ONLY",
    }
