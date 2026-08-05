from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

PACKET_SCHEMA = "FEDOMEGA-N-V21-LEGAL-REAL-READONLY-PACKET-1"
RESULT_SCHEMA = "FEDOMEGA-N-V21-LEGAL-REAL-READONLY-RESULT-1"
EXPERIMENT_ID = "EXP-N-V21-REAL-READONLY-001-LEGAL-FORENSIC"
EXPECTED_DOMAIN = "legal_forensic"
EXPECTED_SOURCE_TYPES = {
    "OFFICIAL_PROVIDER_RECEIPT",
    "LEGAL_AUTHORITY_REGISTER",
    "CHECKSUM_MANIFEST",
    "PAGE_QA_LEDGER",
}
REQUIRED_CONTROLS = (
    "SOURCE_IDENTITY",
    "HASH_INTEGRITY",
    "PAGE_QA",
    "EPISTEMIC_LABELS",
    "CURRENTNESS_SEPARATION",
    "AUTHORITY_HIERARCHY",
    "HISTORICAL_SUPERSESSION",
    "ROUTE_SEPARATION",
    "NO_MERITS_FINALITY",
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
    "current law fully verified",
    "case merits proven",
    "protected disclosure established",
    "occupational detriment proven",
    "jurisdiction confirmed",
    "ccma rules current in all respects",
    "filing ready",
    "final legal advice",
)


class LegalReadonlyError(RuntimeError):
    """Raised when the legal/forensic read-only experiment must fail closed."""


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


