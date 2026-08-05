from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

GOVERNANCE_DIR = Path(__file__).resolve().parent
ROOT = GOVERNANCE_DIR.parent
if str(GOVERNANCE_DIR) not in sys.path:
    sys.path.insert(0, str(GOVERNANCE_DIR))

import federation_n_directive_conformance as base


PROFILE_SCHEMA = "FEDOMEGA-N-DIRECTIVE-DOMAIN-PROFILES-1"
DOMAIN_RESULT_SCHEMA = "FEDOMEGA-N-DIRECTIVE-DOMAIN-CONFORMANCE-RESULT-1"
SUITE_SCHEMA = "FEDOMEGA-N-DIRECTIVE-CROSS-DOMAIN-CONFORMANCE-SUITE-1"
EXPECTED_DOMAINS = (
    "evidenceops",
    "legal_forensic",
    "ict_system_build",
    "federation_evolution",
)
REQUIRED_ROUTE_FAMILIES = {
    "REUSE_OR_OPTIMISE",
    "COMPOSE_OR_EXTEND",
    "MATERIALLY_NEW_OR_INNOVATIVE",
}
REQUIRED_INNOVATION_CLASSES = {
    "STRONGEST_VERIFIED_REUSE_ROUTE",
    "STRONGEST_INCREMENTAL_IMPROVEMENT",
    "STRONGEST_MATERIALLY_DIFFERENT_SOLUTION",
    "HIGHEST_INFORMATION_REVERSIBLE_EXPERIMENT",
}
REQUIRED_CANARY_OUTPUTS = (
    "formation_engine_result",
    "alpha_omega_foundry_result",
    "solution_alternatives_considered",
    "reuse_vs_build_decision",
    "selected_solution",
    "work_performed",
    "innovation_delta",
    "learning_delta",
    "proof_and_maturity",
    "next_experiment_or_opportunity",
    "complete_next_best_automated_pathway",
    "continuation",
)


class DomainConformanceError(RuntimeError):
    """Raised when a cross-domain conformance suite cannot start or complete."""


def _sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def _finalize(
    *,
    kind: str,
    subject_id: str,
    passed: bool,
    success_status: str,
    failure_status: str,
    violations: list[dict[str, Any]],
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": DOMAIN_RESULT_SCHEMA,
        "kind": kind,
        "subject_id": subject_id,
        "passed": passed,
        "status": success_status if passed else failure_status,
        "violations": sorted(
            violations,
            key=lambda item: (item["code"], item["path"]),
        ),
        "evidence": dict(evidence or {}),
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
    }
    result["receipt_sha256"] = base.canonical_sha256(result)
    return result


