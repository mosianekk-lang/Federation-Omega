"""Pre-registration helper for CFBE Evidence Autopilot mission measurement contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .evidence_autopilot import (
    DimensionMeasurementContract,
    ExperimentMeasurementContract,
)


DEFAULT_METRIC_KEYS = {
    "expected_information_gain": "cfbe.information.questions_resolved",
    "mission_value": "sovara.mission.value",
    "proof_strength_gain": "cfbe.proof.axes_gained",
    "reversibility": "sovara.rollback.available",
    "estimated_cost": "sovara.mission.cost",
    "latency_burden": "sovara.mission.elapsed_seconds",
    "owner_burden": "sovara.owner.intervention_seconds",
    "risk": "sovara.mission.risk",
}


@dataclass(frozen=True)
class MissionMeasurementBounds:
    information_questions_targeted: float
    mission_value_target: float
    proof_axes_targeted: float
    max_cost: float
    latency_ceiling_seconds: float
    owner_intervention_ceiling_seconds: float
    risk_ceiling: float
    bound_refs: Mapping[str, str]

    def denominator_for(self, dimension: str) -> float:
        values = {
            "expected_information_gain": self.information_questions_targeted,
            "mission_value": self.mission_value_target,
            "proof_strength_gain": self.proof_axes_targeted,
            "reversibility": 1.0,
            "estimated_cost": self.max_cost,
            "latency_burden": self.latency_ceiling_seconds,
            "owner_burden": self.owner_intervention_ceiling_seconds,
            "risk": self.risk_ceiling,
        }
        return float(values[dimension])


def build_mission_measurement_contract(
    *,
    experiment_id: str,
    label: str,
    observation_ids: Mapping[str, str],
    bounds: MissionMeasurementBounds,
    experiment_evidence_refs: tuple[str, ...],
) -> ExperimentMeasurementContract:
    """Create the exact eight-dimension contract before observations are measured."""
    expected_dimensions = set(DEFAULT_METRIC_KEYS)
    if set(observation_ids) != expected_dimensions:
        missing = sorted(expected_dimensions - set(observation_ids))
        extra = sorted(set(observation_ids) - expected_dimensions)
        raise ValueError(
            "MISSION_MEASUREMENT_OBSERVATION_BINDING_INCOMPLETE:"
            f"missing={','.join(missing) or '-'};extra={','.join(extra) or '-'}"
        )
    if set(bounds.bound_refs) != expected_dimensions:
        missing = sorted(expected_dimensions - set(bounds.bound_refs))
        extra = sorted(set(bounds.bound_refs) - expected_dimensions)
        raise ValueError(
            "MISSION_MEASUREMENT_BOUND_PROVENANCE_INCOMPLETE:"
            f"missing={','.join(missing) or '-'};extra={','.join(extra) or '-'}"
        )

    dimensions = []
    for dimension in sorted(expected_dimensions):
        denominator = bounds.denominator_for(dimension)
        if denominator <= 0.0:
            raise ValueError(f"MISSION_MEASUREMENT_BOUND_MUST_BE_POSITIVE:{dimension}")
        dimensions.append(
            DimensionMeasurementContract(
                dimension=dimension,
                observation_id=observation_ids[dimension],
                metric_key=DEFAULT_METRIC_KEYS[dimension],
                denominator=denominator,
                denominator_ref=bounds.bound_refs[dimension],
                semantics=(
                    f"observed {DEFAULT_METRIC_KEYS[dimension]} / pre-registered {dimension} bound"
                ),
            )
        )
    return ExperimentMeasurementContract(
        experiment_id=experiment_id,
        label=label,
        experiment_evidence_refs=experiment_evidence_refs,
        dimensions=tuple(dimensions),
    )
