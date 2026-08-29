"""CFBE-Ω vNext bridge for SOVARA v4 mission-data readiness.

This module is deliberately provider-neutral and effect-free.  It does not
create mission data, promote a v4 module from synthetic fixtures, or weaken the
CFBE evolution gate.  Its job is to resolve semantically equivalent telemetry
keys into the canonical v4 contract vocabulary and fail closed on ambiguity.

The first receiver is ``V4_OBJECTIVE_ECOLOGY``.  The SOVARA MCF telemetry
emitter currently uses ``sovara.outcome.accepted`` and
``sovara.mission.{value,cost,risk}``, while the v4 contract requires
``mission.{accepted,value,cost,risk}``.  This adapter lets CFBE consume the
existing evidence without duplicating telemetry or pretending that source
instrumentation is real mission evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


OBJECTIVE_ECOLOGY_MODULE_ID = "V4_OBJECTIVE_ECOLOGY"
OBJECTIVE_ECOLOGY_REQUIRED_FIELDS: tuple[str, ...] = (
    "mission.accepted",
    "mission.value",
    "mission.cost",
    "mission.risk",
)

REAL_MISSION_EVIDENCE = "REAL_MISSION"

# Canonical field -> accepted telemetry spellings.  Aliases are admitted only
# where the existing source semantics are equivalent.  We intentionally do not
# alias fields such as ``mission.resource_cost`` to ``mission.cost`` because the
# v4 portfolio contract may require a different accounting definition.
V4_FIELD_ALIASES: Mapping[str, tuple[str, ...]] = {
    "mission.accepted": ("mission.accepted", "sovara.outcome.accepted"),
    "mission.value": ("mission.value", "sovara.mission.value"),
    "mission.cost": ("mission.cost", "sovara.mission.cost"),
    "mission.risk": ("mission.risk", "sovara.mission.risk"),
    "mission.dependencies": ("mission.dependencies", "sovara.mission.dependencies"),
    "route.context": ("route.context", "sovara.route.context"),
    "route.outcome": ("route.outcome", "sovara.route.outcome"),
    "route.counterfactual": ("route.counterfactual", "sovara.route.counterfactual"),
    "mission.checkpoint": ("mission.checkpoint", "sovara.mission.checkpoint"),
    "capability.state": ("capability.state", "sovara.capability.state"),
    "resource.state": ("resource.state", "sovara.resource.state"),
    "opportunity.gradient": ("opportunity.gradient", "sovara.opportunity.gradient"),
    "capability.gap": ("capability.gap", "sovara.capability.gap"),
    "regression.baseline": ("regression.baseline", "sovara.regression.baseline"),
    "owner.intervention_seconds": (
        "owner.intervention_seconds",
        "sovara.owner.intervention_seconds",
    ),
}


@dataclass(frozen=True)
class MissionTelemetryEvidence:
    """One provenance-bound telemetry record supplied to the v4 readiness gate."""

    mission_id: str
    telemetry: Mapping[str, Any]
    evidence_refs: tuple[str, ...]
    evidence_class: str


@dataclass(frozen=True)
class FieldResolution:
    canonical_field: str
    value: Any | None
    source_keys: tuple[str, ...]
    conflict: bool = False


@dataclass(frozen=True)
class V4DataReadinessReport:
    module_id: str
    state: str
    qualifying_mission_ids: tuple[str, ...]
    missing_fields: tuple[str, ...]
    conflict_fields: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    truth_boundary: str


def resolve_field(telemetry: Mapping[str, Any], canonical_field: str) -> FieldResolution:
    aliases = V4_FIELD_ALIASES.get(canonical_field, (canonical_field,))
    present = tuple(key for key in aliases if key in telemetry and telemetry[key] is not None)
    if not present:
        return FieldResolution(canonical_field, None, ())

    values = [telemetry[key] for key in present]
    first = values[0]
    if any(value != first for value in values[1:]):
        return FieldResolution(canonical_field, None, present, conflict=True)
    return FieldResolution(canonical_field, first, present)


def normalize_fields(
    telemetry: Mapping[str, Any],
    required_fields: Sequence[str],
) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]:
    resolved: dict[str, Any] = {}
    missing: list[str] = []
    conflicts: list[str] = []
    for field in required_fields:
        resolution = resolve_field(telemetry, field)
        if resolution.conflict:
            conflicts.append(field)
        elif not resolution.source_keys:
            missing.append(field)
        else:
            resolved[field] = resolution.value
    return resolved, tuple(sorted(missing)), tuple(sorted(conflicts))


def _objective_values_valid(values: Mapping[str, Any]) -> bool:
    if not isinstance(values.get("mission.accepted"), bool):
        return False
    for field in ("mission.value", "mission.cost", "mission.risk"):
        value = values.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if float(value) < 0.0:
            return False
    return True


def evaluate_objective_ecology_readiness(
    records: Sequence[MissionTelemetryEvidence],
) -> V4DataReadinessReport:
    """Evaluate the first v4 module without manufacturing DATA_READY.

    ``DATA_READY`` requires at least one *single* real mission record that:
    - resolves every required field without alias conflict;
    - carries explicit provenance references; and
    - contains type-valid, non-negative value/cost/risk telemetry.

    Fields are never stitched together across separate missions.
    """

    qualifying: list[str] = []
    evidence_refs: set[str] = set()
    aggregate_missing: set[str] = set()
    aggregate_conflicts: set[str] = set()
    saw_real_mission = False
    saw_provenance_gap = False
    saw_invalid_values = False

    for record in records:
        values, missing, conflicts = normalize_fields(
            record.telemetry,
            OBJECTIVE_ECOLOGY_REQUIRED_FIELDS,
        )
        aggregate_missing.update(missing)
        aggregate_conflicts.update(conflicts)

        if record.evidence_class != REAL_MISSION_EVIDENCE:
            continue
        saw_real_mission = True
        if not record.evidence_refs:
            saw_provenance_gap = True
            continue
        if missing or conflicts:
            continue
        if not _objective_values_valid(values):
            saw_invalid_values = True
            continue

        mission_id = str(record.mission_id).strip()
        if not mission_id:
            continue
        qualifying.append(mission_id)
        evidence_refs.update(str(ref).strip() for ref in record.evidence_refs if str(ref).strip())

    if aggregate_conflicts:
        state = "HELD_FIELD_CONFLICT"
    elif qualifying:
        state = "DATA_READY"
        aggregate_missing.clear()
    elif saw_provenance_gap:
        state = "HELD_PROVENANCE_REQUIRED"
    elif saw_invalid_values:
        state = "HELD_INVALID_VALUE_TELEMETRY"
    elif saw_real_mission:
        state = "INSTRUMENTED_MISSING_REQUIRED_DATA"
    else:
        state = "INSTRUMENTED_REAL_MISSION_DATA_REQUIRED"

    return V4DataReadinessReport(
        module_id=OBJECTIVE_ECOLOGY_MODULE_ID,
        state=state,
        qualifying_mission_ids=tuple(sorted(set(qualifying))),
        missing_fields=tuple(sorted(aggregate_missing)),
        conflict_fields=tuple(sorted(aggregate_conflicts)),
        evidence_refs=tuple(sorted(evidence_refs)),
        truth_boundary=(
            "Semantic alias resolution and source instrumentation do not prove a real mission, "
            "positive expected value, module incubation, provider execution, or operational maturity."
        ),
    )
