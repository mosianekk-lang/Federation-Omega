"""CFBE-Ω empirical measurement fabric.

This module composes existing Federation telemetry, the 10X measurement doctrine,
FC-OS evidence economics, the canonical V4 measurement-sheet contract and the
observed experiment normalizer. It creates no provider authority and invents no
measurements.

A measurement is eligible only when both sides of its ratio are provenance-bound:
- the observed numerator comes from one Federation observation packet; and
- the target/ceiling denominator comes from an explicit DimensionBound.

Benefit dimensions use observed / target. Burden dimensions use observed / ceiling.
Incomplete evidence remains incomplete; qualitative labels and cross-mission
stitching are not converted into scores.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Iterable, Mapping, Sequence

from frontier_convergence.os_core import EvidenceEconomicsSelector, ExperimentOption

from .measurement_sheet_ingestion import assemble_observed_experiment_rows
from .observed_experiment_normalization import (
    BENEFIT_DIMENSIONS,
    BURDEN_DIMENSIONS,
    OBSERVED_EXPERIMENT_EVIDENCE,
    OBSERVED_MEASUREMENT_EVIDENCE,
    evaluate_observed_experiment,
)

PUBLIC_SYNTHETIC = "PUBLIC_SYNTHETIC"
FABRIC_ID = "CFBE_EMPIRICAL_MEASUREMENT_FABRIC_V1"

DIMENSION_ORDER: tuple[str, ...] = (
    "expected_information_gain",
    "mission_value",
    "proof_strength_gain",
    "reversibility",
    "estimated_cost",
    "latency_burden",
    "owner_burden",
    "risk",
)
REQUIRED_DIMENSIONS = frozenset(DIMENSION_ORDER)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _clean_refs(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({_clean(value) for value in values if _clean(value)}))


def _numeric(value: Any, code: str) -> float:
    if isinstance(value, bool):
        raise ValueError(code)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(code) from exc
    if not math.isfinite(number):
        raise ValueError(code)
    return number


def _measurement_id(experiment_id: str, dimension: str, source_work_id: str) -> str:
    raw = f"{experiment_id}|{dimension}|{source_work_id}".encode("utf-8")
    return f"CFBE-MEAS-{hashlib.sha256(raw).hexdigest()[:24].upper()}"


@dataclass(frozen=True)
class DimensionBound:
    """Provenance-bound target/ceiling and accepted source aliases for one dimension."""

    dimension: str
    source_keys: tuple[str, ...]
    bound: float
    evidence_refs: tuple[str, ...]

    def validate(self) -> None:
        if self.dimension not in REQUIRED_DIMENSIONS:
            raise ValueError(f"UNKNOWN_DIMENSION_BOUND:{self.dimension}")
        if not _clean_refs(self.source_keys):
            raise ValueError(f"DIMENSION_SOURCE_KEYS_REQUIRED:{self.dimension}")
        numeric = _numeric(self.bound, f"DIMENSION_BOUND_NUMERIC_REQUIRED:{self.dimension}")
        if numeric <= 0.0:
            raise ValueError(f"DIMENSION_BOUND_MUST_BE_POSITIVE:{self.dimension}")
        if not _clean_refs(self.evidence_refs):
            raise ValueError(f"DIMENSION_BOUND_PROVENANCE_REQUIRED:{self.dimension}")

    @property
    def semantic_kind(self) -> str:
        if self.dimension in BENEFIT_DIMENSIONS:
            return "BENEFIT_TARGET"
        if self.dimension in BURDEN_DIMENSIONS:
            return "BURDEN_CEILING"
        raise ValueError(f"UNKNOWN_DIMENSION_BOUND:{self.dimension}")


@dataclass(frozen=True)
class FederationObservationPacket:
    """One source/work-item observation envelope; fields are never stitched across packets."""

    experiment_id: str
    label: str
    telemetry: Mapping[str, Any]
    observed_at_sast: str
    source_system: str
    source_work_id: str
    evidence_refs: tuple[str, ...]
    evidence_class: str = OBSERVED_EXPERIMENT_EVIDENCE
    synthetic: bool = False


@dataclass(frozen=True)
class MeasurementFabricReport:
    experiment_id: str
    state: str
    rows: tuple[Mapping[str, Any], ...]
    missing_dimensions: tuple[str, ...]
    conflict_dimensions: tuple[str, ...]
    blockers: tuple[str, ...]
    normalized_state: str | None
    option_key: str | None
    evidence_refs: tuple[str, ...]
    truth_boundary: str


@dataclass(frozen=True)
class AcquisitionRoute:
    """An existing or proposed sensor route expressed through FC-OS economics."""

    route_id: str
    coverage_dimensions: tuple[str, ...]
    option: ExperimentOption


@dataclass(frozen=True)
class AcquisitionPlan:
    state: str
    selected_route_ids: tuple[str, ...]
    unresolved_dimensions: tuple[str, ...]
    route_option_keys: tuple[str, ...]
    truth_boundary: str


def _resolve_aliases(telemetry: Mapping[str, Any], bound: DimensionBound) -> tuple[Any | None, tuple[str, ...], bool]:
    present = tuple(key for key in _clean_refs(bound.source_keys) if key in telemetry and telemetry[key] is not None)
    if not present:
        return None, (), False
    values = [telemetry[key] for key in present]
    first = values[0]
    if any(value != first for value in values[1:]):
        return None, present, True
    return first, present, False


def compile_measurement_rows(
    packet: FederationObservationPacket,
    bounds: Sequence[DimensionBound],
) -> MeasurementFabricReport:
    """Compile canonical V4 measurement rows from one provenance-bound observation.

    The compiler is intentionally conservative: one packet, one experiment, explicit
    denominator provenance and no inferred aliases beyond those declared per bound.
    """

    blockers: set[str] = set()
    missing: set[str] = set()
    conflicts: set[str] = set()
    rows: list[Mapping[str, Any]] = []

    experiment_id = _clean(packet.experiment_id)
    label = _clean(packet.label)
    observed_at = _clean(packet.observed_at_sast)
    source_system = _clean(packet.source_system)
    source_work_id = _clean(packet.source_work_id)
    packet_refs = _clean_refs(packet.evidence_refs)

    if not experiment_id:
        blockers.add("EXPERIMENT_ID_REQUIRED")
    if not label:
        blockers.add("EXPERIMENT_LABEL_REQUIRED")
    if not observed_at:
        blockers.add("OBSERVED_AT_SAST_REQUIRED")
    if not source_system:
        blockers.add("SOURCE_SYSTEM_REQUIRED")
    if not source_work_id:
        blockers.add("SOURCE_WORK_ID_REQUIRED")
    if not packet_refs:
        blockers.add("OBSERVATION_PROVENANCE_REQUIRED")

    expected_class = PUBLIC_SYNTHETIC if packet.synthetic else OBSERVED_EXPERIMENT_EVIDENCE
    if packet.evidence_class != expected_class:
        blockers.add("OBSERVATION_EVIDENCE_CLASS_MISMATCH")

    bound_map: dict[str, DimensionBound] = {}
    for bound in bounds:
        if bound.dimension in bound_map:
            blockers.add(f"DUPLICATE_DIMENSION_BOUND:{bound.dimension}")
            continue
        try:
            bound.validate()
        except ValueError as exc:
            blockers.add(str(exc))
            continue
        bound_map[bound.dimension] = bound

    for dimension in DIMENSION_ORDER:
        bound = bound_map.get(dimension)
        if bound is None:
            missing.add(dimension)
            continue
        value, source_keys, conflict = _resolve_aliases(packet.telemetry, bound)
        if conflict:
            conflicts.add(dimension)
            continue
        if not source_keys:
            missing.add(dimension)
            continue
        try:
            observed = _numeric(value, f"OBSERVED_DIMENSION_NUMERIC_REQUIRED:{dimension}")
        except ValueError as exc:
            blockers.add(str(exc))
            continue
        denominator = float(bound.bound)
        if observed < 0.0:
            blockers.add(f"OBSERVED_DIMENSION_NEGATIVE:{dimension}")
            continue
        if observed > denominator:
            blockers.add(f"OBSERVED_DIMENSION_EXCEEDS_BOUND:{dimension}")
            continue

        normalized = round(observed / denominator, 9)
        measurement_refs = _clean_refs((*packet_refs, *bound.evidence_refs))
        measurement_evidence_class = PUBLIC_SYNTHETIC if packet.synthetic else OBSERVED_MEASUREMENT_EVIDENCE
        semantics = (
            "benefit=observed/target"
            if bound.semantic_kind == "BENEFIT_TARGET"
            else "burden=observed/ceiling"
        )
        truth = (
            "Observed raw measurement compiled from explicit source aliases plus a provenance-bound "
            "target/ceiling. This row does not itself prove V4 DATA_READY, positive expected value, "
            "provider execution, behavioral maturity or promotion."
        )
        rows.append(
            {
                "Measurement_ID": _measurement_id(experiment_id, dimension, source_work_id),
                "Observed_At_SAST": observed_at,
                "Experiment_ID": experiment_id,
                "Experiment_Label": label,
                "Dimension": dimension,
                "Numerator": observed,
                "Denominator": denominator,
                "Normalized_Value": normalized,
                "Measurement_Evidence_Class": measurement_evidence_class,
                "Experiment_Evidence_Class": packet.evidence_class,
                "Synthetic": packet.synthetic,
                "Measurement_Evidence_Refs": ";".join(measurement_refs),
                "Experiment_Evidence_Refs": ";".join(packet_refs),
                "Source_System": source_system,
                "Source_Work_ID": source_work_id,
                "Normalization_Semantics": semantics,
                "Verifier": FABRIC_ID,
                "Verification_Refs": ";".join(_clean_refs(bound.evidence_refs)),
                "State": "OBSERVED_RAW",
                "Truth_Boundary": truth,
            }
        )

    normalized_state: str | None = None
    option_key: str | None = None
    if conflicts:
        state = "HELD_FIELD_CONFLICT"
    elif blockers:
        state = "HELD_INVALID_MEASUREMENT"
    elif missing:
        state = "PARTIAL_MEASUREMENT_PACKET"
    elif packet.synthetic:
        assembled = assemble_observed_experiment_rows(rows)
        normalized = evaluate_observed_experiment(assembled)
        normalized_state = normalized.state
        state = "SYNTHETIC_PACKET_HELD_BY_DESIGN"
    else:
        assembled = assemble_observed_experiment_rows(rows)
        normalized = evaluate_observed_experiment(assembled)
        normalized_state = normalized.state
        option_key = normalized.option.option_key if normalized.option is not None else None
        state = "MEASUREMENT_PACKET_READY" if normalized.state == "OBSERVED_OPTION_READY" else "HELD_NORMALIZATION_GATE"

    evidence = set(packet_refs)
    for bound in bound_map.values():
        evidence.update(_clean_refs(bound.evidence_refs))

    return MeasurementFabricReport(
        experiment_id=experiment_id,
        state=state,
        rows=tuple(rows),
        missing_dimensions=tuple(sorted(missing)),
        conflict_dimensions=tuple(sorted(conflicts)),
        blockers=tuple(sorted(blockers)),
        normalized_state=normalized_state,
        option_key=option_key,
        evidence_refs=tuple(sorted(evidence)),
        truth_boundary=(
            "MEASUREMENT_PACKET_READY proves only deterministic compilation of all eight FC-OS economics "
            "from one provenance-bound observation packet and explicit provenance-bound bounds. It does not "
            "prove Foundry DATA_READY, positive expected value, incubation, provider execution, repeated success, "
            "soak, production qualification or a 10x claim."
        ),
    )


def plan_measurement_acquisition(
    missing_dimensions: Iterable[str],
    routes: Sequence[AcquisitionRoute],
) -> AcquisitionPlan:
    """Greedy set-cover planner with FC-OS evidence economics as the tie-break court.

    The planner never manufactures a measurement. It only chooses the smallest useful
    sequence of declared sensor routes. New-coverage count is the primary objective;
    the existing FC-OS information-value score breaks ties.
    """

    remaining = set(_clean_refs(missing_dimensions))
    unknown = remaining - REQUIRED_DIMENSIONS
    if unknown:
        raise ValueError("UNKNOWN_MISSING_DIMENSION:" + ",".join(sorted(unknown)))

    route_map: dict[str, AcquisitionRoute] = {}
    for route in routes:
        route_id = _clean(route.route_id)
        if not route_id:
            raise ValueError("ACQUISITION_ROUTE_ID_REQUIRED")
        if route_id in route_map:
            raise ValueError(f"DUPLICATE_ACQUISITION_ROUTE:{route_id}")
        coverage = set(_clean_refs(route.coverage_dimensions))
        unknown_coverage = coverage - REQUIRED_DIMENSIONS
        if unknown_coverage:
            raise ValueError(
                f"UNKNOWN_ROUTE_COVERAGE:{route_id}:" + ",".join(sorted(unknown_coverage))
            )
        if not coverage:
            raise ValueError(f"ACQUISITION_ROUTE_COVERAGE_REQUIRED:{route_id}")
        if not route.option.evidence_refs:
            raise ValueError(f"ACQUISITION_ROUTE_EVIDENCE_REQUIRED:{route_id}")
        route_map[route_id] = route

    selected: list[AcquisitionRoute] = []
    unused = dict(route_map)
    while remaining:
        candidates: list[tuple[int, AcquisitionRoute]] = []
        for route in unused.values():
            new_coverage = remaining.intersection(route.coverage_dimensions)
            if new_coverage:
                candidates.append((len(new_coverage), route))
        if not candidates:
            break
        max_coverage = max(count for count, _ in candidates)
        tied = [route for count, route in candidates if count == max_coverage]
        ranked_options = EvidenceEconomicsSelector.rank(route.option for route in tied)
        winning_option = ranked_options[0]
        winner = next(route for route in tied if route.option.option_key == winning_option.option_key)
        selected.append(winner)
        remaining.difference_update(winner.coverage_dimensions)
        unused.pop(winner.route_id, None)

    return AcquisitionPlan(
        state="ACQUISITION_PLAN_READY" if not remaining else "ACQUISITION_PLAN_PARTIAL",
        selected_route_ids=tuple(route.route_id for route in selected),
        unresolved_dimensions=tuple(sorted(remaining)),
        route_option_keys=tuple(route.option.option_key for route in selected),
        truth_boundary=(
            "The acquisition plan ranks declared evidence-collection routes only. It does not prove the route "
            "exists at runtime, authorize provider effects or convert expected route economics into observed data."
        ),
    )


def plan_from_report(
    report: MeasurementFabricReport,
    routes: Sequence[AcquisitionRoute],
) -> AcquisitionPlan:
    return plan_measurement_acquisition(report.missing_dimensions, routes)


def bounds_from_10x_rollout_stage(
    stage_policy: Mapping[str, Any],
    *,
    evidence_refs: Iterable[str],
) -> tuple[DimensionBound, DimensionBound]:
    """Compile existing SOVARA 10X rollout ceilings into CFBE burden bounds.

    This adapter intentionally maps only semantically exact, unit-stable metrics:
    `maximum_cost_per_accepted_mission_usd` -> `estimated_cost`, and
    `maximum_p95_latency_ms` -> `latency_burden`.

    Mission-level aggregate cost or elapsed time are not aliases for these metrics.
    The source rollout-policy evidence reference is mandatory so denominator values
    remain auditable instead of becoming magic constants.
    """

    refs = _clean_refs(evidence_refs)
    if not refs:
        raise ValueError("ROLLOUT_STAGE_PROVENANCE_REQUIRED")

    latency = _numeric(
        stage_policy.get("maximum_p95_latency_ms"),
        "ROLLOUT_STAGE_P95_LATENCY_CEILING_REQUIRED",
    )
    cost = _numeric(
        stage_policy.get("maximum_cost_per_accepted_mission_usd"),
        "ROLLOUT_STAGE_COST_CEILING_REQUIRED",
    )
    if latency <= 0.0:
        raise ValueError("ROLLOUT_STAGE_P95_LATENCY_CEILING_MUST_BE_POSITIVE")
    if cost <= 0.0:
        raise ValueError("ROLLOUT_STAGE_COST_CEILING_MUST_BE_POSITIVE")

    return (
        DimensionBound(
            dimension="estimated_cost",
            source_keys=(
                "cost_per_accepted_mission_usd",
                "sovara.10x.cost_per_accepted_mission_usd",
            ),
            bound=cost,
            evidence_refs=refs,
        ),
        DimensionBound(
            dimension="latency_burden",
            source_keys=("p95_latency_ms", "sovara.10x.p95_latency_ms"),
            bound=latency,
            evidence_refs=refs,
        ),
    )
