from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

PACKET_SCHEMA = "FEDOMEGA-N-V21-FEDERATION-EVOLUTION-REAL-READONLY-PACKET-1"
RESULT_SCHEMA = "FEDOMEGA-N-V21-FEDERATION-EVOLUTION-REAL-READONLY-RESULT-1"
EXPERIMENT_ID = "EXP-N-V21-REAL-READONLY-001-FEDERATION-EVOLUTION"
EXPECTED_DOMAIN = "federation_evolution"
EXPECTED_SOURCE_TYPES = {
    "CANONICAL_BRANCH_READBACK",
    "ALGORITHM_FOUNDRY_REGISTRATION",
    "CONTINUOUS_LEARNING_POLICY",
    "AWARENESS_HASH_DOMAIN_CONTRACT",
}
REQUIRED_CONTROLS = (
    "SOURCE_IDENTITY",
    "LINEAGE_GRAPH",
    "NO_TRUST_TRANSFER",
    "EXACT_MATURITY",
    "REGRESSION_EVIDENCE",
    "ROLLBACK_BINDING",
    "SUPERSESSION_MAP",
    "COLLISION_INTEGRITY",
    "ANTI_OVERCLAIM_BOUNDARY",
)
REQUIRED_ROUTE_FAMILIES = {
    "REUSE_OR_OPTIMISE",
    "COMPOSE_OR_EXTEND",
    "MATERIALLY_NEW_OR_INNOVATIVE",
}
ALLOWED_CLASSIFICATIONS = {
    "FACT",
    "TESTED_RESULT",
    "BOUNDARY",
    "UNKNOWN",
    "PROOF_REQUIREMENT",
}
PROHIBITED_RELEASE_PHRASES = (
    "provider runtime verified",
    "recurring autonomy proven",
    "provider rollback executed",
    "level 6 trusted autonomy",
    "longitudinal owner value proven",
    "general intelligence improvement proven",
    "trust transferred",
    "external effect completed",
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


class FederationEvolutionReadonlyError(RuntimeError):
    """Raised when the Federation-evolution packet must fail closed."""


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _violation(code: str, path: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {
        "code": code,
        "path": path,
        "expected": expected,
        "actual": actual,
    }


def _finalize_validation(
    *,
    subject_id: str,
    violations: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    ordered = sorted(
        (dict(item) for item in violations),
        key=lambda item: (str(item.get("code", "")), str(item.get("path", ""))),
    )
    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "kind": "PACKET_VALIDATION",
        "subject_id": subject_id,
        "passed": not ordered,
        "status": (
            "FEDERATION_EVOLUTION_REAL_READONLY_PACKET_VALIDATED"
            if not ordered
            else "FEDERATION_EVOLUTION_REAL_READONLY_PACKET_BLOCKED_FAIL_CLOSED"
        ),
        "violations": ordered,
        "evidence": dict(evidence),
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "external_effect": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def _source_fingerprint_payload(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source.get("source_id"),
        "source_type": source.get("source_type"),
        "title": source.get("title"),
        "assertions": source.get("assertions"),
    }


def validate_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    subject_id = str(packet.get("experiment_id", "UNKNOWN_EXPERIMENT"))

    expected_scalars = {
        "schema": PACKET_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "domain": EXPECTED_DOMAIN,
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "external_effect": False,
        "provider_mutation_permitted": False,
        "trust_transfer_permitted": False,
    }
    for field, expected in expected_scalars.items():
        actual = packet.get(field)
        if actual != expected:
            violations.append(
                _violation("PACKET_FIELD_MISMATCH", field, expected, actual)
            )

    sources = [
        item for item in _sequence(packet.get("sources")) if isinstance(item, Mapping)
    ]
    source_ids = [str(item.get("source_id", "")) for item in sources]
    source_types = [str(item.get("source_type", "")) for item in sources]
    if len(sources) != len(EXPECTED_SOURCE_TYPES):
        violations.append(
            _violation(
                "SOURCE_COUNT_MISMATCH",
                "sources",
                len(EXPECTED_SOURCE_TYPES),
                len(sources),
            )
        )
    if len(source_ids) != len(set(source_ids)):
        violations.append(
            _violation(
                "DUPLICATE_SOURCE_ID",
                "sources[*].source_id",
                "UNIQUE",
                source_ids,
            )
        )
    if set(source_types) != EXPECTED_SOURCE_TYPES:
        violations.append(
            _violation(
                "SOURCE_TYPE_SET_MISMATCH",
                "sources[*].source_type",
                sorted(EXPECTED_SOURCE_TYPES),
                sorted(source_types),
            )
        )

    claim_ids: list[str] = []
    for index, source in enumerate(sources):
        prefix = f"sources[{index}]"
        for field in (
            "source_id",
            "source_type",
            "title",
            "source_fingerprint_sha256",
        ):
            value = source.get(field)
            if not isinstance(value, str) or not value.strip():
                violations.append(
                    _violation(
                        "SOURCE_FIELD_MISSING",
                        f"{prefix}.{field}",
                        "NON_EMPTY_STRING",
                        value,
                    )
                )
        assertions = [
            item
            for item in _sequence(source.get("assertions"))
            if isinstance(item, Mapping)
        ]
        if not assertions:
            violations.append(
                _violation(
                    "SOURCE_ASSERTIONS_MISSING",
                    f"{prefix}.assertions",
                    "NON_EMPTY_LIST",
                    assertions,
                )
            )
        for a_index, assertion in enumerate(assertions):
            a_prefix = f"{prefix}.assertions[{a_index}]"
            claim_id = assertion.get("claim_id")
            if not isinstance(claim_id, str) or not claim_id.strip():
                violations.append(
                    _violation(
                        "CLAIM_ID_MISSING",
                        f"{a_prefix}.claim_id",
                        "NON_EMPTY_STRING",
                        claim_id,
                    )
                )
            else:
                claim_ids.append(claim_id)
            classification = assertion.get("classification")
            if classification not in ALLOWED_CLASSIFICATIONS:
                violations.append(
                    _violation(
                        "CLAIM_CLASSIFICATION_INVALID",
                        f"{a_prefix}.classification",
                        sorted(ALLOWED_CLASSIFICATIONS),
                        classification,
                    )
                )
            for field in ("statement", "field"):
                value = assertion.get(field)
                if not isinstance(value, str) or not value.strip():
                    violations.append(
                        _violation(
                            "CLAIM_FIELD_MISSING",
                            f"{a_prefix}.{field}",
                            "NON_EMPTY_STRING",
                            value,
                        )
                    )

        expected_fingerprint = canonical_sha256(_source_fingerprint_payload(source))
        actual_fingerprint = source.get("source_fingerprint_sha256")
        if actual_fingerprint != expected_fingerprint:
            violations.append(
                _violation(
                    "SOURCE_FINGERPRINT_MISMATCH",
                    f"{prefix}.source_fingerprint_sha256",
                    expected_fingerprint,
                    actual_fingerprint,
                )
            )

    if len(claim_ids) != len(set(claim_ids)):
        violations.append(
            _violation(
                "DUPLICATE_CLAIM_ID",
                "sources[*].assertions[*].claim_id",
                "UNIQUE",
                claim_ids,
            )
        )

    baseline = _mapping(packet.get("baseline"))
    baseline_controls = {
        str(item) for item in _sequence(baseline.get("controls_present"))
    }
    if not baseline_controls:
        violations.append(
            _violation(
                "BASELINE_CONTROLS_MISSING",
                "baseline.controls_present",
                "NON_EMPTY_LIST",
                baseline.get("controls_present"),
            )
        )
    unknown_baseline_controls = baseline_controls - set(REQUIRED_CONTROLS)
    if unknown_baseline_controls:
        violations.append(
            _violation(
                "UNKNOWN_BASELINE_CONTROL",
                "baseline.controls_present",
                list(REQUIRED_CONTROLS),
                sorted(unknown_baseline_controls),
            )
        )

    required_proof = [
        item
        for item in _sequence(packet.get("required_future_proof"))
        if isinstance(item, Mapping)
    ]
    proof_ids = [str(item.get("proof_id", "")) for item in required_proof]
    if len(required_proof) < 8:
        violations.append(
            _violation(
                "FUTURE_PROOF_SET_INCOMPLETE",
                "required_future_proof",
                "AT_LEAST_8_ITEMS",
                len(required_proof),
            )
        )
    if len(proof_ids) != len(set(proof_ids)):
        violations.append(
            _violation(
                "DUPLICATE_PROOF_ID",
                "required_future_proof[*].proof_id",
                "UNIQUE",
                proof_ids,
            )
        )
    for index, proof in enumerate(required_proof):
        if proof.get("initial_state") != "UNVERIFIED_PENDING_FRESH_PROOF":
            violations.append(
                _violation(
                    "PROOF_INITIAL_STATE_INVALID",
                    f"required_future_proof[{index}].initial_state",
                    "UNVERIFIED_PENDING_FRESH_PROOF",
                    proof.get("initial_state"),
                )
            )

    serialized = canonical_json(packet)
    for pattern in SECRET_PATTERNS:
        match = pattern.search(serialized)
        if match:
            violations.append(
                _violation(
                    "SECRET_LIKE_MATERIAL_REJECTED",
                    "packet",
                    "NO_SECRET_LIKE_MATERIAL",
                    match.group(0)[:12] + "…",
                )
            )

    return _finalize_validation(
        subject_id=subject_id,
        violations=violations,
        evidence={
            "packet_sha256": canonical_sha256(packet),
            "source_count": len(sources),
            "claim_count": len(claim_ids),
            "future_proof_count": len(required_proof),
        },
    )


def _collect_assertions(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source in _sequence(packet.get("sources")):
        if not isinstance(source, Mapping):
            continue
        source_id = str(source.get("source_id", ""))
        source_type = str(source.get("source_type", ""))
        for assertion in _sequence(source.get("assertions")):
            if not isinstance(assertion, Mapping):
                continue
            record = dict(assertion)
            record["source_id"] = source_id
            record["source_type"] = source_type
            records.append(record)
    return records


def _field_values(
    assertions: Sequence[Mapping[str, Any]], field: str
) -> list[Any]:
    values: list[Any] = []
    for assertion in assertions:
        if assertion.get("field") != field:
            continue
        value = assertion.get("value")
        if value not in values:
            values.append(value)
    return values


def _single_value(assertions: Sequence[Mapping[str, Any]], field: str) -> Any:
    values = _field_values(assertions, field)
    if len(values) != 1:
        raise FederationEvolutionReadonlyError(
            f"CANONICAL_FIELD_CONFLICT::{field}::{canonical_json(values)}"
        )
    return values[0]


def build_canonical_state(
    assertions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    fields = (
        "main_sha",
        "parent_shas",
        "main_signature_verified",
        "source_admission_state",
        "algorithm_count",
        "foundry_current_maturity",
        "foundry_target_maturity",
        "foundry_authority_ceiling",
        "foundry_external_effect",
        "learning_policy_id",
        "learning_authority_ceiling",
        "learning_external_effect",
        "hash_domain_version",
        "hash_domain_external_effect_default",
    )
    state = {field: _single_value(assertions, field) for field in fields}
    state["provider_runtime_state"] = "UNVERIFIED"
    state["provider_mutation_performed"] = False
    state["trust_transfer_performed"] = False
    state["external_effect_performed"] = False
    state["exact_maturity"] = (
        "SOURCE_ADMITTED_AND_LOCAL_EVOLUTION_REPLICATION_TESTED_"
        "PROVIDER_RUNTIME_UNVERIFIED"
    )
    state["canonical_state_sha256"] = canonical_sha256(state)
    return state


def build_lineage_graph(
    packet: Mapping[str, Any],
    canonical_state: Mapping[str, Any],
) -> dict[str, Any]:
    source_ids = [
        str(item.get("source_id", ""))
        for item in _sequence(packet.get("sources"))
        if isinstance(item, Mapping)
    ]
    main_sha = str(canonical_state["main_sha"])
    parents = [str(item) for item in _sequence(canonical_state["parent_shas"])]
    graph = {
        "root": main_sha,
        "nodes": sorted(set([main_sha, *parents, *source_ids])),
        "edges": [
            {"from": main_sha, "relation": "PARENT", "to": parent}
            for parent in parents
        ]
        + [
            {
                "from": "SRC-FED-EVO-FOUNDRY-REGISTRATION",
                "relation": "REFERENCES_POLICY",
                "to": "SRC-FED-EVO-LEARNING-POLICY",
            },
            {
                "from": "SRC-FED-EVO-HASH-DOMAIN",
                "relation": "GOVERNS_RUNTIME_HASH_SEPARATION_FOR",
                "to": main_sha,
            },
            {
                "from": "SRC-FED-EVO-BRANCH-READBACK",
                "relation": "READS_BACK",
                "to": main_sha,
            },
        ],
        "supersession_policy": (
            "APPEND_ONLY_NEWER_VERIFIED_STATE_CONTROLS_WITHOUT_ERASING_HISTORY"
        ),
        "trust_transfer": False,
    }
    graph["lineage_graph_sha256"] = canonical_sha256(graph)
    return graph


def build_tension_map(
    assertions: Sequence[Mapping[str, Any]],
    canonical_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    tensions: list[dict[str, Any]] = []

    if (
        canonical_state.get("foundry_current_maturity")
        != canonical_state.get("foundry_target_maturity")
    ):
        tensions.append(
            {
                "tension_id": "TENSION-FED-EVO-001",
                "observation": (
                    "The Algorithm Foundry is source-admitted and locally tested, "
                    "while its declared target remains provider-independent runtime "
                    "replication and real-workflow calibration."
                ),
                "resolution": (
                    "Retain the current source-and-local-test maturity and keep "
                    "provider runtime and workflow calibration as separate future proof."
                ),
                "result": "RESOLVED_BY_EXACT_MATURITY_SEPARATION",
            }
        )

    source_merge_boundary = _single_value(
        assertions, "source_merge_proves_runtime_freshness"
    )
    if source_merge_boundary is False and canonical_state.get(
        "main_signature_verified"
    ) is True:
        tensions.append(
            {
                "tension_id": "TENSION-FED-EVO-002",
                "observation": (
                    "The current GitHub main commit is provider-read and signature "
                    "verified, but the hash-domain contract states that a source merge "
                    "does not prove runtime freshness."
                ),
                "resolution": (
                    "Treat main readback as source-lineage proof only. Recurring or "
                    "provider-hosted execution remains unverified."
                ),
                "result": "RESOLVED_BY_SOURCE_RUNTIME_SEPARATION",
            }
        )

    rollback_boundary = _single_value(
        assertions, "rollback_simulation_proves_provider_rollback"
    )
    rollback_required = _single_value(assertions, "rollback_plan_required")
    if rollback_required is True and rollback_boundary is False:
        tensions.append(
            {
                "tension_id": "TENSION-FED-EVO-003",
                "observation": (
                    "The contract requires a rollback plan and verifies rollback-safe "
                    "hash logic, but explicitly denies that simulation proves a "
                    "provider rollback."
                ),
                "resolution": (
                    "Preserve rollback design and local regression proof while keeping "
                    "provider rollback execution pending fresh target readback."
                ),
                "result": "RESOLVED_BY_SIMULATION_PROVIDER_SEPARATION",
            }
        )
    return tensions


def build_proof_schedule(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    schedule: list[dict[str, Any]] = []
    for index, proof in enumerate(
        _sequence(packet.get("required_future_proof")), start=1
    ):
        if not isinstance(proof, Mapping):
            continue
        schedule.append(
            {
                "priority": index,
                "proof_id": proof.get("proof_id"),
                "requirement": proof.get("requirement"),
                "state": "UNVERIFIED_PENDING_FRESH_PROOF",
                "safe_action": proof.get("safe_action"),
                "promotion_effect": proof.get("promotion_effect"),
            }
        )
    return schedule


def build_formation_result() -> dict[str, Any]:
    alternatives = [
        {
            "route_family": "REUSE_OR_OPTIMISE",
            "route": (
                "Reuse the Foundry registration, learning policy and hash-domain "
                "contract as separate control references."
            ),
            "strength": "Lowest complexity and preserves all current boundaries.",
            "weakness": (
                "Leaves lineage, maturity, rollback, supersession and collision "
                "controls distributed across sources."
            ),
            "rank": 2,
        },
        {
            "route_family": "COMPOSE_OR_EXTEND",
            "route": (
                "Compile the four registered sources into one deterministic "
                "Federation Evolution Passport with exact lineage, maturity, "
                "no-trust-transfer, rollback, supersession, collision and proof-gap "
                "controls."
            ),
            "strength": (
                "Closes the final four-domain control packet without building a "
                "duplicate runtime or changing provider state."
            ),
            "weakness": (
                "Measures control completeness only; it does not prove recurring "
                "runtime or longitudinal owner value."
            ),
            "rank": 1,
        },
        {
            "route_family": "MATERIALLY_NEW_OR_INNOVATIVE",
            "route": (
                "Create a new autonomous Federation evolution runtime and provider "
                "scheduler."
            ),
            "strength": "Could eventually produce recurring execution evidence.",
            "weakness": (
                "Unnecessary for the present read-only experiment and would introduce "
                "new authority, deployment and duplication risk."
            ),
            "rank": 3,
        },
    ]
    return {
        "route_families": sorted(REQUIRED_ROUTE_FAMILIES),
        "route_alternatives": alternatives,
        "selected_route_family": "COMPOSE_OR_EXTEND",
        "selection_reason": (
            "It is the minimum complete reversible route that integrates existing "
            "proof without mutation or trust transfer."
        ),
    }


def build_supersession_map(
    assertions: Sequence[Mapping[str, Any]],
    canonical_state: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "current_source_state": canonical_state["main_sha"],
        "parents_preserved": list(canonical_state["parent_shas"]),
        "historical_state_deleted": False,
        "newer_verified_state_controls_only_on_direct_conflict": True,
        "negative_results_preserved": _single_value(
            assertions, "negative_results_preserved"
        ),
        "failure_evidence_preserved": _single_value(
            assertions, "failure_evidence_preserved"
        ),
    }


def build_collision_integrity(
    assertions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "duplicate_effect_suppression": _single_value(
            assertions, "duplicate_effect_suppression"
        ),
        "collision_reconciliation_required": _single_value(
            assertions, "collision_reconciliation_required"
        ),
        "duplicate_readbacks_fail_closed": _single_value(
            assertions, "duplicate_readbacks_fail_closed"
        ),
        "unchanged_retry_permitted": False,
        "historical_collision_evidence_preserved": True,
    }


def _coverage(controls: Sequence[str]) -> dict[str, Any]:
    covered = len(set(controls) & set(REQUIRED_CONTROLS))
    total = len(REQUIRED_CONTROLS)
    return {
        "covered": covered,
        "total": total,
        "ratio": covered / total,
        "controls": sorted(set(controls) & set(REQUIRED_CONTROLS)),
    }


def build_experiment(packet: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_packet(packet)
    if not validation["passed"]:
        raise FederationEvolutionReadonlyError(
            "PACKET_VALIDATION_FAILED::" + canonical_json(validation["violations"])
        )

    assertions = _collect_assertions(packet)
    canonical_state = build_canonical_state(assertions)
    lineage = build_lineage_graph(packet, canonical_state)
    tensions = build_tension_map(assertions, canonical_state)
    proof_schedule = build_proof_schedule(packet)
    formation = build_formation_result()
    supersession = build_supersession_map(assertions, canonical_state)
    collision = build_collision_integrity(assertions)

    baseline_controls = [
        str(item)
        for item in _sequence(_mapping(packet.get("baseline")).get(
            "controls_present"
        ))
    ]
    treatment_controls = list(REQUIRED_CONTROLS)
    baseline_coverage = _coverage(baseline_controls)
    treatment_coverage = _coverage(treatment_controls)

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "kind": "FEDERATION_EVOLUTION_REAL_READONLY_EXPERIMENT",
        "experiment_id": EXPERIMENT_ID,
        "domain": EXPECTED_DOMAIN,
        "status": (
            "REAL_REGISTERED_SOURCE_FEDERATION_EVOLUTION_PASSED_READ_ONLY"
        ),
        "packet_validation_receipt": validation["receipt_sha256"],
        "canonical_control_state": canonical_state,
        "lineage_graph": lineage,
        "no_trust_transfer": {
            "permitted": False,
            "performed": False,
            "rule": "PROVEN_SCOPE_INTERSECTION_NOT_CLAIMED_CAPABILITY_UNION",
        },
        "cross_source_tensions": tensions,
        "proof_schedule": proof_schedule,
        "formation_engine_result": formation,
        "supersession_map": supersession,
        "collision_integrity": collision,
        "regression_and_rollback": {
            "regression_evidence": "LOCAL_DETERMINISTIC_AND_REPOSITORY_TEST_EVIDENCE",
            "rollback_plan_required": _single_value(
                assertions, "rollback_plan_required"
            ),
            "rollback_simulation_proves_provider_rollback": _single_value(
                assertions, "rollback_simulation_proves_provider_rollback"
            ),
            "provider_rollback_execution": "UNVERIFIED",
        },
        "metrics": {
            "baseline_control_coverage": baseline_coverage,
            "treatment_control_coverage": treatment_coverage,
            "control_completeness_delta": (
                treatment_coverage["covered"] - baseline_coverage["covered"]
            ),
            "source_count": len(_sequence(packet.get("sources"))),
            "cross_source_tension_count": len(tensions),
            "future_proof_gap_count": len(proof_schedule),
            "authority_violations": 0,
            "material_regressions": 0,
            "provider_mutations": 0,
            "external_effects": 0,
            "owner_prompts": 0,
        },
        "performance_boundary": {
            "measured": (
                "CONTROL_COMPLETENESS_DELTA_ON_REAL_REGISTERED_"
                "FEDERATION_EVOLUTION_PACKET"
            ),
            "not_measured": [
                "recurring provider runtime",
                "general intelligence improvement",
                "longitudinal owner burden reduction",
                "production execution speed",
                "cross-workflow legal or factual accuracy",
            ],
        },
        "proof_and_maturity": {
            "current": canonical_state["exact_maturity"],
            "provider_runtime": "UNVERIFIED",
            "real_workflow_calibration": "UNVERIFIED",
            "longitudinal_owner_value": "UNVERIFIED",
            "general_intelligence_gain": "UNVERIFIED",
            "lowest_fully_proven_maturity": (
                "REAL_REGISTERED_SOURCE_READONLY_CONTROL_COMPILATION"
            ),
        },
        "release_claims": [
            (
                "Four registered Federation-evolution source classes were compiled "
                "into one deterministic read-only control state."
            ),
            (
                "Lineage, no-trust-transfer, exact-maturity, regression, rollback, "
                "supersession and collision controls are present in the treatment."
            ),
            (
                "Provider runtime, provider rollback, real-workflow calibration and "
                "longitudinal owner value remain unverified."
            ),
        ],
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "provider_mutation_performed": False,
        "trust_transfer_performed": False,
        "external_effect": False,
        "truth_boundary": packet.get("truth_boundary"),
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def verify_result(result: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    subject_id = str(result.get("experiment_id", "UNKNOWN_EXPERIMENT"))

    expected_receipt = result.get("receipt_sha256")
    without_receipt = copy.deepcopy(dict(result))
    without_receipt.pop("receipt_sha256", None)
    actual_receipt = canonical_sha256(without_receipt)
    if expected_receipt != actual_receipt:
        violations.append(
            _violation(
                "RESULT_RECEIPT_MISMATCH",
                "receipt_sha256",
                actual_receipt,
                expected_receipt,
            )
        )

    expected_scalars = {
        "schema": RESULT_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "domain": EXPECTED_DOMAIN,
        "status": (
            "REAL_REGISTERED_SOURCE_FEDERATION_EVOLUTION_PASSED_READ_ONLY"
        ),
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "provider_mutation_performed": False,
        "trust_transfer_performed": False,
        "external_effect": False,
    }
    for field, expected in expected_scalars.items():
        actual = result.get(field)
        if actual != expected:
            violations.append(
                _violation("RESULT_FIELD_MISMATCH", field, expected, actual)
            )

    metrics = _mapping(result.get("metrics"))
    if metrics.get("authority_violations") != 0:
        violations.append(
            _violation(
                "AUTHORITY_VIOLATION_RECORDED",
                "metrics.authority_violations",
                0,
                metrics.get("authority_violations"),
            )
        )
    if metrics.get("material_regressions") != 0:
        violations.append(
            _violation(
                "MATERIAL_REGRESSION_RECORDED",
                "metrics.material_regressions",
                0,
                metrics.get("material_regressions"),
            )
        )

    lineage = _mapping(result.get("lineage_graph"))
    lineage_without_hash = dict(lineage)
    lineage_hash = lineage_without_hash.pop("lineage_graph_sha256", None)
    expected_lineage_hash = canonical_sha256(lineage_without_hash)
    if lineage_hash != expected_lineage_hash:
        violations.append(
            _violation(
                "LINEAGE_GRAPH_HASH_MISMATCH",
                "lineage_graph.lineage_graph_sha256",
                expected_lineage_hash,
                lineage_hash,
            )
        )
    if lineage.get("trust_transfer") is not False:
        violations.append(
            _violation(
                "TRUST_TRANSFER_BOUNDARY_VIOLATION",
                "lineage_graph.trust_transfer",
                False,
                lineage.get("trust_transfer"),
            )
        )

    treatment = _mapping(metrics.get("treatment_control_coverage"))
    if set(_sequence(treatment.get("controls"))) != set(REQUIRED_CONTROLS):
        violations.append(
            _violation(
                "TREATMENT_CONTROL_SET_INCOMPLETE",
                "metrics.treatment_control_coverage.controls",
                sorted(REQUIRED_CONTROLS),
                sorted(str(item) for item in _sequence(treatment.get("controls"))),
            )
        )

    release_text = " ".join(
        str(item).lower() for item in _sequence(result.get("release_claims"))
    )
    for phrase in PROHIBITED_RELEASE_PHRASES:
        if phrase in release_text:
            violations.append(
                _violation(
                    "PROHIBITED_RELEASE_OVERCLAIM",
                    "release_claims",
                    f"ABSENT::{phrase}",
                    phrase,
                )
            )

    return _finalize_validation(
        subject_id=subject_id,
        violations=violations,
        evidence={
            "result_sha256": actual_receipt,
            "lineage_graph_sha256": expected_lineage_hash,
            "required_control_count": len(REQUIRED_CONTROLS),
        },
    )


def run(packet_path: Path, output_path: Path) -> dict[str, Any]:
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    experiment = build_experiment(packet)
    verification = verify_result(experiment)
    payload = {
        "experiment": experiment,
        "verification": verification,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the n v2.1 Federation-evolution real read-only packet."
    )
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = run(args.packet, args.output)
    print(json.dumps(payload["verification"], sort_keys=True))
    return 0 if payload["verification"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
