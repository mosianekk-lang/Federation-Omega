"""CFBE-Ω vNext observed experiment measurement normalizer.

This adapter closes a narrow evidence gap between live Federation measurements and
Frontier Convergence OS ``ExperimentOption`` economics. It does not invent scores,
map qualitative labels such as HIGH/LOW into numbers, or promote synthetic fixtures.

Every normalized dimension must be derived from an observed numerator/denominator
pair with provenance. Benefit dimensions are measured as achieved / target.
Burden dimensions are measured as observed burden / approved ceiling.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping

from frontier_convergence.os_core import ExperimentOption


OBSERVED_MEASUREMENT_EVIDENCE = "OBSERVED_FEDERATION_MEASUREMENT"
OBSERVED_EXPERIMENT_EVIDENCE = "OBSERVED_FEDERATION_EXPERIMENT"

BENEFIT_DIMENSIONS = frozenset(
    {
        "expected_information_gain",
        "mission_value",
        "proof_strength_gain",
        "reversibility",
    }
)
BURDEN_DIMENSIONS = frozenset(
    {
        "estimated_cost",
        "latency_burden",
        "owner_burden",
        "risk",
    }
)
REQUIRED_DIMENSIONS = BENEFIT_DIMENSIONS | BURDEN_DIMENSIONS


def _clean_refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


@dataclass(frozen=True)
class ObservedDimensionMeasurement:
    """One provenance-bound measurement used to derive a normalized FC-OS field."""

    experiment_id: str
    dimension: str
    numerator: float
    denominator: float
    evidence_refs: tuple[str, ...]
    evidence_class: str = OBSERVED_MEASUREMENT_EVIDENCE
    synthetic: bool = False

    def normalized_value(self) -> float:
        experiment_id = str(self.experiment_id).strip()
        if not experiment_id:
            raise ValueError("OBSERVED_EXPERIMENT_ID_REQUIRED")
        if self.dimension not in REQUIRED_DIMENSIONS:
            raise ValueError(f"UNKNOWN_EXPERIMENT_DIMENSION:{self.dimension}")
        if self.evidence_class != OBSERVED_MEASUREMENT_EVIDENCE or self.synthetic:
            raise ValueError(f"OBSERVED_MEASUREMENT_REQUIRED:{self.dimension}")
        if not _clean_refs(self.evidence_refs):
            raise ValueError(f"MEASUREMENT_PROVENANCE_REQUIRED:{self.dimension}")
        try:
            numerator = float(self.numerator)
            denominator = float(self.denominator)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"MEASUREMENT_NUMERIC_VALUE_REQUIRED:{self.dimension}") from exc
        if not math.isfinite(numerator) or not math.isfinite(denominator):
            raise ValueError(f"MEASUREMENT_NON_FINITE:{self.dimension}")
        if denominator <= 0.0:
            raise ValueError(f"MEASUREMENT_DENOMINATOR_MUST_BE_POSITIVE:{self.dimension}")
        if numerator < 0.0:
            raise ValueError(f"MEASUREMENT_NUMERATOR_MUST_BE_NON_NEGATIVE:{self.dimension}")
        if numerator > denominator:
            raise ValueError(f"MEASUREMENT_EXCEEDS_DECLARED_BOUND:{self.dimension}")
        return round(numerator / denominator, 9)


@dataclass(frozen=True)
class ObservedExperimentMeasurements:
    """Complete measured evidence packet for one real Federation experiment."""

    experiment_id: str
    label: str
    measurements: tuple[ObservedDimensionMeasurement, ...]
    experiment_evidence_refs: tuple[str, ...]
    evidence_class: str = OBSERVED_EXPERIMENT_EVIDENCE
    synthetic: bool = False


@dataclass(frozen=True)
class ObservedExperimentNormalizationReport:
    experiment_id: str
    state: str
    normalized_values: Mapping[str, float]
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]
    option: ExperimentOption | None
    truth_boundary: str


def evaluate_observed_experiment(
    packet: ObservedExperimentMeasurements,
) -> ObservedExperimentNormalizationReport:
    """Compile an FC-OS option only from complete measured evidence.

    The normalizer deliberately refuses qualitative/categorical value inference,
    synthetic evidence, cross-experiment stitching, duplicate dimensions, missing
    provenance, missing dimensions, and values outside their declared bounds.
    """

    blockers: set[str] = set()
    experiment_id = str(packet.experiment_id).strip()
    label = " ".join(str(packet.label).split())
    refs = set(_clean_refs(packet.experiment_evidence_refs))

    if not experiment_id:
        blockers.add("EXPERIMENT_ID_REQUIRED")
    if not label:
        blockers.add("EXPERIMENT_LABEL_REQUIRED")
    if packet.evidence_class != OBSERVED_EXPERIMENT_EVIDENCE or packet.synthetic:
        blockers.add("OBSERVED_EXPERIMENT_EVIDENCE_REQUIRED")
    if not refs:
        blockers.add("EXPERIMENT_PROVENANCE_REQUIRED")

    normalized: dict[str, float] = {}
    seen: set[str] = set()
    for measurement in packet.measurements:
        if measurement.dimension in seen:
            blockers.add(f"DUPLICATE_DIMENSION:{measurement.dimension}")
            continue
        seen.add(measurement.dimension)
        if str(measurement.experiment_id).strip() != experiment_id:
            blockers.add(f"CROSS_EXPERIMENT_STITCHING_PROHIBITED:{measurement.dimension}")
            continue
        try:
            normalized[measurement.dimension] = measurement.normalized_value()
        except (TypeError, ValueError) as exc:
            blockers.add(str(exc))
            continue
        refs.update(_clean_refs(measurement.evidence_refs))

    missing = sorted(REQUIRED_DIMENSIONS - set(normalized))
    blockers.update(f"MISSING_DIMENSION:{dimension}" for dimension in missing)

    option: ExperimentOption | None = None
    if not blockers:
        option = ExperimentOption.create(
            label=label,
            expected_information_gain=normalized["expected_information_gain"],
            mission_value=normalized["mission_value"],
            proof_strength_gain=normalized["proof_strength_gain"],
            reversibility=normalized["reversibility"],
            estimated_cost=normalized["estimated_cost"],
            latency_burden=normalized["latency_burden"],
            owner_burden=normalized["owner_burden"],
            risk=normalized["risk"],
            evidence_refs=tuple(sorted(refs)),
        )
        state = "OBSERVED_OPTION_READY"
    elif any(
        item.startswith("CROSS_EXPERIMENT_STITCHING")
        or item.startswith("DUPLICATE_DIMENSION")
        for item in blockers
    ):
        state = "HELD_MEASUREMENT_CONFLICT"
    elif "OBSERVED_EXPERIMENT_EVIDENCE_REQUIRED" in blockers:
        state = "HELD_OBSERVED_EXPERIMENT_REQUIRED"
    elif any(item.startswith("OBSERVED_MEASUREMENT_REQUIRED") for item in blockers):
        state = "HELD_OBSERVED_MEASUREMENT_REQUIRED"
    elif (
        any(item.startswith("MEASUREMENT_PROVENANCE_REQUIRED") for item in blockers)
        or "EXPERIMENT_PROVENANCE_REQUIRED" in blockers
    ):
        state = "HELD_PROVENANCE_REQUIRED"
    else:
        state = "INSTRUMENTED_MEASUREMENTS_INCOMPLETE"

    return ObservedExperimentNormalizationReport(
        experiment_id=experiment_id,
        state=state,
        normalized_values=dict(sorted(normalized.items())),
        evidence_refs=tuple(sorted(refs)),
        blockers=tuple(sorted(blockers)),
        option=option,
        truth_boundary=(
            "OBSERVED_OPTION_READY proves only that all eight FC-OS experiment economics "
            "were deterministically normalized from provenance-bound observed measurements. "
            "It does not prove Foundry DATA_READY, positive expected value, incubation, "
            "provider execution, operational maturity, or promotion."
        ),
    )
