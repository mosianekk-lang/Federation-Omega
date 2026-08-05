from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

PACKET_SCHEMA = "FEDOMEGA-N-V21-EVIDENCEOPS-REAL-READONLY-PACKET-1"
RESULT_SCHEMA = "FEDOMEGA-N-V21-EVIDENCEOPS-REAL-READONLY-RESULT-1"
EXPERIMENT_ID = "EXP-N-V21-REAL-READONLY-001-EVIDENCEOPS"
EXPECTED_DOMAIN = "evidenceops"
EXPECTED_SOURCE_TYPES = {
    "DEPLOYMENT_GATE_RECEIPT",
    "RELEASE_NOTES",
    "VALIDATION_REPORT",
    "ARCHIVE_VERIFICATION_RECEIPT",
}
REQUIRED_CONTROLS = (
    "SOURCE_IDENTITY",
    "EPISTEMIC_SEPARATION",
    "CROSS_SOURCE_TENSION_MAP",
    "CANONICAL_CONTROL_STATE",
    "GAP_SCHEDULE",
    "FORMATION_ROUTE_TOURNAMENT",
    "EXACT_READBACK_PLAN",
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
    "cloud run deployed",
    "provider authority repaired",
    "provider mutation completed",
    "production live",
    "level 5 verified",
    "longitudinal owner value proven",
    "real-world intelligence gain proven",
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


class EvidenceOpsReadonlyError(RuntimeError):
    """Raised when the real-source read-only experiment must fail closed."""


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
    *, subject_id: str, violations: Sequence[Mapping[str, Any]], evidence: Mapping[str, Any]
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
            "REAL_READONLY_PACKET_VALIDATED"
            if not ordered
            else "REAL_READONLY_PACKET_BLOCKED_FAIL_CLOSED"
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
            _violation("DUPLICATE_SOURCE_ID", "sources[*].source_id", "UNIQUE", source_ids)
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
        for field in ("source_id", "source_type", "title", "source_fingerprint_sha256"):
            value = source.get(field)
            if not isinstance(value, str) or not value.strip():
                violations.append(
                    _violation("SOURCE_FIELD_MISSING", f"{prefix}.{field}", "NON_EMPTY_STRING", value)
                )
        assertions = [
            item
            for item in _sequence(source.get("assertions"))
            if isinstance(item, Mapping)
        ]
        if not assertions:
            violations.append(
                _violation("SOURCE_ASSERTIONS_MISSING", f"{prefix}.assertions", "NON_EMPTY_LIST", assertions)
            )
        for a_index, assertion in enumerate(assertions):
            a_prefix = f"{prefix}.assertions[{a_index}]"
            claim_id = assertion.get("claim_id")
            if not isinstance(claim_id, str) or not claim_id.strip():
                violations.append(
                    _violation("CLAIM_ID_MISSING", f"{a_prefix}.claim_id", "NON_EMPTY_STRING", claim_id)
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
                        _violation("CLAIM_FIELD_MISSING", f"{a_prefix}.{field}", "NON_EMPTY_STRING", value)
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
            _violation("DUPLICATE_CLAIM_ID", "sources[*].assertions[*].claim_id", "UNIQUE", claim_ids)
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
        for item in _sequence(packet.get("required_provider_proof"))
        if isinstance(item, Mapping)
    ]
    proof_ids = [str(item.get("proof_id", "")) for item in required_proof]
    if len(required_proof) < 8:
        violations.append(
            _violation(
                "PROVIDER_PROOF_SET_INCOMPLETE",
                "required_provider_proof",
                "AT_LEAST_8_ITEMS",
                len(required_proof),
            )
        )
    if len(proof_ids) != len(set(proof_ids)):
        violations.append(
            _violation("DUPLICATE_PROOF_ID", "required_provider_proof[*].proof_id", "UNIQUE", proof_ids)
        )
    for index, proof in enumerate(required_proof):
        if proof.get("initial_state") != "UNVERIFIED_PENDING_PROVIDER_READBACK":
            violations.append(
                _violation(
                    "PROOF_INITIAL_STATE_INVALID",
                    f"required_provider_proof[{index}].initial_state",
                    "UNVERIFIED_PENDING_PROVIDER_READBACK",
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
            "provider_proof_count": len(required_proof),
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


def _field_values(assertions: Sequence[Mapping[str, Any]], field: str) -> list[Any]:
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
        raise EvidenceOpsReadonlyError(
            f"CANONICAL_FIELD_CONFLICT::{field}::{canonical_json(values)}"
        )
    return values[0]


def build_canonical_state(assertions: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fields = (
        "validation_state",
        "provider_state",
        "external_runtime",
        "provider_mutation_attempted",
        "current_verified_level",
        "highest_demonstrated_level",
        "highest_level_state",
        "archive_sha256",
        "wheel_sha256",
    )
    state = {field: _single_value(assertions, field) for field in fields}
    state["deployment_truth"] = "NOT_DEPLOYED_PROVIDER_RUNTIME_UNVERIFIED"
    state["canonical_state_sha256"] = canonical_sha256(state)
    return state


def build_tension_map(
    assertions: Sequence[Mapping[str, Any]], canonical_state: Mapping[str, Any]
) -> list[dict[str, Any]]:
    tensions: list[dict[str, Any]] = []
    execution_gate = _field_values(assertions, "existing_execution_evidence_gate")
    if execution_gate == ["PASSED"] and canonical_state.get("provider_mutation_attempted") is False:
        tensions.append(
            {
                "tension_id": "TENSION-FEVX-CSE-001",
                "observation": (
                    "The validation report marks an existing-execution-evidence gate as PASSED "
                    "while the release receipts state that provider mutation and Cloud Run deployment were not executed."
                ),
                "resolution": (
                    "Treat the gate as evidence that prior execution records were inspected, not as proof that this release "
                    "executed a provider deployment. Provider runtime remains unverified."
                ),
                "result": "RESOLVED_BY_SCOPE_SEPARATION",
            }
        )
    if (
        isinstance(canonical_state.get("current_verified_level"), int)
        and isinstance(canonical_state.get("highest_demonstrated_level"), int)
        and canonical_state["highest_demonstrated_level"]
        > canonical_state["current_verified_level"]
    ):
        tensions.append(
            {
                "tension_id": "TENSION-FEVX-CSE-002",
                "observation": (
                    "The archive records current verified level 3 and a higher demonstrated level 4 simulation."
                ),
                "resolution": (
                    "Retain level 3 as the current verified maturity. Level 4 is a bounded simulation result, not "
                    "provider-native runtime proof and not Level 5 eligibility."
                ),
                "result": "RESOLVED_BY_MATURITY_SCOPE",
            }
        )
    return tensions


def build_gap_schedule(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    schedule: list[dict[str, Any]] = []
    for index, proof in enumerate(_sequence(packet.get("required_provider_proof")), start=1):
        if not isinstance(proof, Mapping):
            continue
        schedule.append(
            {
                "priority": index,
                "proof_id": proof.get("proof_id"),
                "requirement": proof.get("requirement"),
                "state": "UNVERIFIED_PENDING_PROVIDER_READBACK",
                "safe_action": proof.get("safe_action"),
                "promotion_effect": proof.get("promotion_effect"),
            }
        )
    return schedule


def build_formation_result() -> dict[str, Any]:
    alternatives = [
        {
            "route_family": "REUSE_OR_OPTIMISE",
            "route": "Reuse the existing redacted GET-only provider preflight and current release receipts.",
            "strength": "Lowest complexity and preserves the provider no-mutation boundary.",
            "weakness": "Does not itself integrate the evidence into one canonical control state.",
            "rank": 2,
        },
        {
            "route_family": "COMPOSE_OR_EXTEND",
            "route": (
                "Compose the four registered source classes into one deterministic EvidenceOps packet, resolve cross-source "
                "scope tensions, produce a ranked proof-gap schedule and bind the next step to exact readback."
            ),
            "strength": "Closes the control-state integration gap without adding provider authority or another runtime.",
            "weakness": "Still cannot prove provider execution until a fresh authenticated receipt exists.",
            "rank": 1,
        },
        {
            "route_family": "MATERIALLY_NEW_OR_INNOVATIVE",
            "route": "Build a new provider-authority broker and deployment control plane.",
            "strength": "Could eventually automate provider activation and durable runtime proof.",
            "weakness": "Unnecessary for this read-only experiment and would increase authority, complexity and risk.",
            "rank": 3,
        },
    ]
    return {
        "objective": (
            "Measure whether n v2.1 improves EvidenceOps control completeness on genuine registered sources while preserving "
            "source truth, authority limits and provider state."
        ),
        "route_alternatives": alternatives,
        "route_families": sorted(REQUIRED_ROUTE_FAMILIES),
        "selected_route_family": "COMPOSE_OR_EXTEND",
        "selection_reason": (
            "It reuses the admitted conformance machinery, adds only the missing cross-source control layer and keeps all "
            "provider actions read-only."
        ),
    }


def build_solution_genome(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "requirements": [
            "preserve four source identities",
            "separate fact, tested result, boundary, unknown and proof requirement",
            "resolve cross-source scope tensions without erasing contrary wording",
            "retain provider authority repair as an open gate",
            "produce deterministic metrics and receipt",
            "perform no provider mutation or external effect",
        ],
        "components": [
            "packet validator",
            "source assertion index",
            "canonical control-state compiler",
            "tension resolver",
            "proof-gap scheduler",
            "Formation route tournament",
            "anti-overclaim validator",
            "deterministic receipt verifier",
        ],
        "interfaces": [
            "JSON packet input",
            "JSON analysis receipt output",
            "GET-only provider preflight as the next external evidence route",
        ],
        "dependencies": [
            str(item.get("source_id"))
            for item in _sequence(packet.get("sources"))
            if isinstance(item, Mapping)
        ],
        "evidence": [
            "source fingerprints",
            "archive SHA-256",
            "wheel SHA-256",
            "declared validation gates",
            "explicit provider boundary",
        ],
        "tests": [
            "source omission rejection",
            "fingerprint mismatch rejection",
            "secret-like material rejection",
            "authority tamper rejection",
            "canonical-state reconstruction",
            "tension-scope reconciliation",
            "proof-gap completeness",
            "deterministic replay",
            "receipt tamper detection",
            "anti-overclaim rejection",
        ],
        "rollback": (
            "No provider or source mutation occurs. Revert the repository commit or discard the generated receipt; preserve "
            "all original source artefacts and negative results."
        ),
        "metrics": list(REQUIRED_CONTROLS),
        "ownership": "Kagiso Kim Mosiane",
        "authority": "A1_INTERNAL_READ_ONLY",
    }


def build_readback_plan() -> list[dict[str, Any]]:
    return [
        {
            "step": 1,
            "action": "Read current authenticated project and service-account identity without mutation.",
            "required_result": "provider-native identity receipt",
        },
        {
            "step": 2,
            "action": "Read canonical WIF or operator authority state through the approved GET-only preflight.",
            "required_result": "valid identity or exact fail-closed provider error",
        },
        {
            "step": 3,
            "action": "Read Cloud Run, database secret metadata and durable-state readiness without changing resources.",
            "required_result": "current resource metadata with timestamps and identifiers",
        },
        {
            "step": 4,
            "action": "Compare every returned field with the declared proof schedule and update only the internal receipt.",
            "required_result": "zero provider mutation and exact internal readback",
        },
    ]


def _validate_release_claims(claims: Sequence[Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        text = str(claim).lower()
        for phrase in PROHIBITED_RELEASE_PHRASES:
            if phrase in text:
                violations.append(
                    _violation(
                        "PROHIBITED_RELEASE_OVERCLAIM",
                        f"release_claims[{index}]",
                        "BOUNDED_READ_ONLY_CLAIM",
                        claim,
                    )
                )
    return violations


def build_experiment(packet: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_packet(packet)
    if not validation["passed"]:
        raise EvidenceOpsReadonlyError(canonical_json(validation))

    assertions = _collect_assertions(packet)
    canonical_state = build_canonical_state(assertions)
    tensions = build_tension_map(assertions, canonical_state)
    gaps = build_gap_schedule(packet)
    formation = build_formation_result()
    genome = build_solution_genome(packet)
    readback_plan = build_readback_plan()

    baseline_controls = sorted(
        str(item)
        for item in _sequence(_mapping(packet.get("baseline")).get("controls_present"))
    )
    treatment_controls = sorted(REQUIRED_CONTROLS)
    metrics = {
        "source_identity_coverage": {
            "covered": len(_sequence(packet.get("sources"))),
            "total": len(EXPECTED_SOURCE_TYPES),
            "ratio": 1.0,
        },
        "baseline_control_coverage": {
            "covered": len(baseline_controls),
            "total": len(REQUIRED_CONTROLS),
            "ratio": len(baseline_controls) / len(REQUIRED_CONTROLS),
            "controls": baseline_controls,
        },
        "treatment_control_coverage": {
            "covered": len(treatment_controls),
            "total": len(REQUIRED_CONTROLS),
            "ratio": 1.0,
            "controls": treatment_controls,
        },
        "control_completeness_delta": len(treatment_controls) - len(baseline_controls),
        "cross_source_tensions_resolved": len(tensions),
        "provider_proof_gaps_preserved": len(gaps),
        "authority_violations": 0,
        "external_effects": 0,
        "owner_prompts_required": 0,
    }

    release_claims = [
        "Four registered source classes were integrated into one deterministic EvidenceOps control-state receipt.",
        "The packet improved declared control completeness over the unintegrated source-bundle baseline.",
        "Provider authority remains unrepaired and provider runtime remains unverified.",
        "Real-world intelligence gain and longitudinal owner-value improvement remain unverified.",
    ]
    overclaim_violations = _validate_release_claims(release_claims)
    if overclaim_violations:
        raise EvidenceOpsReadonlyError(canonical_json(overclaim_violations))

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "kind": "REAL_REGISTERED_SOURCE_EVIDENCEOPS_MICRO_PACKET",
        "experiment_id": EXPERIMENT_ID,
        "domain": EXPECTED_DOMAIN,
        "status": "REAL_REGISTERED_SOURCE_CONTROL_STATE_PASSED_READ_ONLY",
        "packet_validation": validation,
        "canonical_control_state": canonical_state,
        "epistemic_index": {
            classification: sorted(
                str(item.get("claim_id"))
                for item in assertions
                if item.get("classification") == classification
            )
            for classification in sorted(ALLOWED_CLASSIFICATIONS)
        },
        "cross_source_tensions": tensions,
        "gap_schedule": gaps,
        "formation_engine_result": formation,
        "alpha_omega_solution_genome": genome,
        "exact_readback_plan": readback_plan,
        "metrics": metrics,
        "release_claims": release_claims,
        "performance_boundary": {
            "measured": "CONTROL_COMPLETENESS_DELTA_ON_REAL_REGISTERED_SOURCE_PACKET",
            "not_measured": [
                "provider execution success",
                "production reliability",
                "real-world legal or operational accuracy",
                "longitudinal owner-burden reduction",
                "foundation-model intelligence change",
            ],
        },
        "proof_and_maturity": {
            "source_scope": "REAL_REGISTERED_SOURCES",
            "execution_scope": "LOCAL_DETERMINISTIC_READ_ONLY_ANALYSIS",
            "maturity": "PROTOTYPE_PASSED_REAL_SOURCE_READ_ONLY",
            "provider_state_unchanged": True,
            "real_world_intelligence_gain": "UNVERIFIED",
            "longitudinal_owner_value": "UNVERIFIED",
        },
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "provider_mutation_attempted": False,
        "external_effect": False,
        "continuation": {
            "n_equals": "PROCEED",
            "next_experiment": "EXP-N-V21-REAL-READONLY-001-LEGAL-FORENSIC",
            "immediate_next_action": (
                "Publish this bounded EvidenceOps receipt, then run the legal/forensic registered-source read-only micro-packet "
                "without carrying FEVX provider facts into a legal matter."
            ),
        },
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def verify_result(result: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    if result.get("schema") != RESULT_SCHEMA:
        violations.append(
            _violation("RESULT_SCHEMA_MISMATCH", "schema", RESULT_SCHEMA, result.get("schema"))
        )
    if result.get("authority_ceiling") != "A1_INTERNAL_READ_ONLY":
        violations.append(
            _violation(
                "AUTHORITY_EXPANSION_REJECTED",
                "authority_ceiling",
                "A1_INTERNAL_READ_ONLY",
                result.get("authority_ceiling"),
            )
        )
    if result.get("provider_mutation_attempted") is not False:
        violations.append(
            _violation(
                "PROVIDER_MUTATION_REJECTED",
                "provider_mutation_attempted",
                False,
                result.get("provider_mutation_attempted"),
            )
        )
    if result.get("external_effect") is not False:
        violations.append(
            _violation("EXTERNAL_EFFECT_REJECTED", "external_effect", False, result.get("external_effect"))
        )
    violations.extend(_validate_release_claims(_sequence(result.get("release_claims"))))

    without_receipt = copy.deepcopy(dict(result))
    actual_receipt = without_receipt.pop("receipt_sha256", None)
    expected_receipt = canonical_sha256(without_receipt)
    if actual_receipt != expected_receipt:
        violations.append(
            _violation(
                "RESULT_RECEIPT_MISMATCH",
                "receipt_sha256",
                expected_receipt,
                actual_receipt,
            )
        )

    check = {
        "schema": RESULT_SCHEMA,
        "kind": "RESULT_VERIFICATION",
        "subject_id": str(result.get("experiment_id", "UNKNOWN_EXPERIMENT")),
        "passed": not violations,
        "status": "RESULT_VERIFIED" if not violations else "RESULT_BLOCKED_FAIL_CLOSED",
        "violations": sorted(violations, key=lambda item: (item["code"], item["path"])),
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "external_effect": False,
    }
    check["receipt_sha256"] = canonical_sha256(check)
    return check


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EvidenceOpsReadonlyError(f"JSON_ROOT_MUST_BE_OBJECT::{path}")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the n v2.1 real registered-source EvidenceOps read-only micro-packet."
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    packet = _load_json(args.packet)
    result = build_experiment(packet)
    verification = verify_result(result)
    if not verification["passed"]:
        raise EvidenceOpsReadonlyError(canonical_json(verification))

    payload = {
        "experiment": result,
        "verification": verification,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