def validate_profile_document(document: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    if document.get("schema") != PROFILE_SCHEMA:
        violations.append(
            _violation(
                "PROFILE_DOCUMENT_SCHEMA_MISMATCH",
                "schema",
                PROFILE_SCHEMA,
                document.get("schema"),
            )
        )
    profiles = [
        item
        for item in _sequence(document.get("profiles"))
        if isinstance(item, Mapping)
    ]
    domain_ids = [str(item.get("domain_id", "")) for item in profiles]
    if len(profiles) != len(EXPECTED_DOMAINS):
        violations.append(
            _violation(
                "PROFILE_COUNT_MISMATCH",
                "profiles",
                len(EXPECTED_DOMAINS),
                len(profiles),
            )
        )
    if set(domain_ids) != set(EXPECTED_DOMAINS):
        violations.append(
            _violation(
                "DOMAIN_SET_MISMATCH",
                "profiles[*].domain_id",
                sorted(EXPECTED_DOMAINS),
                sorted(domain_ids),
            )
        )
    if len(domain_ids) != len(set(domain_ids)):
        violations.append(
            _violation(
                "DUPLICATE_DOMAIN_ID",
                "profiles[*].domain_id",
                "UNIQUE",
                domain_ids,
            )
        )
    return _finalize(
        kind="DOMAIN_PROFILE_DOCUMENT",
        subject_id=str(document.get("suite_id", "UNKNOWN_SUITE")),
        passed=not violations,
        success_status="DOMAIN_PROFILE_DOCUMENT_PASSED",
        failure_status="DOMAIN_PROFILE_DOCUMENT_BLOCKED_FAIL_CLOSED",
        violations=violations,
        evidence={"document_sha256": base.canonical_sha256(document)},
    )


def validate_domain_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    domain_id = str(profile.get("domain_id", "UNKNOWN_DOMAIN"))
    for field in ("domain_id", "node_id", "mission_id", "objective"):
        value = profile.get(field)
        if not isinstance(value, str) or not value.strip():
            violations.append(
                _violation(
                    "PROFILE_FIELD_MISSING",
                    field,
                    "NON_EMPTY_STRING",
                    value,
                )
            )
    if domain_id not in EXPECTED_DOMAINS:
        violations.append(
            _violation(
                "UNKNOWN_DOMAIN",
                "domain_id",
                list(EXPECTED_DOMAINS),
                domain_id,
            )
        )

    list_fields = (
        "success_criteria",
        "constraints",
        "available_capabilities",
        "proof_requirements",
        "required_controls",
        "prohibited_outcomes",
    )
    for field in list_fields:
        value = profile.get(field)
        if not isinstance(value, list) or not value:
            violations.append(
                _violation(
                    "PROFILE_SEQUENCE_MISSING",
                    field,
                    "NON_EMPTY_LIST",
                    value,
                )
            )

    success_criteria = set(
        value
        for value in _sequence(profile.get("success_criteria"))
        if isinstance(value, str)
    )
    required_controls = set(
        value
        for value in _sequence(profile.get("required_controls"))
        if isinstance(value, str)
    )
    missing_controls = sorted(required_controls - success_criteria)
    if missing_controls:
        violations.append(
            _violation(
                "REQUIRED_CONTROL_NOT_IN_SUCCESS_CRITERIA",
                "required_controls",
                "SUBSET_OF_SUCCESS_CRITERIA",
                missing_controls,
            )
        )

    constraints = set(
        value
        for value in _sequence(profile.get("constraints"))
        if isinstance(value, str)
    )
    prohibited = set(
        value
        for value in _sequence(profile.get("prohibited_outcomes"))
        if isinstance(value, str)
    )
    missing_holds = sorted(prohibited - constraints)
    if missing_holds:
        violations.append(
            _violation(
                "PROHIBITED_OUTCOME_NOT_HELD",
                "prohibited_outcomes",
                "SUBSET_OF_CONSTRAINTS",
                missing_holds,
            )
        )

    return _finalize(
        kind="DOMAIN_PROFILE",
        subject_id=domain_id,
        passed=not violations,
        success_status="DOMAIN_PROFILE_PASSED",
        failure_status="DOMAIN_PROFILE_BLOCKED_FAIL_CLOSED",
        violations=violations,
        evidence={"profile_sha256": base.canonical_sha256(profile)},
    )


def build_domain_fixture(
    profile: Mapping[str, Any],
    base_fixture: Mapping[str, Any],
) -> dict[str, Any]:
    profile_result = validate_domain_profile(profile)
    if not profile_result["passed"]:
        raise DomainConformanceError(
            f"domain profile {profile.get('domain_id')} is fail-closed"
        )

    fixture = copy.deepcopy(dict(base_fixture))
    fixture["node_id"] = profile["node_id"]
    fixture["parent_node"] = "CENTRAL-MASTER"
    fixture["privacy_tier"] = "P1_INTERNAL_SYNTHETIC"
    fixture["domain_profile"] = {
        "domain_id": profile["domain_id"],
        "profile_version": profile.get("profile_version", "1.0.0"),
        "required_controls": list(profile["required_controls"]),
        "prohibited_outcomes": list(profile["prohibited_outcomes"]),
    }
    fixture["mission"] = {
        "mission_id": profile["mission_id"],
        "directive": "n",
        "objective": profile["objective"],
        "success_criteria": list(profile["success_criteria"]),
        "constraints": list(profile["constraints"]),
        "available_capabilities": list(profile["available_capabilities"]),
        "proof_requirements": list(profile["proof_requirements"]),
    }
    return fixture


def validate_domain_canary(
    profile: Mapping[str, Any],
    fixture: Mapping[str, Any],
    canary: Mapping[str, Any],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    domain_id = str(profile.get("domain_id", "UNKNOWN_DOMAIN"))
    base_validation = base.validate_canary_receipt(canary)
    if not base_validation["passed"]:
        for item in base_validation["violations"]:
            inherited = dict(item)
            inherited["code"] = f"BASE_{item['code']}"
            inherited["path"] = f"canary.{item['path']}"
            violations.append(inherited)

    formation = _mapping(canary.get("formation_engine_result"))
    if formation.get("objective_locked") != profile.get("objective"):
        violations.append(
            _violation(
                "OBJECTIVE_NOT_LOCKED",
                "formation_engine_result.objective_locked",
                profile.get("objective"),
                formation.get("objective_locked"),
            )
        )
    action_integrity = _mapping(formation.get("action_verb_integrity"))
    if action_integrity.get("directive") != "n" or action_integrity.get(
        "preserved"
    ) is not True:
        violations.append(
            _violation(
                "ACTION_VERB_NOT_PRESERVED",
                "formation_engine_result.action_verb_integrity",
                {"directive": "n", "preserved": True},
                dict(action_integrity),
            )
        )

    inspected = formation.get("capabilities_inspected")
    if inspected != profile.get("available_capabilities"):
        violations.append(
            _violation(
                "CAPABILITY_PREFLIGHT_DRIFT",
                "formation_engine_result.capabilities_inspected",
                profile.get("available_capabilities"),
                inspected,
            )
        )

    route_families = {
        route.get("family")
        for route in _sequence(formation.get("route_families"))
        if isinstance(route, Mapping)
    }
    if route_families != REQUIRED_ROUTE_FAMILIES:
        violations.append(
            _violation(
                "ROUTE_FAMILY_COVERAGE_INCOMPLETE",
                "formation_engine_result.route_families",
                sorted(REQUIRED_ROUTE_FAMILIES),
                sorted(item for item in route_families if item),
            )
        )

    foundry = _mapping(canary.get("alpha_omega_foundry_result"))
    genome = _mapping(foundry.get("solution_genome"))
    requirements = genome.get("requirements")
    if requirements != profile.get("success_criteria"):
        violations.append(
            _violation(
                "SOLUTION_GENOME_REQUIREMENT_DRIFT",
                "alpha_omega_foundry_result.solution_genome.requirements",
                profile.get("success_criteria"),
                requirements,
            )
        )

    required_controls = set(_sequence(profile.get("required_controls")))
    genome_controls = set(_sequence(requirements))
    missing_controls = sorted(required_controls - genome_controls)
    if missing_controls:
        violations.append(
            _violation(
                "DOMAIN_CONTROL_NOT_COMPILED",
                "alpha_omega_foundry_result.solution_genome.requirements",
                sorted(required_controls),
                missing_controls,
            )
        )

    fixture_constraints = set(
        _sequence(_mapping(fixture.get("mission")).get("constraints"))
    )
    prohibited = set(_sequence(profile.get("prohibited_outcomes")))
    missing_holds = sorted(prohibited - fixture_constraints)
    if missing_holds:
        violations.append(
            _violation(
                "PROHIBITED_OUTCOME_NOT_BOUND",
                "mission.constraints",
                sorted(prohibited),
                missing_holds,
            )
        )

    frontier = [
        item
        for item in _sequence(canary.get("innovation_frontier"))
        if isinstance(item, Mapping)
    ]
    classes = {item.get("candidate_class") for item in frontier}
    if classes != REQUIRED_INNOVATION_CLASSES or len(frontier) != 4:
        violations.append(
            _violation(
                "INNOVATION_CLASS_COVERAGE_INCOMPLETE",
                "innovation_frontier",
                sorted(REQUIRED_INNOVATION_CLASSES),
                sorted(item for item in classes if item),
            )
        )

    missing_outputs = [
        field for field in REQUIRED_CANARY_OUTPUTS if not canary.get(field)
    ]
    if missing_outputs:
        violations.append(
            _violation(
                "REQUIRED_CANARY_OUTPUT_MISSING",
                "canary",
                list(REQUIRED_CANARY_OUTPUTS),
                missing_outputs,
            )
        )

    proof = _mapping(canary.get("proof_and_maturity"))
    for field in ("external_effect", "provider_mutation", "trust_transfer"):
        if proof.get(field) is not False:
            violations.append(
                _violation(
                    "DOMAIN_AUTHORITY_BOUNDARY_VIOLATION",
                    f"proof_and_maturity.{field}",
                    False,
                    proof.get(field),
                )
            )
    if proof.get("authority_ceiling") != "A1_INTERNAL":
        violations.append(
            _violation(
                "DOMAIN_AUTHORITY_CEILING_MISMATCH",
                "proof_and_maturity.authority_ceiling",
                "A1_INTERNAL",
                proof.get("authority_ceiling"),
            )
        )
    if canary.get("continuation") != "n = proceed":
        violations.append(
            _violation(
                "DOMAIN_CONTINUATION_MISSING",
                "continuation",
                "n = proceed",
                canary.get("continuation"),
            )
        )

    return _finalize(
        kind="DOMAIN_BEHAVIOURAL_CANARY",
        subject_id=domain_id,
        passed=not violations,
        success_status="DOMAIN_CANARY_CONFORMANCE_PASSED",
        failure_status="DOMAIN_CANARY_CONFORMANCE_BLOCKED_FAIL_CLOSED",
        violations=violations,
        evidence={
            "fixture_sha256": base.canonical_sha256(fixture),
            "canary_receipt_sha256": canary.get("receipt_sha256"),
            "base_validation_receipt_sha256": base_validation.get(
                "receipt_sha256"
            ),
        },
    )


def run_domain_canary(
    profile: Mapping[str, Any],
    *,
    base_fixture: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
    policy_text: str,
) -> dict[str, Any]:
    fixture = build_domain_fixture(profile, base_fixture)
    fixture_validation = base.validate_future_node_fixture(fixture, bootstrap)
    if not fixture_validation["passed"]:
        raise DomainConformanceError(
            f"generated fixture for {profile.get('domain_id')} failed bootstrap"
        )

    first = base.run_synthetic_n_canary(fixture, bootstrap, policy_text)
    second = base.run_synthetic_n_canary(fixture, bootstrap, policy_text)
    deterministic_replay = (
        first.get("receipt_sha256") == second.get("receipt_sha256")
    )
    domain_validation = validate_domain_canary(profile, fixture, first)
    passed = bool(domain_validation["passed"] and deterministic_replay)

    result: dict[str, Any] = {
        "schema": DOMAIN_RESULT_SCHEMA,
        "kind": "DOMAIN_CANARY_EXECUTION",
        "domain_id": profile["domain_id"],
        "node_id": profile["node_id"],
        "mission_id": profile["mission_id"],
        "passed": passed,
        "status": (
            "DOMAIN_CONFORMANCE_VERIFIED_SYNTHETIC"
            if passed
            else "DOMAIN_CONFORMANCE_BLOCKED_FAIL_CLOSED"
        ),
        "fixture_validation": fixture_validation,
        "domain_validation": domain_validation,
        "deterministic_replay": deterministic_replay,
        "formation_route_family_count": len(
            _sequence(
                _mapping(first.get("formation_engine_result")).get(
                    "route_families"
                )
            )
        ),
        "innovation_candidate_count": len(
            _sequence(first.get("innovation_frontier"))
        ),
        "required_output_count": sum(
            bool(first.get(field)) for field in REQUIRED_CANARY_OUTPUTS
        ),
        "required_output_total": len(REQUIRED_CANARY_OUTPUTS),
        "authority_violations": len(
            [
                item
                for item in domain_validation["violations"]
                if "AUTHORITY" in item["code"]
            ]
        ),
        "synthetic_owner_prompts_required": 0,
        "canary": first,
        "external_effect": False,
        "authority_ceiling": "A1_INTERNAL",
    }
    result["receipt_sha256"] = base.canonical_sha256(result)
    return result


def build_cross_domain_suite(
    *,
    profile_document: Mapping[str, Any],
    base_fixture: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
    policy_text: str,
) -> dict[str, Any]:
    profile_document_result = validate_profile_document(profile_document)
    if not profile_document_result["passed"]:
        raise DomainConformanceError("domain profile document is fail-closed")

    policy_result = base.validate_policy_text(policy_text)
    bootstrap_result = base.validate_bootstrap_contract(bootstrap)
    base_fixture_result = base.validate_future_node_fixture(
        base_fixture,
        bootstrap,
    )
    if not (
        policy_result["passed"]
        and bootstrap_result["passed"]
        and base_fixture_result["passed"]
    ):
        raise DomainConformanceError(
            "static policy, bootstrap or base fixture gate failed"
        )

    profiles = {
        str(item["domain_id"]): item
        for item in _sequence(profile_document.get("profiles"))
        if isinstance(item, Mapping)
    }
    domain_results = [
        run_domain_canary(
            profiles[domain_id],
            base_fixture=base_fixture,
            bootstrap=bootstrap,
            policy_text=policy_text,
        )
        for domain_id in EXPECTED_DOMAINS
    ]

    domains_passed = sum(result["passed"] for result in domain_results)
    outputs_observed = sum(
        int(result["required_output_count"]) for result in domain_results
    )
    outputs_total = len(REQUIRED_CANARY_OUTPUTS) * len(domain_results)
    route_families_observed = sum(
        int(result["formation_route_family_count"])
        for result in domain_results
    )
    innovation_candidates_observed = sum(
        int(result["innovation_candidate_count"])
        for result in domain_results
    )
    authority_violations = sum(
        int(result["authority_violations"]) for result in domain_results
    )
    deterministic_domains = sum(
        bool(result["deterministic_replay"]) for result in domain_results
    )
    synthetic_owner_prompts = sum(
        int(result["synthetic_owner_prompts_required"])
        for result in domain_results
    )
    passed = bool(
        domains_passed == len(EXPECTED_DOMAINS)
        and outputs_observed == outputs_total
        and route_families_observed
        == len(REQUIRED_ROUTE_FAMILIES) * len(EXPECTED_DOMAINS)
        and innovation_candidates_observed
        == len(REQUIRED_INNOVATION_CLASSES) * len(EXPECTED_DOMAINS)
        and authority_violations == 0
        and deterministic_domains == len(EXPECTED_DOMAINS)
    )

    report: dict[str, Any] = {
        "schema": SUITE_SCHEMA,
        "suite_id": str(
            profile_document.get(
                "suite_id",
                "SUITE-N-V21-CROSS-DOMAIN-001",
            )
        ),
        "status": (
            "CROSS_DOMAIN_CONFORMANCE_VERIFIED_SYNTHETIC"
            if passed
            else "CROSS_DOMAIN_CONFORMANCE_BLOCKED_FAIL_CLOSED"
        ),
        "passed": passed,
        "baseline": {
            "state": "STATIC_CONTRACT_VERIFIED",
            "contract_layers_passed": 3,
            "behavioural_domain_receipts": 0,
            "domain_transfer_coverage": "0/4",
            "executed_required_output_checks": 0,
            "intelligence_improvement_claim": False,
        },
        "current": {
            "state": (
                "CROSS_DOMAIN_CONFORMANCE_VERIFIED_SYNTHETIC"
                if passed
                else "CROSS_DOMAIN_CONFORMANCE_BLOCKED_FAIL_CLOSED"
            ),
            "domains_passed": domains_passed,
            "domains_total": len(EXPECTED_DOMAINS),
            "domain_transfer_coverage": (
                f"{domains_passed}/{len(EXPECTED_DOMAINS)}"
            ),
            "required_outputs_observed": outputs_observed,
            "required_outputs_total": outputs_total,
            "required_output_coverage_percent": (
                100.0 * outputs_observed / outputs_total
                if outputs_total
                else 0.0
            ),
            "formation_route_families_observed": route_families_observed,
            "innovation_candidates_observed": (
                innovation_candidates_observed
            ),
            "deterministic_domain_replays": deterministic_domains,
            "authority_violations": authority_violations,
            "synthetic_owner_prompts_required": synthetic_owner_prompts,
        },
        "synthetic_coverage_delta": {
            "behavioural_domain_receipts": domains_passed,
            "domain_transfer_coverage_points": domains_passed,
            "executed_required_output_checks": outputs_observed,
            "formation_route_families": route_families_observed,
            "innovation_candidates": innovation_candidates_observed,
        },
        "domain_results": domain_results,
        "terminal_learning_event": {
            "event": "SUCCESS" if passed else "FAILURE",
            "additional_events": [
                "INNOVATION_CANDIDATE",
                "EXPERIMENT_RESULT",
            ],
            "lesson": (
                "The v2.1 n contract transfers across four synthetic domains "
                "when objectives, capabilities, domain controls, holds, both "
                "engines, innovation, proof and learning are executable rather "
                "than merely stored."
            ),
            "intelligence_claim": (
                "DOCUMENTED_LEARNING_PENDING_REAL_COMPARABLE_TASKS_"
                "AND_LONGITUDINAL_OWNER_VALUE"
            ),
        },
        "next_experiment": {
            "experiment_id": "EXP-N-V21-REAL-READONLY-001",
            "objective": (
                "Run one real but read-only, non-consequential micro-packet in "
                "each domain using registered source identities and compare "
                "owner corrections, completion time, proof completeness, route "
                "quality and recovery against the pre-v2.1 baseline."
            ),
            "proof_gate": (
                "Four real read-only receipts, no authority expansion, no "
                "case-wall breach, preserved negative results and measurable "
                "improvement on at least one predeclared outcome."
            ),
            "first_packet": (
                "EvidenceOps registered-source control-state micro-packet"
            ),
        },
        "proof_boundary": {
            "verified": [
                "four synthetic domain receipts",
                "full required-output coverage",
                "three Formation route families per domain",
                "four innovation candidates per domain",
                "deterministic replay",
                "zero authority-boundary violations",
            ],
            "unverified": [
                "real-world task accuracy improvement",
                "longitudinal owner-burden reduction",
                "production or provider runtime behaviour",
                "consequential external action",
            ],
            "authority_ceiling": "A1_INTERNAL",
            "external_effect": False,
            "provider_mutation": False,
            "trust_transfer": False,
        },
        "complete_next_best_automated_pathway": {
            "result": (
                "Real read-only cross-domain performance delta measured"
            ),
            "steps": [
                "select one registered, non-consequential micro-packet per domain",
                "lock the source identities, case walls and success measures",
                "run Formation and Alpha-to-Omega using the domain profile",
                "capture proof, failures, negative results and owner corrections",
                "compare each result with a documented pre-v2.1 baseline",
                "repair only the failing control and rerun once",
                "promote only the exact domain scope with measured improvement",
            ],
            "failure_route": (
                "preserve the failing receipt, isolate the affected domain, "
                "continue unaffected domains and choose a materially different "
                "reversible route"
            ),
            "complete_condition": (
                "four real read-only receipts and at least one measured "
                "improvement with zero material regression"
            ),
            "partial_condition": (
                "one or more domains pass while another remains held by a named "
                "source, authority, privacy or proof gate"
            ),
            "blocked_condition": (
                "no registered safe source packet exists or a case-wall, "
                "authority or proof gate cannot be satisfied"
            ),
            "next_n_executes": (
                "the first EvidenceOps registered-source control-state "
                "micro-packet, then the remaining non-conflicting domains"
            ),
            "benefit": (
                "moves the n directive from synthetic transfer proof to measured "
                "real-work performance without exposing consequential actions"
            ),
        },
        "authority_ceiling": "A1_INTERNAL",
        "external_effect": False,
        "continuation": "n = proceed",
    }
    report["receipt_sha256"] = base.canonical_sha256(report)
    return report


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DomainConformanceError(f"{path} must contain a JSON object")
    return payload


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Federation n-directive v2.1 four-domain synthetic "
            "behavioural conformance suite."
        )
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        default=(
            ROOT
            / "tests"
            / "fixtures"
            / "federation_n_domain_conformance_profiles.json"
        ),
    )
    parser.add_argument(
        "--base-fixture",
        type=Path,
        default=(
            ROOT
            / "tests"
            / "fixtures"
            / "federation_n_future_node_valid.json"
        ),
    )
    parser.add_argument(
        "--bootstrap",
        type=Path,
        default=ROOT / "governance" / "federation_node_bootstrap_v2.json",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=ROOT / "governance" / "federation_n_directive_v2.yaml",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_cross_domain_suite(
        profile_document=_read_json(args.profiles),
        base_fixture=_read_json(args.base_fixture),
        bootstrap=_read_json(args.bootstrap),
        policy_text=args.policy.read_text(encoding="utf-8"),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
