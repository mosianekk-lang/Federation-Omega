from __future__ import annotations

"""Read-only cohort census for prospective EDPF prediction evidence.

The census reports whether a source-epoch/matter cohort has enough resolved
prospective observations to enter the already-admitted Shadow Prediction Court.
It does not evaluate calibration quality, alter predictor weights, or create a
second persistence layer.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from benchmarking.cfbe_omega.edpf_shadow_prediction_court_v1 import (
    MIN_HOLDOUT_PAIRS,
    MIN_INDEPENDENT_SOURCES,
    MIN_PREDICTORS,
    MIN_REAL_PAIRS,
)
from .edpf_prediction_adapter import (
    OPEN_STATE,
    RESOLVED_FALSE_STATE,
    RESOLVED_TRUE_STATE,
    SCHEMA as INTAKE_SCHEMA,
    compile_real_shadow_pairs,
)
from .types import NodeKind

SCHEMA = "SOVARA_EDPF_PROSPECTIVE_COHORT_CENSUS_V1"


@dataclass(frozen=True, slots=True)
class CohortReadiness:
    source_head_sha: str
    matter_scope: str
    open_count: int
    resolved_count: int
    occurred_count: int
    not_occurred_count: int
    predictor_ids: tuple[str, ...]
    predictor_count: int
    source_fingerprints: tuple[str, ...]
    independent_source_count: int
    domains: tuple[str, ...]
    domain_count: int
    possible_holdout_count: int
    additional_resolutions_needed: int
    additional_predictors_needed: int
    additional_independent_sources_needed: int
    count_ready_for_shadow_court: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CohortCensusReceipt:
    schema: str
    cohort_count: int
    total_open: int
    total_resolved: int
    count_ready_cohorts: int
    cohorts: tuple[CohortReadiness, ...]
    empirical_calibration_evaluated: bool
    empirical_calibration_proven: bool
    owner_value_proven: bool
    live_predictor_weights_changed: bool
    live_predictor_weight_change_authorized: bool
    dispatch_authorized: bool
    external_effect_authorized: bool
    stable_self_promotion_allowed: bool
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _kind_value(value: object) -> str:
    return value.value if isinstance(value, NodeKind) else str(value)


def _prediction_nodes(events: Sequence[Mapping[str, Any]]) -> dict[str, list[tuple[int, Mapping[str, Any]]]]:
    nodes: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
    for raw_event in events:
        if str(raw_event.get("event_type")) != "NODE_OBSERVED":
            continue
        sequence = int(raw_event.get("sequence", 0))
        node = dict(dict(raw_event.get("payload", {})).get("node", {}))
        if _kind_value(node.get("kind")) not in (NodeKind.EXPERIMENT.value, str(NodeKind.EXPERIMENT)):
            continue
        payload = dict(node.get("payload", {}))
        if payload.get("schema") != INTAKE_SCHEMA or not payload.get("prospective_capture"):
            continue
        node_id = str(node.get("node_id", ""))
        if not node_id:
            raise ValueError("EDPF_CENSUS_NODE_ID_REQUIRED")
        nodes.setdefault(node_id, []).append((sequence, node))
    return nodes


def _latest_states(events: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    open_nodes: dict[str, Mapping[str, Any]] = {}
    resolved_nodes: dict[str, Mapping[str, Any]] = {}
    for node_id, versions in _prediction_nodes(events).items():
        ordered = sorted(versions, key=lambda item: item[0])
        sequences = [item[0] for item in ordered]
        if len(sequences) != len(set(sequences)):
            raise ValueError("EDPF_CENSUS_DUPLICATE_EVENT_SEQUENCE")
        first = ordered[0][1]
        if str(first.get("state")) != OPEN_STATE:
            raise ValueError("EDPF_CENSUS_FIRST_STATE_MUST_BE_OPEN")
        if len(ordered) > 2:
            raise ValueError("EDPF_CENSUS_MULTIPLE_RESOLUTION_EVENTS")
        if len(ordered) == 1:
            open_nodes[node_id] = first
            continue
        final = ordered[1][1]
        if str(final.get("state")) not in (RESOLVED_TRUE_STATE, RESOLVED_FALSE_STATE):
            raise ValueError("EDPF_CENSUS_INVALID_RESOLVED_STATE")
        if int(ordered[0][0]) >= int(ordered[1][0]):
            raise ValueError("EDPF_CENSUS_EVENT_ORDER_INVALID")
        if dict(final.get("payload", {})).get("prediction") != dict(first.get("payload", {})).get("prediction"):
            raise ValueError("EDPF_CENSUS_PREDICTION_MUTATED_AFTER_CUTOFF")
        resolved_nodes[node_id] = final
    return open_nodes, resolved_nodes


def _cohort_key(node: Mapping[str, Any]) -> tuple[str, str]:
    payload = dict(node.get("payload", {}))
    provenance = dict(node.get("provenance", {}))
    source_head = str(payload.get("system_source_head_sha", "")).lower().strip()
    matter_scope = str(provenance.get("matter_scope", "GLOBAL"))
    if len(source_head) != 40 or any(ch not in "0123456789abcdef" for ch in source_head):
        raise ValueError("EDPF_CENSUS_SOURCE_HEAD_INVALID")
    if not matter_scope:
        raise ValueError("EDPF_CENSUS_MATTER_SCOPE_REQUIRED")
    return source_head, matter_scope


def _prediction_fields(node: Mapping[str, Any]) -> tuple[str, str, str]:
    payload = dict(node.get("payload", {}))
    prediction = dict(payload.get("prediction", {}))
    predictor_id = str(prediction.get("predictor_id", "")).strip()
    domain = str(prediction.get("domain", "")).strip()
    fingerprint = str(payload.get("predictor_source_fingerprint", "")).strip()
    if not predictor_id or not domain or not fingerprint:
        raise ValueError("EDPF_CENSUS_PREDICTOR_METADATA_REQUIRED")
    return predictor_id, domain, fingerprint


def census_prospective_cohorts(events: Sequence[Mapping[str, Any]]) -> CohortCensusReceipt:
    """Return count-only readiness by fixed source epoch and matter scope.

    Resolved observations are also compiled through ``compile_real_shadow_pairs``
    so the census inherits the intake adapter's chronology/evidence-separation
    validation. Count readiness means only that the cohort is large/diverse
    enough to *enter* the Shadow Prediction Court; it is not a positive
    calibration result.
    """

    open_nodes, resolved_nodes = _latest_states(events)
    resolved_pairs = compile_real_shadow_pairs(events)
    if len(resolved_pairs) != len(resolved_nodes):
        raise ValueError("EDPF_CENSUS_RESOLVED_PAIR_COUNT_MISMATCH")

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for status, nodes in (("open", open_nodes), ("resolved", resolved_nodes)):
        for node in nodes.values():
            key = _cohort_key(node)
            predictor_id, domain, fingerprint = _prediction_fields(node)
            bucket = grouped.setdefault(
                key,
                {
                    "open": 0,
                    "resolved": 0,
                    "occurred": 0,
                    "not_occurred": 0,
                    "predictors": set(),
                    "fingerprints": set(),
                    "domains": set(),
                },
            )
            bucket[status] += 1
            bucket["predictors"].add(predictor_id)
            bucket["fingerprints"].add(fingerprint)
            bucket["domains"].add(domain)
            if status == "resolved":
                state = str(node.get("state"))
                if state == RESOLVED_TRUE_STATE:
                    bucket["occurred"] += 1
                elif state == RESOLVED_FALSE_STATE:
                    bucket["not_occurred"] += 1

    cohorts: list[CohortReadiness] = []
    for (source_head, matter_scope), bucket in sorted(grouped.items()):
        resolved_count = int(bucket["resolved"])
        predictor_ids = tuple(sorted(bucket["predictors"]))
        fingerprints = tuple(sorted(bucket["fingerprints"]))
        domains = tuple(sorted(bucket["domains"]))
        blockers: list[str] = []
        if resolved_count < MIN_REAL_PAIRS:
            blockers.append("MINIMUM_REAL_SHADOW_PAIR_COHORT_REQUIRED")
        if resolved_count < MIN_HOLDOUT_PAIRS:
            blockers.append("MINIMUM_CHRONOLOGICAL_HOLDOUT_REQUIRED")
        if len(predictor_ids) < MIN_PREDICTORS:
            blockers.append("MINIMUM_PREDICTOR_DIVERSITY_REQUIRED")
        if len(fingerprints) < MIN_INDEPENDENT_SOURCES:
            blockers.append("MINIMUM_INDEPENDENT_SOURCE_DIVERSITY_REQUIRED")
        cohorts.append(
            CohortReadiness(
                source_head_sha=source_head,
                matter_scope=matter_scope,
                open_count=int(bucket["open"]),
                resolved_count=resolved_count,
                occurred_count=int(bucket["occurred"]),
                not_occurred_count=int(bucket["not_occurred"]),
                predictor_ids=predictor_ids,
                predictor_count=len(predictor_ids),
                source_fingerprints=fingerprints,
                independent_source_count=len(fingerprints),
                domains=domains,
                domain_count=len(domains),
                possible_holdout_count=min(MIN_HOLDOUT_PAIRS, resolved_count),
                additional_resolutions_needed=max(0, MIN_REAL_PAIRS - resolved_count),
                additional_predictors_needed=max(0, MIN_PREDICTORS - len(predictor_ids)),
                additional_independent_sources_needed=max(0, MIN_INDEPENDENT_SOURCES - len(fingerprints)),
                count_ready_for_shadow_court=not blockers,
                blockers=tuple(blockers),
            )
        )

    body: dict[str, Any] = {
        "schema": SCHEMA,
        "cohort_count": len(cohorts),
        "total_open": len(open_nodes),
        "total_resolved": len(resolved_nodes),
        "count_ready_cohorts": sum(1 for cohort in cohorts if cohort.count_ready_for_shadow_court),
        "cohorts": tuple(cohorts),
        "empirical_calibration_evaluated": False,
        "empirical_calibration_proven": False,
        "owner_value_proven": False,
        "live_predictor_weights_changed": False,
        "live_predictor_weight_change_authorized": False,
        "dispatch_authorized": False,
        "external_effect_authorized": False,
        "stable_self_promotion_allowed": False,
    }
    body["receipt_sha256"] = _digest(body)
    return CohortCensusReceipt(**body)
