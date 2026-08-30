"""Schema-bound ingestion for CFBE V4 experiment measurement rows.

The live CFBE scorecard stores raw experiment measurements as one row per FC-OS
dimension. This adapter converts those rows into the already-admitted observed
experiment normalizer without trusting spreadsheet-computed normalized values.

It is intentionally effect-free: no Sheets access, no writes, no provider calls,
and no score inference from qualitative labels. Callers must supply rows read from
the canonical evidence plane and retain their provider/readback provenance.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .observed_experiment_normalization import (
    ObservedDimensionMeasurement,
    ObservedExperimentMeasurements,
)


ELIGIBLE_MEASUREMENT_STATES = frozenset({"OBSERVED_RAW", "VERIFIED_NORMALIZED"})


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized == "TRUE":
            return True
        if normalized == "FALSE":
            return False
    raise ValueError("MEASUREMENT_SYNTHETIC_BOOLEAN_REQUIRED")


def _parse_refs(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set, frozenset)):
        items = value
    else:
        text = str(value).replace("\r\n", "\n").replace("\n", ";")
        items = text.split(";")
    return tuple(sorted({_clean_text(item) for item in items if _clean_text(item)}))


def _parse_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"MEASUREMENT_{field}_NUMERIC_REQUIRED") from exc
    if not math.isfinite(number):
        raise ValueError(f"MEASUREMENT_{field}_NON_FINITE")
    return number


def _parse_optional_number(value: Any, field: str) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return _parse_number(value, field)


def _derived_ratio(numerator: float, denominator: float, dimension: str) -> float:
    if denominator <= 0.0:
        raise ValueError(f"MEASUREMENT_DENOMINATOR_MUST_BE_POSITIVE:{dimension}")
    if numerator < 0.0:
        raise ValueError(f"MEASUREMENT_NUMERATOR_MUST_BE_NON_NEGATIVE:{dimension}")
    if numerator > denominator:
        raise ValueError(f"MEASUREMENT_EXCEEDS_DECLARED_BOUND:{dimension}")
    return round(numerator / denominator, 9)


def assemble_observed_experiment_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    experiment_id: str | None = None,
) -> ObservedExperimentMeasurements:
    """Assemble one spreadsheet experiment into the canonical observed packet.

    Hard gates:
    - one experiment only; no row filtering or cross-experiment stitching;
    - one stable non-empty experiment label and evidence class;
    - unique non-empty measurement IDs;
    - only raw/verified-normalized row states are eligible;
    - ``Synthetic`` must be an explicit boolean/TRUE/FALSE value;
    - any stored ``Normalized_Value`` is checked against raw numerator/denominator
      and never accepted as the source of truth.
    """

    if not rows:
        raise ValueError("MEASUREMENT_ROWS_REQUIRED")

    observed_ids = {_clean_text(row.get("Experiment_ID")) for row in rows}
    if "" in observed_ids:
        raise ValueError("MEASUREMENT_EXPERIMENT_ID_REQUIRED")
    if experiment_id is not None:
        expected_id = _clean_text(experiment_id)
        if not expected_id:
            raise ValueError("MEASUREMENT_EXPERIMENT_ID_REQUIRED")
        if observed_ids != {expected_id}:
            raise ValueError("MEASUREMENT_MIXED_EXPERIMENT_IDS")
        selected_id = expected_id
    else:
        if len(observed_ids) != 1:
            raise ValueError("MEASUREMENT_MIXED_EXPERIMENT_IDS")
        selected_id = next(iter(observed_ids))

    labels = {_clean_text(row.get("Experiment_Label")) for row in rows}
    if "" in labels:
        raise ValueError("MEASUREMENT_EXPERIMENT_LABEL_REQUIRED")
    if len(labels) != 1:
        raise ValueError("MEASUREMENT_EXPERIMENT_LABEL_CONFLICT")
    label = next(iter(labels))

    evidence_classes = {_clean_text(row.get("Experiment_Evidence_Class")) for row in rows}
    if "" in evidence_classes:
        raise ValueError("MEASUREMENT_EXPERIMENT_EVIDENCE_CLASS_REQUIRED")
    if len(evidence_classes) != 1:
        raise ValueError("MEASUREMENT_EXPERIMENT_EVIDENCE_CLASS_CONFLICT")
    experiment_evidence_class = next(iter(evidence_classes))

    measurement_ids: set[str] = set()
    measurements: list[ObservedDimensionMeasurement] = []
    experiment_refs: set[str] = set()
    any_synthetic = False

    for row in rows:
        measurement_id = _clean_text(row.get("Measurement_ID"))
        if not measurement_id:
            raise ValueError("MEASUREMENT_ID_REQUIRED")
        if measurement_id in measurement_ids:
            raise ValueError(f"DUPLICATE_MEASUREMENT_ID:{measurement_id}")
        measurement_ids.add(measurement_id)

        state = _clean_text(row.get("State"))
        if state not in ELIGIBLE_MEASUREMENT_STATES:
            raise ValueError(f"MEASUREMENT_ROW_NOT_ELIGIBLE:{measurement_id}:{state or 'EMPTY'}")

        dimension = _clean_text(row.get("Dimension"))
        numerator = _parse_number(row.get("Numerator"), "NUMERATOR")
        denominator = _parse_number(row.get("Denominator"), "DENOMINATOR")
        expected_normalized = _derived_ratio(numerator, denominator, dimension)
        stored_normalized = _parse_optional_number(row.get("Normalized_Value"), "NORMALIZED_VALUE")
        if stored_normalized is not None and not math.isclose(
            stored_normalized,
            expected_normalized,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(f"NORMALIZED_VALUE_MISMATCH:{measurement_id}")

        synthetic = _parse_bool(row.get("Synthetic"))
        any_synthetic = any_synthetic or synthetic
        measurement_refs = _parse_refs(row.get("Measurement_Evidence_Refs"))
        experiment_refs.update(_parse_refs(row.get("Experiment_Evidence_Refs")))

        measurements.append(
            ObservedDimensionMeasurement(
                experiment_id=selected_id,
                dimension=dimension,
                numerator=numerator,
                denominator=denominator,
                evidence_refs=measurement_refs,
                evidence_class=_clean_text(row.get("Measurement_Evidence_Class")),
                synthetic=synthetic,
            )
        )

    return ObservedExperimentMeasurements(
        experiment_id=selected_id,
        label=label,
        measurements=tuple(measurements),
        experiment_evidence_refs=tuple(sorted(experiment_refs)),
        evidence_class=experiment_evidence_class,
        synthetic=any_synthetic,
    )