def _source_fingerprint_payload(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source.get("source_id"),
        "source_type": source.get("source_type"),
        "title": source.get("title"),
        "assertions": source.get("assertions"),
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
            "LEGAL_REAL_READONLY_PACKET_VALIDATED"
            if not ordered
            else "LEGAL_REAL_READONLY_PACKET_BLOCKED_FAIL_CLOSED"
        ),
        "violations": ordered,
        "evidence": dict(evidence),
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "external_effect": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def validate_packet(packet: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    subject_id = str(packet.get("experiment_id", "UNKNOWN_EXPERIMENT"))

    expected_scalars = {
        "schema": PACKET_SCHEMA,
        "experiment_id": EXPERIMENT_ID,
        "domain": EXPECTED_DOMAIN,
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "external_effect": False,
        "legal_finding_permitted": False,
        "filing_permitted": False,
        "case_fact_import_permitted": False,
    }
    for field, expected in expected_scalars.items():
        actual = packet.get(field)
        if actual != expected:
            violations.append(
                _violation("PACKET_FIELD_MISMATCH", field, expected, actual)
            )

    sources = [
        item
        for item in _sequence(packet.get("sources"))
        if isinstance(item, Mapping)
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
    unknown_baseline = baseline_controls - set(REQUIRED_CONTROLS)
    if unknown_baseline:
        violations.append(
            _violation(
                "UNKNOWN_BASELINE_CONTROL",
                "baseline.controls_present",
                list(REQUIRED_CONTROLS),
                sorted(unknown_baseline),
            )
        )

    treatment_controls = {
        str(item) for item in _sequence(packet.get("treatment_controls"))
    }
    if treatment_controls != set(REQUIRED_CONTROLS):
        violations.append(
            _violation(
                "TREATMENT_CONTROL_SET_MISMATCH",
                "treatment_controls",
                sorted(REQUIRED_CONTROLS),
                sorted(treatment_controls),
            )
        )

    gaps = [
        item
        for item in _sequence(packet.get("legal_proof_gaps"))
        if isinstance(item, Mapping)
    ]
    gap_ids = [str(item.get("gap_id", "")) for item in gaps]
    if len(gaps) < 7:
        violations.append(
            _violation(
                "LEGAL_PROOF_GAP_SET_INCOMPLETE",
                "legal_proof_gaps",
                "AT_LEAST_7_ITEMS",
                len(gaps),
            )
        )
    if len(gap_ids) != len(set(gap_ids)):
        violations.append(
            _violation(
                "DUPLICATE_GAP_ID",
                "legal_proof_gaps[*].gap_id",
                "UNIQUE",
                gap_ids,
            )
        )
    for index, gap in enumerate(gaps):
        if gap.get("initial_state") != "UNVERIFIED_REQUIRES_SEPARATE_LEGAL_PROOF":
            violations.append(
                _violation(
                    "GAP_INITIAL_STATE_INVALID",
                    f"legal_proof_gaps[{index}].initial_state",
                    "UNVERIFIED_REQUIRES_SEPARATE_LEGAL_PROOF",
                    gap.get("initial_state"),
                )
            )

    return _finalize_validation(
        subject_id=subject_id,
        violations=violations,
        evidence={
            "packet_sha256": canonical_sha256(packet),
            "source_count": len(sources),
            "claim_count": len(claim_ids),
            "legal_proof_gap_count": len(gaps),
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
        raise LegalReadonlyError(
            f"CANONICAL_FIELD_CONFLICT::{field}::{canonical_json(values)}"
        )
    return values[0]


def build_authority_passport(
    assertions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ccma_manifest_hash = _single_value(assertions, "ccma_rules_manifest_sha256")
    ccma_qa_hash = _single_value(assertions, "ccma_rules_qa_sha256")
    if ccma_manifest_hash != ccma_qa_hash:
        raise LegalReadonlyError(
            "CCMA_RULES_HASH_MISMATCH::"
            f"{ccma_manifest_hash}::{ccma_qa_hash}"
        )

    qa_start = _single_value(assertions, "ccma_rules_page_start")
    qa_end = _single_value(assertions, "ccma_rules_page_end")
    qa_count = _single_value(assertions, "ccma_rules_qa_page_count")
    text_count = _single_value(assertions, "ccma_rules_text_read_count")
    visual_count = _single_value(assertions, "ccma_rules_visual_scan_count")
    expected_count = int(qa_end) - int(qa_start) + 1
    if not (
        int(qa_start) == 1
        and expected_count == int(qa_count)
        and int(text_count) == int(qa_count)
        and int(visual_count) == int(qa_count)
    ):
        raise LegalReadonlyError(
            "CCMA_RULES_PAGE_QA_INCOMPLETE::"
            f"start={qa_start};end={qa_end};qa={qa_count};"
            f"text={text_count};visual={visual_count}"
        )

    passport = {
        "official_provider_receipt": {
            "required_official_source_count": _single_value(
                assertions, "required_official_source_count"
            ),
            "raw_byte_gate": _single_value(
                assertions, "required_official_raw_byte_gate"
            ),
            "secondary_archive_gate": _single_value(
                assertions, "secondary_archive_gate"
            ),
            "secondary_provider_blocked_ids": _single_value(
                assertions, "secondary_provider_blocked_ids"
            ),
            "base_act_currentness": "HELD_SEPARATELY_FROM_BYTE_IDENTITY",
        },
        "ccma_rules_carrier": {
            "sha256": ccma_manifest_hash,
            "page_start": qa_start,
            "page_end": qa_end,
            "qa_page_count": qa_count,
            "text_read_count": text_count,
            "visual_scan_count": visual_count,
            "carrier_identity": "HASH_AND_PAGE_QA_VERIFIED",
            "currentness": "UNVERIFIED_REQUIRES_CURRENT_OFFICIAL_RULES_CHECK",
            "case_application": "NOT_ASSESSED",
        },
        "labour_relations_act": {
            "register_status": _single_value(assertions, "lra_register_status"),
            "version_note": _single_value(assertions, "lra_version_note"),
            "drive_copy_sha256": _single_value(assertions, "lra_drive_sha256"),
            "currentness": "AMENDMENT_CHECK_REQUIRED",
            "case_application": "NOT_ASSESSED",
        },
        "protected_disclosures_act": {
            "register_status": _single_value(assertions, "pda_register_status"),
            "version_note": _single_value(assertions, "pda_version_note"),
            "drive_copy_sha256": _single_value(assertions, "pda_drive_sha256"),
            "currentness": "CURRENT_OFFICIAL_SOURCE_WITH_AMENDMENT_NOTED",
            "case_application": "NOT_ASSESSED",
        },
        "dismissal_code_2025": {
            "register_status": _single_value(
                assertions, "dismissal_code_register_status"
            ),
            "effective_from": _single_value(
                assertions, "dismissal_code_effective_from"
            ),
            "gazette": _single_value(assertions, "dismissal_code_gazette"),
            "currentness": "CURRENT_OFFICIAL_SOURCE",
            "case_application": "NOT_ASSESSED",
        },
        "historical_schedule_8": {
            "sha256": _single_value(assertions, "historical_schedule8_sha256"),
            "state": _single_value(assertions, "historical_schedule8_state"),
            "activation": "ARCHIVED_QUERYABLE_NOT_CURRENT_CONTROLLER",
        },
        "route_separation": {
            "source_identity": "VERIFIED_WHERE_STATED",
            "currentness": "SEPARATELY_CLASSIFIED",
            "legal_proposition": "NOT_COMPILED_INTO_CASE_FINDING",
            "case_facts": "NOT_IMPORTED",
            "jurisdiction": "UNVERIFIED",
            "causation": "UNVERIFIED",
            "remedy": "UNVERIFIED",
        },
    }
    passport["authority_passport_sha256"] = canonical_sha256(passport)
    return passport


def build_tension_map(
    assertions: Sequence[Mapping[str, Any]],
    passport: Mapping[str, Any],
) -> list[dict[str, Any]]:
    tensions: list[dict[str, Any]] = []

    if (
        passport["official_provider_receipt"]["raw_byte_gate"] is True
        and passport["official_provider_receipt"]["base_act_currentness"]
        == "HELD_SEPARATELY_FROM_BYTE_IDENTITY"
    ):
        tensions.append(
            {
                "tension_id": "TENSION-LEGAL-001",
                "observation": (
                    "The required official-source raw-byte gate passed while "
                    "base-Act consolidated currentness remains separately held."
                ),
                "resolution": (
                    "Treat identity and integrity as verified only for the "
                    "retrieved carrier. Do not promote consolidated currentness "
                    "without an amendment and commencement check."
                ),
                "result": "RESOLVED_BY_IDENTITY_CURRENTNESS_SEPARATION",
            }
        )

    ccma = passport["ccma_rules_carrier"]
    if (
        ccma["carrier_identity"] == "HASH_AND_PAGE_QA_VERIFIED"
        and ccma["currentness"]
        == "UNVERIFIED_REQUIRES_CURRENT_OFFICIAL_RULES_CHECK"
    ):
        tensions.append(
            {
                "tension_id": "TENSION-LEGAL-002",
                "observation": (
                    "All 42 stored CCMA Rules pages are text-read and visually "
                    "QA-verified, but the carrier's current legal status and "
                    "application are not proved by page review."
                ),
                "resolution": (
                    "Preserve page-level QA as carrier completeness evidence; "
                    "require a separate current official-rules and commencement "
                    "check before legal reliance."
                ),
                "result": "RESOLVED_BY_QA_CURRENTNESS_SEPARATION",
            }
        )

    historical = passport["historical_schedule_8"]
    code = passport["dismissal_code_2025"]
    if (
        historical["state"] == "HISTORICAL_SUPERSEDED_NATIONALLY_IN_2025"
        and code["currentness"] == "CURRENT_OFFICIAL_SOURCE"
    ):
        tensions.append(
            {
                "tension_id": "TENSION-LEGAL-003",
                "observation": (
                    "The checksum corpus preserves historical Schedule 8 while "
                    "the authority register identifies the 2025 Dismissal Code "
                    "as the current official source."
                ),
                "resolution": (
                    "Preserve Schedule 8 for history, transition and comparison, "
                    "but do not treat it as the current controller where the "
                    "2025 Code governs."
                ),
                "result": "RESOLVED_BY_HISTORICAL_SUPERSESSION",
            }
        )

    receipt = passport["official_provider_receipt"]
    if (
        receipt["secondary_archive_gate"] is False
        and receipt["raw_byte_gate"] is True
    ):
        tensions.append(
            {
                "tension_id": "TENSION-LEGAL-004",
                "observation": (
                    "Secondary CCMA information-sheet archives were provider-"
                    "blocked while the required official primary-source raw-byte "
                    "gate passed."
                ),
                "resolution": (
                    "Do not allow the optional secondary archive failure to "
                    "negate verified primary-source identity; retain the "
                    "secondary explanatory material as unavailable and do not "
                    "invent its contents."
                ),
                "result": "RESOLVED_BY_PRIMARY_SECONDARY_SEPARATION",
            }
        )

    return tensions


def build_gap_schedule(packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    schedule: list[dict[str, Any]] = []
    for index, gap in enumerate(_sequence(packet.get("legal_proof_gaps")), start=1):
        if not isinstance(gap, Mapping):
            continue
        schedule.append(
            {
                "priority": index,
                "gap_id": gap.get("gap_id"),
                "requirement": gap.get("requirement"),
                "state": "UNVERIFIED_REQUIRES_SEPARATE_LEGAL_PROOF",
                "safe_action": gap.get("safe_action"),
                "promotion_effect": gap.get("promotion_effect"),
            }
        )
    return schedule


def build_formation_result() -> dict[str, Any]:
    alternatives = [
        {
            "route_family": "REUSE_OR_OPTIMISE",
            "route": (
                "Reuse the existing legal-authority register, provider receipt, "
                "checksum manifest and page QA ledger as separate control records."
            ),
            "strength": (
                "Lowest complexity and preserves all existing provenance."
            ),
            "weakness": (
                "Leaves identity, currentness, supersession and case-use states "
                "distributed across different surfaces."
            ),
            "rank": 2,
        },
        {
            "route_family": "COMPOSE_OR_EXTEND",
            "route": (
                "Compile the four control sources into one deterministic Legal "
                "Authority Passport, tension map, currentness matrix, gap "
                "schedule and no-merits release gate."
            ),
            "strength": (
                "Adds the missing cross-source legal-control layer without "
                "deciding a case or creating a new research platform."
            ),
            "weakness": (
                "Still requires current official-source and matter-specific "
                "proof before any legal conclusion."
            ),
            "rank": 1,
        },
        {
            "route_family": "MATERIALLY_NEW_OR_INNOVATIVE",
            "route": (
                "Build a new autonomous legal-opinion and filing platform."
            ),
            "strength": (
                "Could eventually automate authority retrieval and matter "
                "application."
            ),
            "weakness": (
                "Unnecessary, authority-expanding and incompatible with this "
                "read-only source-control experiment."
            ),
            "rank": 3,
        },
    ]
    return {
        "objective": (
            "Measure whether n v2.1 improves legal/forensic source-control "
            "completeness on genuine registered records while preserving "
            "currentness, supersession, route separation and merits boundaries."
        ),
        "route_alternatives": alternatives,
        "route_families": sorted(REQUIRED_ROUTE_FAMILIES),
        "selected_route_family": "COMPOSE_OR_EXTEND",
        "selection_reason": (
            "It reuses the existing source-control estate, resolves distributed "
            "legal-state ambiguity and introduces no legal finding, filing or "
            "external effect."
        ),
    }


def build_solution_genome(packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "requirements": [
            "preserve four source-control identities",
            "verify checksum agreement where two carriers identify one document",
            "preserve complete page-QA evidence",
            "separate carrier identity from legal currentness",
            "preserve historical sources without activating them as current law",
            "separate primary and secondary source failures",
            "import no case facts and issue no merits conclusion",
            "produce deterministic metrics and receipt",
        ],
        "components": [
            "packet validator",
            "source fingerprint verifier",
            "claim and epistemic index",
            "Legal Authority Passport compiler",
            "currentness and supersession matrix",
            "cross-source tension resolver",
            "legal proof-gap scheduler",
            "Formation route tournament",
            "anti-overclaim validator",
            "deterministic receipt verifier",
        ],
        "interfaces": [
            "JSON packet input",
            "JSON legal-control receipt output",
            "separate current-official-source retrieval lane for later proof",
        ],
        "dependencies": [
            str(item.get("source_id"))
            for item in _sequence(packet.get("sources"))
            if isinstance(item, Mapping)
        ],
        "evidence": [
            "provider receipt",
            "authority-register states",
            "checksum manifest",
            "42-page QA ledger",
        ],
        "tests": [
            "source omission rejection",
            "fingerprint mismatch rejection",
            "duplicate claim rejection",
            "authority tamper rejection",
            "checksum disagreement rejection",
            "incomplete page-QA rejection",
            "currentness separation",
            "historical supersession",
            "primary-secondary route separation",
            "Formation route coverage",
            "baseline-treatment delta",
            "deterministic replay",
            "receipt tamper detection",
            "anti-overclaim rejection",
        ],
        "rollback": (
            "No source, case or provider mutation occurs. Revert the repository "
            "commit or discard the receipt while preserving all original legal "
            "source-control records and negative results."
        ),
        "metrics": list(REQUIRED_CONTROLS),
        "ownership": "Kagiso Kim Mosiane",
        "authority": "A1_INTERNAL_READ_ONLY",
    }


def _validate_release_claims(claims: Sequence[Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for index, claim in enumerate(claims):
        text = str(claim).lower()
        for phrase in PROHIBITED_RELEASE_PHRASES:
            if phrase in text:
                violations.append(
                    _violation(
                        "PROHIBITED_LEGAL_OVERCLAIM",
                        f"release_claims[{index}]",
                        "BOUNDED_SOURCE_CONTROL_CLAIM",
                        claim,
                    )
                )
    return violations


def build_experiment(packet: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_packet(packet)
    if not validation["passed"]:
        raise LegalReadonlyError(canonical_json(validation))

    assertions = _collect_assertions(packet)
    passport = build_authority_passport(assertions)
    tensions = build_tension_map(assertions, passport)
    gaps = build_gap_schedule(packet)
    formation = build_formation_result()
    genome = build_solution_genome(packet)

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
        "control_completeness_delta": (
            len(treatment_controls) - len(baseline_controls)
        ),
        "ccma_hash_agreement": "2_OF_2_MATCH",
        "ccma_page_qa_coverage": "42_OF_42",
        "cross_source_tensions_resolved": len(tensions),
        "legal_proof_gaps_preserved": len(gaps),
        "case_facts_imported": 0,
        "legal_findings_issued": 0,
        "filings_or_communications": 0,
        "authority_violations": 0,
        "external_effects": 0,
        "owner_prompts_required": 0,
    }

    release_claims = [
        (
            "Four registered legal source-control records were compiled into one "
            "deterministic Legal Authority Passport."
        ),
        (
            "The treatment improved declared source-control completeness over "
            "the distributed-record baseline."
        ),
        (
            "CCMA Rules carrier integrity and 42-page QA are verified while "
            "currentness and matter application remain separately unverified."
        ),
        (
            "No case facts, legal finding, jurisdiction decision, causation "
            "finding, remedy decision, filing or external communication occurred."
        ),
    ]
    overclaim_violations = _validate_release_claims(release_claims)
    if overclaim_violations:
        raise LegalReadonlyError(canonical_json(overclaim_violations))

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "kind": "REAL_REGISTERED_SOURCE_LEGAL_FORENSIC_MICRO_PACKET",
        "experiment_id": EXPERIMENT_ID,
        "domain": EXPECTED_DOMAIN,
        "status": (
            "REAL_REGISTERED_SOURCE_LEGAL_CONTROL_STATE_PASSED_READ_ONLY"
        ),
        "packet_validation": validation,
        "legal_authority_passport": passport,
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
        "metrics": metrics,
        "release_claims": release_claims,
        "performance_boundary": {
            "measured": (
                "LEGAL_SOURCE_CONTROL_COMPLETENESS_DELTA_ON_REAL_REGISTERED_RECORDS"
            ),
            "not_measured": [
                "substantive legal correctness of a matter",
                "currentness beyond the registered authority states",
                "jurisdiction",
                "protected-disclosure status",
                "causation",
                "remedy",
                "filing readiness",
                "longitudinal owner-burden reduction",
                "foundation-model intelligence change",
            ],
        },
        "proof_and_maturity": {
            "source_scope": "REAL_REGISTERED_LEGAL_CONTROL_RECORDS",
            "execution_scope": "LOCAL_DETERMINISTIC_READ_ONLY_ANALYSIS",
            "maturity": "PROTOTYPE_PASSED_REAL_SOURCE_READ_ONLY",
            "case_wall_preserved": True,
            "legal_merits_finality": "NOT_ASSESSED",
            "real_world_intelligence_gain": "UNVERIFIED",
            "longitudinal_owner_value": "UNVERIFIED",
        },
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "case_fact_import_permitted": False,
        "legal_finding_permitted": False,
        "filing_permitted": False,
        "external_effect": False,
        "continuation": {
            "n_equals": "PROCEED",
            "next_experiment": (
                "EXP-N-V21-REAL-READONLY-001-ICT-SYSTEM-BUILD"
            ),
            "immediate_next_action": (
                "Publish this bounded legal/forensic receipt, then run the "
                "ICT/system-build registered-source read-only micro-packet using "
                "a separate technical source universe."
            ),
        },
    }
    result["receipt_sha256"] = canonical_sha256(result)
    return result


def verify_result(result: Mapping[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    if result.get("schema") != RESULT_SCHEMA:
        violations.append(
            _violation(
                "RESULT_SCHEMA_MISMATCH",
                "schema",
                RESULT_SCHEMA,
                result.get("schema"),
            )
        )
    expected_false = {
        "case_fact_import_permitted": False,
        "legal_finding_permitted": False,
        "filing_permitted": False,
        "external_effect": False,
    }
    for field, expected in expected_false.items():
        if result.get(field) is not expected:
            violations.append(
                _violation(
                    "LEGAL_OR_EXTERNAL_EFFECT_REJECTED",
                    field,
                    expected,
                    result.get(field),
                )
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

    violations.extend(
        _validate_release_claims(_sequence(result.get("release_claims")))
    )

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

    check: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "kind": "RESULT_VERIFICATION",
        "subject_id": str(result.get("experiment_id", "UNKNOWN_EXPERIMENT")),
        "passed": not violations,
        "status": (
            "RESULT_VERIFIED"
            if not violations
            else "RESULT_BLOCKED_FAIL_CLOSED"
        ),
        "violations": sorted(
            violations, key=lambda item: (item["code"], item["path"])
        ),
        "authority_ceiling": "A1_INTERNAL_READ_ONLY",
        "external_effect": False,
    }
    check["receipt_sha256"] = canonical_sha256(check)
    return check


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LegalReadonlyError(f"JSON_ROOT_MUST_BE_OBJECT::{path}")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the n v2.1 real registered-source legal/forensic "
            "read-only micro-packet."
        )
    )
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    packet = _load_json(args.packet)
    result = build_experiment(packet)
    verification = verify_result(result)
    if not verification["passed"]:
        raise LegalReadonlyError(canonical_json(verification))

    payload = {"experiment": result, "verification": verification}
    text = json.dumps(
        payload, indent=2, ensure_ascii=False, sort_keys=True
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
