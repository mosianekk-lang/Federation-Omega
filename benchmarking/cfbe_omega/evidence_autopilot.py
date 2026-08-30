"""CFBE-Ω Evidence Autopilot Compiler.

Compile existing Federation telemetry/receipts into canonical V4 experiment
measurement rows without inventing scores. The compiler is deliberately narrow:
every FC-OS dimension must name an exact observation, metric, denominator and
provenance reference. It performs no provider calls, no Sheets writes and no
promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Mapping, Sequence

from .measurement_sheet_ingestion import assemble_observed_experiment_rows
from .observed_experiment_normalization import (
    REQUIRED_DIMENSIONS,
    evaluate_observed_experiment,
)


AUTOPILOT_ID = "CFBE_EVIDENCE_AUTOPILOT_V1"


@dataclass(frozen=True)
class MetricObservation:
    observation_id: str
    experiment_id: str
    observed_at_sast: str
    source_system: str
    source_work_id: str
    metrics: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    synthetic: bool = False


@dataclass(frozen=True)
class DimensionMeasurementContract:
    dimension: str
    observation_id: str
    metric_key: str
    denominator: float
    denominator_ref: str
    semantics: str


@dataclass(frozen=True)
class ExperimentMeasurementContract:
    experiment_id: str
    label: str
    experiment_evidence_refs: tuple[str, ...]
    dimensions: tuple[DimensionMeasurementContract, ...]
    evidence_class: str = "OBSERVED_FEDERATION_EXPERIMENT"


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _refs(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({_text(value) for value in values if _text(value)}))


def _number(value: Any, *, dimension: str) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"OBSERVED_METRIC_NUMERIC_REQUIRED:{dimension}") from exc
    if not math.isfinite(result):
        raise ValueError(f"OBSERVED_METRIC_NON_FINITE:{dimension}")
    return result


def _measurement_id(experiment_id: str, dimension: str, observation_id: str) -> str:
    digest = hashlib.sha256(
        f"{experiment_id}|{dimension}|{observation_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"CFBE-M-{digest}"


def compile_measurement_rows(
    contract: ExperimentMeasurementContract,
    observations: Sequence[MetricObservation],
) -> tuple[dict[str, Any], ...]:
    """Compile canonical V4 sheet rows from exact, provenance-bound observations."""

    experiment_id = _text(contract.experiment_id)
    label = _text(contract.label)
    experiment_refs = _refs(contract.experiment_evidence_refs)
    if not experiment_id:
        raise ValueError("AUTOPILOT_EXPERIMENT_ID_REQUIRED")
    if not label:
        raise ValueError("AUTOPILOT_EXPERIMENT_LABEL_REQUIRED")
    if not experiment_refs:
        raise ValueError("AUTOPILOT_EXPERIMENT_PROVENANCE_REQUIRED")
    if contract.evidence_class != "OBSERVED_FEDERATION_EXPERIMENT":
        raise ValueError("AUTOPILOT_OBSERVED_EXPERIMENT_CLASS_REQUIRED")

    by_id: dict[str, MetricObservation] = {}
    for observation in observations:
        observation_id = _text(observation.observation_id)
        if not observation_id:
            raise ValueError("AUTOPILOT_OBSERVATION_ID_REQUIRED")
        if observation_id in by_id:
            raise ValueError(f"AUTOPILOT_DUPLICATE_OBSERVATION_ID:{observation_id}")
        by_id[observation_id] = observation

    dimensions = [item.dimension for item in contract.dimensions]
    if set(dimensions) != set(REQUIRED_DIMENSIONS) or len(dimensions) != len(REQUIRED_DIMENSIONS):
        missing = sorted(set(REQUIRED_DIMENSIONS) - set(dimensions))
        extra = sorted(set(dimensions) - set(REQUIRED_DIMENSIONS))
        raise ValueError(
            "AUTOPILOT_DIMENSION_CONTRACT_INCOMPLETE:"
            f"missing={','.join(missing) or '-'};extra={','.join(extra) or '-'}"
        )
    if len(set(dimensions)) != len(dimensions):
        raise ValueError("AUTOPILOT_DUPLICATE_DIMENSION_CONTRACT")

    rows: list[dict[str, Any]] = []
    for spec in sorted(contract.dimensions, key=lambda item: item.dimension):
        observation_id = _text(spec.observation_id)
        if observation_id not in by_id:
            raise ValueError(f"AUTOPILOT_OBSERVATION_NOT_FOUND:{spec.dimension}:{observation_id}")
        observation = by_id[observation_id]
        if _text(observation.experiment_id) != experiment_id:
            raise ValueError(f"AUTOPILOT_CROSS_EXPERIMENT_OBSERVATION:{spec.dimension}")
        if observation.synthetic:
            raise ValueError(f"AUTOPILOT_SYNTHETIC_OBSERVATION_REJECTED:{spec.dimension}")
        evidence_refs = _refs(observation.evidence_refs)
        if not evidence_refs:
            raise ValueError(f"AUTOPILOT_OBSERVATION_PROVENANCE_REQUIRED:{spec.dimension}")
        metric_key = _text(spec.metric_key)
        if not metric_key or metric_key not in observation.metrics:
            raise ValueError(f"AUTOPILOT_METRIC_NOT_FOUND:{spec.dimension}:{metric_key or '-'}")
        numerator = _number(observation.metrics[metric_key], dimension=spec.dimension)
        denominator = _number(spec.denominator, dimension=spec.dimension)
        if denominator <= 0.0:
            raise ValueError(f"MEASUREMENT_DENOMINATOR_MUST_BE_POSITIVE:{spec.dimension}")
        if numerator < 0.0:
            raise ValueError(f"MEASUREMENT_NUMERATOR_MUST_BE_NON_NEGATIVE:{spec.dimension}")
        if numerator > denominator:
            raise ValueError(f"MEASUREMENT_EXCEEDS_DECLARED_BOUND:{spec.dimension}")
        denominator_ref = _text(spec.denominator_ref)
        if not denominator_ref:
            raise ValueError(f"AUTOPILOT_DENOMINATOR_PROVENANCE_REQUIRED:{spec.dimension}")
        semantics = _text(spec.semantics)
        if not semantics:
            raise ValueError(f"AUTOPILOT_NORMALIZATION_SEMANTICS_REQUIRED:{spec.dimension}")
        normalized = round(numerator / denominator, 9)
        measurement_refs = _refs((*evidence_refs, denominator_ref))
        rows.append(
            {
                "Measurement_ID": _measurement_id(experiment_id, spec.dimension, observation_id),
                "Observed_At_SAST": _text(observation.observed_at_sast),
                "Experiment_ID": experiment_id,
                "Experiment_Label": label,
                "Dimension": spec.dimension,
                "Numerator": numerator,
                "Denominator": denominator,
                "Normalized_Value": normalized,
                "Measurement_Evidence_Class": "OBSERVED_FEDERATION_MEASUREMENT",
                "Experiment_Evidence_Class": contract.evidence_class,
                "Synthetic": False,
                "Measurement_Evidence_Refs": ";".join(measurement_refs),
                "Experiment_Evidence_Refs": ";".join(experiment_refs),
                "Source_System": _text(observation.source_system),
                "Source_Work_ID": _text(observation.source_work_id) or observation_id,
                "Normalization_Semantics": semantics,
                "Verifier": AUTOPILOT_ID,
                "Verification_Refs": "",
                "State": "OBSERVED_RAW",
                "Truth_Boundary": (
                    "Autopilot mechanically compiled this row from an exact observed metric, "
                    "an explicit denominator and provenance. OBSERVED_RAW is not independent "
                    "verification, DATA_READY, provider proof, value proof or promotion."
                ),
            }
        )
    return tuple(rows)


def compile_observed_experiment(
    contract: ExperimentMeasurementContract,
    observations: Sequence[MetricObservation],
):
    """End-to-end compile into the already-admitted ingestion/normalization path."""
    rows = compile_measurement_rows(contract, observations)
    packet = assemble_observed_experiment_rows(rows, experiment_id=contract.experiment_id)
    return rows, packet, evaluate_observed_experiment(packet)
