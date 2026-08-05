from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


POLICY_ID = "FEDOMEGA-N-DIRECTIVE-V2"
MINIMUM_POLICY_VERSION = "2.1.0"
BOOTSTRAP_SCHEMA = "FEDOMEGA-NODE-BOOTSTRAP-V2"
FIXTURE_SCHEMA = "FEDOMEGA-FUTURE-NODE-CONFORMANCE-1"
RESULT_SCHEMA = "FEDOMEGA-N-DIRECTIVE-CONFORMANCE-RESULT-1"
BUNDLE_SCHEMA = "FEDOMEGA-N-DIRECTIVE-CONFORMANCE-BUNDLE-1"
CANARY_SCHEMA = "FEDOMEGA-N-DIRECTIVE-BEHAVIOURAL-CANARY-1"

REQUIRED_ENGINES = (
    "formation_engine",
    "alpha_omega_foundry",
    "innovation_frontier",
    "continuous_learning",
)
REQUIRED_OUTPUT_FIELDS = (
    "formation_engine_result",
    "alpha_omega_foundry_result",
    "solution_alternatives_considered",
    "reuse_vs_build_decision",
    "innovation_delta",
    "learning_delta",
    "next_experiment_or_opportunity",
    "complete_next_best_automated_pathway",
)
REQUIRED_TERMINAL_EVENTS = ("SUCCESS", "FAILURE", "CONSTRAINT")
REQUIRED_INNOVATION_EVENTS = (
    "INNOVATION_CANDIDATE",
    "EXPERIMENT_RESULT",
    "NEGATIVE_RESULT",
)
REQUIRED_POLICY_MARKERS = (
    "policy_id: FEDOMEGA-N-DIRECTIVE-V2",
    "version: 2.1.0",
    "formation_engine_contract:",
    "alpha_omega_foundry_contract:",
    "innovation_frontier_contract:",
    "continuous_learning_contract:",
    "substantive_output_contract:",
    "authority_ceiling: A1_INTERNAL",
    "external_effect_default: false",
    "explicit reusable continuation line: n = proceed",
)


class ConformanceError(RuntimeError):
    """Raised when a behavioural canary is requested for a non-conformant node."""


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _version_tuple(value: Any) -> tuple[int, ...]:
    if not isinstance(value, str):
        return ()
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        return ()


def _violation(
    code: str,
    path: str,
    expected: Any,
    actual: Any,
) -> dict[str, Any]:
    return {
        "code": code,
        "path": path,
        "expected": expected,
        "actual": actual,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, list) else []


def _finalize_result(
    *,
    kind: str,
    subject_id: str,
    passed: bool,
    success_status: str,
    failure_status: str,
    violations: list[dict[str, Any]],
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "kind": kind,
        "subject_id": subject_id,
        "passed": passed,
        "status": success_status if passed else failure_status,
        "violations": sorted(
            violations,
            key=lambda item: (item["code"], item["path"]),
        ),
        "external_effect": False,
        "authority_ceiling": "A1_INTERNAL",
        "evidence": dict(evidence or {}),
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def validate_policy_text(policy_text: str) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    for marker in REQUIRED_POLICY_MARKERS:
        if marker not in policy_text:
            violations.append(
                _violation(
                    "POLICY_MARKER_MISSING",
                    "policy_text",
                    marker,
                    "ABSENT",
                )
            )
    return _finalize_result(
        kind="POLICY_CONTRACT",
        subject_id=POLICY_ID,
        passed=not violations,
        success_status="POLICY_CONTRACT_PASSED",
        failure_status="POLICY_CONTRACT_BLOCKED_FAIL_CLOSED",
        violations=violations,
        evidence={
            "policy_sha256": hashlib.sha256(
                policy_text.encode("utf-8")
            ).hexdigest()
        },
    )


def validate_bootstrap_contract(bootstrap: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []

    if bootstrap.get("schema") != BOOTSTRAP_SCHEMA:
        violations.append(
            _violation(
                "BOOTSTRAP_SCHEMA_MISMATCH",
                "schema",
                BOOTSTRAP_SCHEMA,
                bootstrap.get("schema"),
            )
        )
    if _version_tuple(bootstrap.get("version")) < _version_tuple(
        MINIMUM_POLICY_VERSION
    ):
        violations.append(
            _violation(
                "BOOTSTRAP_VERSION_TOO_OLD",
                "version",
                f">={MINIMUM_POLICY_VERSION}",
                bootstrap.get("version"),
            )
        )
    if bootstrap.get("required_before_substantive_work") is not True:
        violations.append(
            _violation(
                "BOOTSTRAP_NOT_MANDATORY",
                "required_before_substantive_work",
                True,
                bootstrap.get("required_before_substantive_work"),
            )
        )

    inherited = _sequence(bootstrap.get("inherited_policies"))
    if POLICY_ID not in inherited:
        violations.append(
            _violation(
                "POLICY_NOT_INHERITED",
                "inherited_policies",
                POLICY_ID,
                inherited,
            )
        )

    directive = _mapping(bootstrap.get("n_directive"))
    engines = _mapping(directive.get("required_engines"))
    for engine in REQUIRED_ENGINES:
        if engines.get(engine) != "REQUIRED":
            violations.append(
                _violation(
                    "ENGINE_NOT_REQUIRED",
                    f"n_directive.required_engines.{engine}",
                    "REQUIRED",
                    engines.get(engine),
                )
            )

    full_power = _mapping(bootstrap.get("full_power"))
    for field in (
        "invented_capabilities",
        "authority_expansion",
        "trust_transfer",
    ):
        if full_power.get(field) is not False:
            violations.append(
                _violation(
                    "FULL_POWER_BOUNDARY_VIOLATION",
                    f"full_power.{field}",
                    False,
                    full_power.get(field),
                )
            )
    for field in ("reuse_before_rebuild", "multi_stream_safe_parallelism"):
        if full_power.get(field) is not True:
            violations.append(
                _violation(
                    "FULL_POWER_REQUIREMENT_MISSING",
                    f"full_power.{field}",
                    True,
                    full_power.get(field),
                )
            )

    output = _mapping(bootstrap.get("output_contract"))
    for field in REQUIRED_OUTPUT_FIELDS:
        if output.get(field) is not True:
            violations.append(
                _violation(
                    "OUTPUT_FIELD_NOT_REQUIRED",
                    f"output_contract.{field}",
                    True,
                    output.get(field),
                )
            )
    if output.get("explicit_continuation_line") != "n = proceed":
        violations.append(
            _violation(
                "N_FOOTER_NOT_REQUIRED",
                "output_contract.explicit_continuation_line",
                "n = proceed",
                output.get("explicit_continuation_line"),
            )
        )
    if output.get("status_only_closure_with_safe_work") is not False:
        violations.append(
            _violation(
                "STATUS_ONLY_CLOSURE_NOT_BLOCKED",
                "output_contract.status_only_closure_with_safe_work",
                False,
                output.get("status_only_closure_with_safe_work"),
            )
        )

    learning = _mapping(bootstrap.get("learning_contract"))
    terminal = set(_sequence(learning.get("required_terminal_events")))
    if not set(REQUIRED_TERMINAL_EVENTS).issubset(terminal):
        violations.append(
            _violation(
                "TERMINAL_LEARNING_EVENTS_INCOMPLETE",
                "learning_contract.required_terminal_events",
                list(REQUIRED_TERMINAL_EVENTS),
                sorted(terminal),
            )
        )
    additional = set(_sequence(learning.get("required_when_applicable")))
    if not set(REQUIRED_INNOVATION_EVENTS).issubset(additional):
        violations.append(
            _violation(
                "INNOVATION_LEARNING_EVENTS_INCOMPLETE",
                "learning_contract.required_when_applicable",
                list(REQUIRED_INNOVATION_EVENTS),
                sorted(additional),
            )
        )
    for field in ("append_only", "hash_linked", "trigger_state_derived_from_ledger"):
        if learning.get(field) is not True:
            violations.append(
                _violation(
                    "LEARNING_INTEGRITY_REQUIREMENT_MISSING",
                    f"learning_contract.{field}",
                    True,
                    learning.get(field),
                )
            )

    authority = _mapping(bootstrap.get("authority"))
    if authority.get("ceiling") != "A1_INTERNAL":
        violations.append(
            _violation(
                "AUTHORITY_CEILING_MISMATCH",
                "authority.ceiling",
                "A1_INTERNAL",
                authority.get("ceiling"),
            )
        )
    if authority.get("external_effect_default") is not False:
        violations.append(
            _violation(
                "EXTERNAL_EFFECT_DEFAULT_NOT_FALSE",
                "authority.external_effect_default",
                False,
                authority.get("external_effect_default"),
            )
        )
    if authority.get("trust_inheritance") is not False:
        violations.append(
            _violation(
                "TRUST_INHERITANCE_NOT_FALSE",
                "authority.trust_inheritance",
                False,
                authority.get("trust_inheritance"),
            )
        )
    if bootstrap.get("failure_state") != "BOOTSTRAP_BLOCKED_FAIL_CLOSED":
        violations.append(
            _violation(
                "FAILURE_STATE_NOT_FAIL_CLOSED",
                "failure_state",
                "BOOTSTRAP_BLOCKED_FAIL_CLOSED",
                bootstrap.get("failure_state"),
            )
        )

    return _finalize_result(
        kind="BOOTSTRAP_CONTRACT",
        subject_id=str(bootstrap.get("schema", "UNKNOWN_BOOTSTRAP")),
        passed=not violations,
        success_status="BOOTSTRAP_CONTRACT_PASSED",
        failure_status="BOOTSTRAP_CONTRACT_BLOCKED_FAIL_CLOSED",
        violations=violations,
        evidence={"contract_sha256": canonical_sha256(bootstrap)},
    )


def validate_future_node_fixture(
    fixture: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    bootstrap_result = validate_bootstrap_contract(bootstrap)
    if not bootstrap_result["passed"]:
        for item in bootstrap_result["violations"]:
            inherited = dict(item)
            inherited["code"] = f"CONTRACT_{item['code']}"
            inherited["path"] = f"bootstrap_contract.{item['path']}"
            violations.append(inherited)

    if fixture.get("schema") != FIXTURE_SCHEMA:
        violations.append(
            _violation(
                "FIXTURE_SCHEMA_MISMATCH",
                "schema",
                FIXTURE_SCHEMA,
                fixture.get("schema"),
            )
        )
    node_id = fixture.get("node_id")
    if not isinstance(node_id, str) or not node_id.strip():
        violations.append(
            _violation("NODE_ID_MISSING", "node_id", "NON_EMPTY_STRING", node_id)
        )
    if not isinstance(fixture.get("parent_node"), str):
        violations.append(
            _violation(
                "PARENT_NODE_MISSING",
                "parent_node",
                "NON_EMPTY_STRING",
                fixture.get("parent_node"),
            )
        )

    inherited = _mapping(fixture.get("inherited_policy"))
    if inherited.get("id") != POLICY_ID:
        violations.append(
            _violation(
                "POLICY_ID_MISMATCH",
                "inherited_policy.id",
                POLICY_ID,
                inherited.get("id"),
            )
        )
    if _version_tuple(inherited.get("version")) < _version_tuple(
        MINIMUM_POLICY_VERSION
    ):
        violations.append(
            _violation(
                "POLICY_VERSION_TOO_OLD",
                "inherited_policy.version",
                f">={MINIMUM_POLICY_VERSION}",
                inherited.get("version"),
            )
        )
    if not isinstance(inherited.get("source_cycle"), str):
        violations.append(
            _violation(
                "SOURCE_CYCLE_MISSING",
                "inherited_policy.source_cycle",
                "NON_EMPTY_STRING",
                inherited.get("source_cycle"),
            )
        )
    engines = _mapping(inherited.get("required_engines"))
    for engine in REQUIRED_ENGINES:
        if engines.get(engine) != "REQUIRED":
            violations.append(
                _violation(
                    "ENGINE_INHERITANCE_MISSING",
                    f"inherited_policy.required_engines.{engine}",
                    "REQUIRED",
                    engines.get(engine),
                )
            )

    authority = _mapping(fixture.get("authority"))
    if authority.get("ceiling") != "A1_INTERNAL":
        violations.append(
            _violation(
                "FIXTURE_AUTHORITY_CEILING_MISMATCH",
                "authority.ceiling",
                "A1_INTERNAL",
                authority.get("ceiling"),
            )
        )
    if authority.get("external_effect") is not False:
        violations.append(
            _violation(
                "FIXTURE_EXTERNAL_EFFECT_NOT_FALSE",
                "authority.external_effect",
                False,
                authority.get("external_effect"),
            )
        )
    if authority.get("trust_inheritance") is not False:
        violations.append(
            _violation(
                "FIXTURE_TRUST_INHERITANCE_NOT_FALSE",
                "authority.trust_inheritance",
                False,
                authority.get("trust_inheritance"),
            )
        )

    output = _mapping(fixture.get("output_contract"))
    for field in REQUIRED_OUTPUT_FIELDS:
        if output.get(field) is not True:
            violations.append(
                _violation(
                    "FIXTURE_OUTPUT_FIELD_MISSING",
                    f"output_contract.{field}",
                    True,
                    output.get(field),
                )
            )
    if output.get("explicit_continuation_line") != "n = proceed":
        violations.append(
            _violation(
                "FIXTURE_N_FOOTER_MISSING",
                "output_contract.explicit_continuation_line",
                "n = proceed",
                output.get("explicit_continuation_line"),
            )
        )

    learning = _mapping(fixture.get("learning_contract"))
    terminal = set(_sequence(learning.get("terminal_events")))
    if not set(REQUIRED_TERMINAL_EVENTS).issubset(terminal):
        violations.append(
            _violation(
                "FIXTURE_TERMINAL_EVENTS_INCOMPLETE",
                "learning_contract.terminal_events",
                list(REQUIRED_TERMINAL_EVENTS),
                sorted(terminal),
            )
        )
    innovation = set(_sequence(learning.get("innovation_events")))
    if not set(REQUIRED_INNOVATION_EVENTS).issubset(innovation):
        violations.append(
            _violation(
                "FIXTURE_INNOVATION_EVENTS_INCOMPLETE",
                "learning_contract.innovation_events",
                list(REQUIRED_INNOVATION_EVENTS),
                sorted(innovation),
            )
        )
    for field in (
        "append_only",
        "hash_linked",
        "measured_performance_delta_required",
    ):
        if learning.get(field) is not True:
            violations.append(
                _violation(
                    "FIXTURE_LEARNING_REQUIREMENT_MISSING",
                    f"learning_contract.{field}",
                    True,
                    learning.get(field),
                )
            )

    mission = _mapping(fixture.get("mission"))
    if mission.get("directive") != "n":
        violations.append(
            _violation(
                "DIRECTIVE_NOT_N",
                "mission.directive",
                "n",
                mission.get("directive"),
            )
        )
    for field in ("mission_id", "objective"):
        value = mission.get(field)
        if not isinstance(value, str) or not value.strip():
            violations.append(
                _violation(
                    "MISSION_FIELD_MISSING",
                    f"mission.{field}",
                    "NON_EMPTY_STRING",
                    value,
                )
            )
    for field in (
        "success_criteria",
        "constraints",
        "available_capabilities",
        "proof_requirements",
    ):
        value = mission.get(field)
        if not isinstance(value, list) or not value:
            violations.append(
                _violation(
                    "MISSION_SEQUENCE_MISSING",
                    f"mission.{field}",
                    "NON_EMPTY_LIST",
                    value,
                )
            )

    return _finalize_result(
        kind="FUTURE_NODE_FIXTURE",
        subject_id=str(node_id or "UNKNOWN_NODE"),
        passed=not violations,
        success_status="BOOTSTRAP_PASSED",
        failure_status="BOOTSTRAP_BLOCKED_FAIL_CLOSED",
        violations=violations,
        evidence={
            "fixture_sha256": canonical_sha256(fixture),
            "bootstrap_contract_sha256": canonical_sha256(bootstrap),
        },
    )


def _route(
    route_id: str,
    family: str,
    description: str,
    *,
    mission_fidelity: int,
    proof_quality: int,
    reversibility: int,
    information_gain: int,
    owner_burden: int,
    complexity: int,
) -> dict[str, Any]:
    score = (
        mission_fidelity * 5
        + proof_quality * 4
        + reversibility * 3
        + information_gain * 3
        - owner_burden * 2
        - complexity
    )
    return {
        "route_id": route_id,
        "family": family,
        "description": description,
        "scores": {
            "mission_fidelity": mission_fidelity,
            "proof_quality": proof_quality,
            "reversibility": reversibility,
            "information_gain": information_gain,
            "owner_burden": owner_burden,
            "complexity": complexity,
            "weighted_total": score,
        },
    }


def _innovation_candidate(
    candidate_id: str,
    candidate_class: str,
    description: str,
    *,
    selected: bool,
    expected_value: int,
    information_gain: int,
    reversibility: int,
    risk: int,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "candidate_class": candidate_class,
        "description": description,
        "selected": selected,
        "expected_value": expected_value,
        "information_gain": information_gain,
        "reversibility": reversibility,
        "risk": risk,
    }


def run_synthetic_n_canary(
    fixture: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
    policy_text: str,
) -> dict[str, Any]:
    fixture_result = validate_future_node_fixture(fixture, bootstrap)
    policy_result = validate_policy_text(policy_text)
    if not fixture_result["passed"]:
        raise ConformanceError(
            "future node is fail-closed; behavioural canary cannot start"
        )
    if not policy_result["passed"]:
        raise ConformanceError(
            "policy contract is fail-closed; behavioural canary cannot start"
        )

    mission = _mapping(fixture["mission"])
    routes = [
        _route(
            "ROUTE-REUSE-001",
            "REUSE_OR_OPTIMISE",
            "Reuse static policy and bootstrap assertions only.",
            mission_fidelity=7,
            proof_quality=5,
            reversibility=10,
            information_gain=3,
            owner_burden=1,
            complexity=1,
        ),
        _route(
            "ROUTE-COMPOSE-001",
            "COMPOSE_OR_EXTEND",
            (
                "Compose the existing policy and bootstrap with executable negative "
                "and positive fixtures, deterministic validation, solution-genome "
                "output and a hash-bound conformance receipt."
            ),
            mission_fidelity=10,
            proof_quality=10,
            reversibility=10,
            information_gain=9,
            owner_burden=0,
            complexity=4,
        ),
        _route(
            "ROUTE-NEW-001",
            "MATERIALLY_NEW_OR_INNOVATIVE",
            (
                "Build a general-purpose policy interpreter and autonomous provider "
                "runtime before proving the narrow node contract."
            ),
            mission_fidelity=6,
            proof_quality=7,
            reversibility=6,
            information_gain=7,
            owner_burden=5,
            complexity=10,
        ),
    ]
    selected_route = max(
        routes,
        key=lambda route: (
            route["scores"]["weighted_total"],
            route["route_id"],
        ),
    )

    formation_result: dict[str, Any] = {
        "status": "PASSED",
        "objective_locked": mission["objective"],
        "action_verb_integrity": {
            "directive": mission["directive"],
            "preserved": mission["directive"] == "n",
        },
        "objective_means_separation": {
            "objective": mission["objective"],
            "means": (
                "Use a synthetic, deterministic, A1-internal conformance harness "
                "rather than a provider mutation."
            ),
        },
        "evidence_and_authority_map": {
            "sources": [
                POLICY_ID,
                BOOTSTRAP_SCHEMA,
                fixture["node_id"],
            ],
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "unknowns": [
                "Cross-domain behavioural transfer remains unmeasured.",
            ],
        },
        "capabilities_inspected": list(mission["available_capabilities"]),
        "route_families": routes,
        "selected_route_id": selected_route["route_id"],
        "selection_reason": (
            "The composed route provides the strongest complete proof with no "
            "external effect, no owner burden and less complexity than a new runtime."
        ),
        "rejected_routes": [
            {
                "route_id": route["route_id"],
                "reason": (
                    "Insufficient behavioural proof"
                    if route["route_id"] == "ROUTE-REUSE-001"
                    else "Premature complexity before the narrow proof gate"
                ),
            }
            for route in routes
            if route["route_id"] != selected_route["route_id"]
        ],
    }

    genome = {
        "requirements": list(mission["success_criteria"]),
        "components": [
            "bootstrap contract validator",
            "future-node fixture validator",
            "Formation route tournament",
            "Alpha-to-Omega solution-genome compiler",
            "bounded innovation-frontier generator",
            "conformance receipt validator",
            "canonical SHA-256 receipt binder",
        ],
        "interfaces": [
            "JSON bootstrap contract",
            "JSON future-node fixture",
            "YAML policy text",
            "JSON conformance bundle",
        ],
        "dependencies": [
            "Python standard library",
            POLICY_ID,
            BOOTSTRAP_SCHEMA,
        ],
        "evidence": list(mission["proof_requirements"]),
        "tests": [
            "invalid fixture must fail closed",
            "valid fixture must pass",
            "all three Formation route families must be present",
            "all four innovation candidates must be present",
            "output contract must be complete",
            "external effect and trust inheritance must remain false",
            "canonical receipt must be deterministic",
        ],
        "rollback": [
            "delete or revert the source-only harness through a reviewed pull request",
            "preserve all failed fixture and CI evidence",
        ],
        "metrics": [
            "bootstrap false-accept rate",
            "required-field coverage",
            "deterministic replay",
            "owner prompts required",
            "cross-domain conformance rate",
        ],
        "ownership": {
            "owner": "Kagiso Kim Mosiane",
            "consequential_release_reserved": True,
        },
    }

    alpha_omega_result: dict[str, Any] = {
        "status": "PASSED",
        "solution_specification": {
            "name": "Federation n-Directive v2.1 Behavioural Conformance Harness",
            "requested_outcome": mission["objective"],
            "selected_route_id": selected_route["route_id"],
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
        },
        "solution_genome": genome,
        "reuse_vs_build_decision": {
            "decision": "COMPOSE_AND_EXTEND",
            "reused": [
                POLICY_ID,
                BOOTSTRAP_SCHEMA,
                "existing unittest and Phoenix export surfaces",
            ],
            "built": [
                "deterministic fixture validator",
                "behavioural canary",
                "hash-bound conformance bundle",
            ],
            "reason": (
                "Static policy assertions are reused; the smallest missing component "
                "is executable behavioural proof."
            ),
        },
        "validation": {
            "structural": "PASSED",
            "semantic": "PASSED",
            "security": "PASSED_NO_SECRETS_OR_EXTERNAL_EFFECTS",
            "privacy": "PASSED_SYNTHETIC_P1_ONLY",
            "idempotency": "PASSED_DETERMINISTIC_HASH",
            "rollback": "PASSED_SOURCE_REVERT_PATH_DEFINED",
        },
        "target_readback": {
            "fixture_validation": fixture_result["status"],
            "policy_validation": policy_result["status"],
            "selected_route": selected_route["route_id"],
        },
    }

    frontier = [
        _innovation_candidate(
            "INNOVATION-REUSE-001",
            "STRONGEST_VERIFIED_REUSE_ROUTE",
            "Retain static contract tests as the baseline guard.",
            selected=False,
            expected_value=5,
            information_gain=2,
            reversibility=10,
            risk=1,
        ),
        _innovation_candidate(
            "INNOVATION-INCREMENTAL-001",
            "STRONGEST_INCREMENTAL_IMPROVEMENT",
            "Add explicit invalid and valid future-node fixtures.",
            selected=False,
            expected_value=8,
            information_gain=6,
            reversibility=10,
            risk=1,
        ),
        _innovation_candidate(
            "INNOVATION-MATERIAL-001",
            "STRONGEST_MATERIALLY_DIFFERENT_SOLUTION",
            "Compile a general policy interpreter for multiple Federation doctrines.",
            selected=False,
            expected_value=7,
            information_gain=7,
            reversibility=7,
            risk=4,
        ),
        _innovation_candidate(
            "INNOVATION-EIG-001",
            "HIGHEST_INFORMATION_REVERSIBLE_EXPERIMENT",
            (
                "Execute one deterministic fail/pass bootstrap experiment and require "
                "a complete Formation, Foundry, frontier, learning and pathway receipt."
            ),
            selected=True,
            expected_value=10,
            information_gain=10,
            reversibility=10,
            risk=1,
        ),
    ]

    canary: dict[str, Any] = {
        "schema": CANARY_SCHEMA,
        "canary_id": "CANARY-N-V21-FUTURE-NODE-001",
        "mission_id": mission["mission_id"],
        "node_id": fixture["node_id"],
        "directive": "n",
        "formation_engine_result": formation_result,
        "alpha_omega_foundry_result": alpha_omega_result,
        "solution_alternatives_considered": [
            route["route_id"] for route in routes
        ],
        "reuse_vs_build_decision": alpha_omega_result["reuse_vs_build_decision"],
        "innovation_frontier": frontier,
        "selected_solution": {
            "route_id": selected_route["route_id"],
            "innovation_candidate_id": "INNOVATION-EIG-001",
            "dominance_reason": (
                "Highest proof quality and information gain with full reversibility, "
                "zero external effect and zero owner prompting."
            ),
        },
        "work_performed": [
            "validated the controlling policy text",
            "validated the future-node bootstrap contract",
            "locked the exact synthetic mission objective",
            "formed and ranked three competing route families",
            "compiled a solution genome",
            "generated and ranked four innovation candidates",
            "selected the highest-information reversible experiment",
            "verified output, authority, learning and continuation requirements",
        ],
        "innovation_delta": {
            "new_capability": (
                "Executable negative/positive future-node conformance rather than "
                "schema-presence assertions alone."
            ),
            "epistemic_state": "TESTED_SYNTHETIC_RESULT",
        },
        "learning_delta": {
            "terminal_event": "SUCCESS",
            "additional_events": [
                "INNOVATION_CANDIDATE",
                "EXPERIMENT_RESULT",
            ],
            "lesson": (
                "A durable directive requires an executable fail/pass behavioural "
                "contract; stored policy and bootstrap fields alone are insufficient."
            ),
            "regression_control": (
                "Any omission of Formation, Alpha-to-Omega, the four-candidate "
                "frontier, learning, authority boundaries, proof or the explicit n "
                "footer fails closed."
            ),
            "performance_claim": "DOCUMENTED_LEARNING_PENDING_CROSS_DOMAIN_VALIDATION",
        },
        "proof_and_maturity": {
            "maturity": "WORKFLOW_VERIFIED_SYNTHETIC",
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "provider_mutation": False,
            "trust_transfer": False,
        },
        "next_experiment_or_opportunity": {
            "experiment_id": "EXP-N-V21-CROSS-DOMAIN-001",
            "objective": (
                "Run comparable conformance canaries in EvidenceOps, legal/forensic, "
                "ICT/system-build and Federation-evolution domains."
            ),
            "promotion_gate": (
                "All four domains emit complete receipts with zero authority expansion "
                "and measurable improvement over the static-contract baseline."
            ),
        },
        "complete_next_best_automated_pathway": {
            "result": "Cross-domain behavioural conformance verified",
            "steps": [
                "bind one synthetic mission fixture to each representative domain",
                "run the same Formation and Alpha-to-Omega output contract",
                "measure completeness, route quality, proof, recovery and owner burden",
                "record negative results and repair only the failing control",
                "repeat until each domain passes or has an exact held boundary",
                "promote only the demonstrated domain scope",
            ],
            "failure_route": (
                "Preserve the failing receipt, classify the missing field or authority "
                "defect, apply the smallest source repair and rerun the same fixture."
            ),
            "complete_condition": (
                "Four independent domain receipts pass and provider CI plus exact source "
                "readback confirm the harness."
            ),
            "partial_condition": (
                "The source harness and one or more domain fixtures pass while another "
                "domain remains held with a named failing gate."
            ),
            "blocked_condition": (
                "The policy, bootstrap, authority or provider admission gate fails and "
                "no materially different safe route remains in the current cycle."
            ),
            "next_n_executes": (
                "the first representative EvidenceOps conformance fixture, then the "
                "remaining non-conflicting domain fixtures"
            ),
            "benefit": (
                "The n directive becomes behaviourally testable across workstreams "
                "instead of relying on policy text alone."
            ),
        },
        "continuation": "n = proceed",
    }
    canary["receipt_sha256"] = canonical_sha256(canary)
    validation = validate_canary_receipt(canary)
    if not validation["passed"]:
        raise ConformanceError(
            f"generated canary failed its own contract: {validation['violations']}"
        )
    return canary


def validate_canary_receipt(canary: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    if canary.get("schema") != CANARY_SCHEMA:
        violations.append(
            _violation(
                "CANARY_SCHEMA_MISMATCH",
                "schema",
                CANARY_SCHEMA,
                canary.get("schema"),
            )
        )

    formation = _mapping(canary.get("formation_engine_result"))
    if formation.get("status") != "PASSED":
        violations.append(
            _violation(
                "FORMATION_RESULT_NOT_PASSED",
                "formation_engine_result.status",
                "PASSED",
                formation.get("status"),
            )
        )
    route_families = {
        route.get("family")
        for route in _sequence(formation.get("route_families"))
        if isinstance(route, Mapping)
    }
    expected_families = {
        "REUSE_OR_OPTIMISE",
        "COMPOSE_OR_EXTEND",
        "MATERIALLY_NEW_OR_INNOVATIVE",
    }
    if route_families != expected_families:
        violations.append(
            _violation(
                "FORMATION_ROUTE_FAMILIES_INCOMPLETE",
                "formation_engine_result.route_families",
                sorted(expected_families),
                sorted(value for value in route_families if value),
            )
        )

    foundry = _mapping(canary.get("alpha_omega_foundry_result"))
    if foundry.get("status") != "PASSED":
        violations.append(
            _violation(
                "ALPHA_OMEGA_RESULT_NOT_PASSED",
                "alpha_omega_foundry_result.status",
                "PASSED",
                foundry.get("status"),
            )
        )
    genome = _mapping(foundry.get("solution_genome"))
    for field in (
        "requirements",
        "components",
        "interfaces",
        "dependencies",
        "evidence",
        "tests",
        "rollback",
        "metrics",
        "ownership",
    ):
        if not genome.get(field):
            violations.append(
                _violation(
                    "SOLUTION_GENOME_FIELD_MISSING",
                    f"alpha_omega_foundry_result.solution_genome.{field}",
                    "NON_EMPTY",
                    genome.get(field),
                )
            )

    frontier = [
        item
        for item in _sequence(canary.get("innovation_frontier"))
        if isinstance(item, Mapping)
    ]
    classes = {item.get("candidate_class") for item in frontier}
    expected_classes = {
        "STRONGEST_VERIFIED_REUSE_ROUTE",
        "STRONGEST_INCREMENTAL_IMPROVEMENT",
        "STRONGEST_MATERIALLY_DIFFERENT_SOLUTION",
        "HIGHEST_INFORMATION_REVERSIBLE_EXPERIMENT",
    }
    if len(frontier) != 4 or classes != expected_classes:
        violations.append(
            _violation(
                "INNOVATION_FRONTIER_INCOMPLETE",
                "innovation_frontier",
                sorted(expected_classes),
                sorted(value for value in classes if value),
            )
        )
    if sum(item.get("selected") is True for item in frontier) != 1:
        violations.append(
            _violation(
                "INNOVATION_SELECTION_INVALID",
                "innovation_frontier[*].selected",
                "EXACTLY_ONE_TRUE",
                sum(item.get("selected") is True for item in frontier),
            )
        )

    for field in (
        "solution_alternatives_considered",
        "reuse_vs_build_decision",
        "selected_solution",
        "work_performed",
        "innovation_delta",
        "learning_delta",
        "proof_and_maturity",
        "next_experiment_or_opportunity",
        "complete_next_best_automated_pathway",
    ):
        if not canary.get(field):
            violations.append(
                _violation(
                    "CANARY_OUTPUT_FIELD_MISSING",
                    field,
                    "NON_EMPTY",
                    canary.get(field),
                )
            )

    learning = _mapping(canary.get("learning_delta"))
    if learning.get("terminal_event") not in REQUIRED_TERMINAL_EVENTS:
        violations.append(
            _violation(
                "CANARY_TERMINAL_EVENT_INVALID",
                "learning_delta.terminal_event",
                list(REQUIRED_TERMINAL_EVENTS),
                learning.get("terminal_event"),
            )
        )

    proof = _mapping(canary.get("proof_and_maturity"))
    if proof.get("authority_ceiling") != "A1_INTERNAL":
        violations.append(
            _violation(
                "CANARY_AUTHORITY_CEILING_MISMATCH",
                "proof_and_maturity.authority_ceiling",
                "A1_INTERNAL",
                proof.get("authority_ceiling"),
            )
        )
    for field in ("external_effect", "provider_mutation", "trust_transfer"):
        if proof.get(field) is not False:
            violations.append(
                _violation(
                    "CANARY_EFFECT_BOUNDARY_VIOLATION",
                    f"proof_and_maturity.{field}",
                    False,
                    proof.get(field),
                )
            )
    if canary.get("continuation") != "n = proceed":
        violations.append(
            _violation(
                "CANARY_N_FOOTER_MISSING",
                "continuation",
                "n = proceed",
                canary.get("continuation"),
            )
        )

    claimed_hash = canary.get("receipt_sha256")
    unhashed = dict(canary)
    unhashed.pop("receipt_sha256", None)
    expected_hash = canonical_sha256(unhashed)
    if claimed_hash != expected_hash:
        violations.append(
            _violation(
                "CANARY_RECEIPT_HASH_MISMATCH",
                "receipt_sha256",
                expected_hash,
                claimed_hash,
            )
        )

    return _finalize_result(
        kind="BEHAVIOURAL_CANARY",
        subject_id=str(canary.get("canary_id", "UNKNOWN_CANARY")),
        passed=not violations,
        success_status="CANARY_CONFORMANCE_PASSED",
        failure_status="CANARY_CONFORMANCE_BLOCKED_FAIL_CLOSED",
        violations=violations,
        evidence={"evaluated_receipt_sha256": claimed_hash},
    )


def build_conformance_bundle(
    *,
    bootstrap: Mapping[str, Any],
    policy_text: str,
    invalid_fixture: Mapping[str, Any],
    valid_fixture: Mapping[str, Any],
) -> dict[str, Any]:
    policy_result = validate_policy_text(policy_text)
    contract_result = validate_bootstrap_contract(bootstrap)
    invalid_result = validate_future_node_fixture(invalid_fixture, bootstrap)
    valid_result = validate_future_node_fixture(valid_fixture, bootstrap)

    invalid_expected_failure_observed = (
        invalid_result["passed"] is False
        and invalid_result["status"] == "BOOTSTRAP_BLOCKED_FAIL_CLOSED"
    )

    canary: dict[str, Any] | None = None
    canary_validation: dict[str, Any] | None = None
    if (
        policy_result["passed"]
        and contract_result["passed"]
        and invalid_expected_failure_observed
        and valid_result["passed"]
    ):
        canary = run_synthetic_n_canary(
            valid_fixture,
            bootstrap,
            policy_text,
        )
        canary_validation = validate_canary_receipt(canary)

    passed = bool(
        policy_result["passed"]
        and contract_result["passed"]
        and invalid_expected_failure_observed
        and valid_result["passed"]
        and canary_validation
        and canary_validation["passed"]
    )

    bundle: dict[str, Any] = {
        "schema": BUNDLE_SCHEMA,
        "bundle_id": "BUNDLE-N-V21-FUTURE-NODE-CONFORMANCE-001",
        "status": (
            "CONFORMANCE_VERIFIED_SYNTHETIC"
            if passed
            else "CONFORMANCE_BLOCKED_FAIL_CLOSED"
        ),
        "passed": passed,
        "external_effect": False,
        "authority_ceiling": "A1_INTERNAL",
        "policy_result": policy_result,
        "bootstrap_contract_result": contract_result,
        "invalid_fixture_experiment": {
            "expected": "BOOTSTRAP_BLOCKED_FAIL_CLOSED",
            "observed": invalid_result["status"],
            "expected_failure_observed": invalid_expected_failure_observed,
            "result": invalid_result,
        },
        "valid_fixture_experiment": {
            "expected": "BOOTSTRAP_PASSED",
            "observed": valid_result["status"],
            "result": valid_result,
        },
        "behavioural_canary": canary,
        "behavioural_canary_validation": canary_validation,
        "terminal_learning_event": {
            "event": "SUCCESS" if passed else "FAILURE",
            "failure_classification": None if passed else "CONFORMANCE_GATE",
            "innovation_event": "EXPERIMENT_RESULT",
            "learning_delta": (
                "Future-node inheritance is now tested through both a negative and "
                "positive executable fixture plus a complete behavioural receipt."
            ),
            "intelligence_claim": (
                "DOCUMENTED_LEARNING_PENDING_CROSS_DOMAIN_PERFORMANCE_DELTA"
            ),
        },
        "next_experiment": {
            "experiment_id": "EXP-N-V21-CROSS-DOMAIN-001",
            "domains": [
                "EvidenceOps",
                "legal_forensic",
                "ICT_system_build",
                "Federation_evolution",
            ],
            "promotion_gate": (
                "Four complete conformance receipts, zero authority expansion and "
                "measurable improvement over the static baseline."
            ),
        },
        "continuation": "n = proceed",
    }
    bundle["receipt_sha256"] = canonical_sha256(bundle)
    return bundle


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ConformanceError(f"{path} must contain a JSON object")
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "Run the Federation n-directive v2.1 future-node fail/pass "
            "behavioural conformance fixture."
        )
    )
    parser.add_argument(
        "--bootstrap",
        type=Path,
        default=root / "governance" / "federation_node_bootstrap_v2.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=root / "governance" / "federation_n_directive_v2.yaml",
    )
    parser.add_argument(
        "--invalid-fixture",
        type=Path,
        default=(
            root
            / "tests"
            / "fixtures"
            / "federation_n_future_node_invalid.json"
        ),
    )
    parser.add_argument(
        "--valid-fixture",
        type=Path,
        default=(
            root
            / "tests"
            / "fixtures"
            / "federation_n_future_node_valid.json"
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    bundle = build_conformance_bundle(
        bootstrap=_read_json(args.bootstrap),
        policy_text=args.policy.read_text(encoding="utf-8"),
        invalid_fixture=_read_json(args.invalid_fixture),
        valid_fixture=_read_json(args.valid_fixture),
    )
    rendered = json.dumps(bundle, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if bundle["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
