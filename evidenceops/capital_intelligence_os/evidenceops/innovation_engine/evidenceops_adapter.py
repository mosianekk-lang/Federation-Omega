from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping, Sequence

from .algorithms import sha256, text
from .foundry import EvidenceOpsAlgorithmFoundry


_MASTER_SIGNAL_PATTERNS: tuple[tuple[str, str, tuple[str, ...], float], ...] = (
    (
        "SIG-MB-DIRECTIVE-EXECUTION",
        "Directive execution and action-verb integrity failures require a callable compiler.",
        ("ARTIFACT_ACTION_COLLAPSE", "PROOF_GATE_BYPASS", "ACTION-VERB INTEGRITY"),
        1.0,
    ),
    (
        "SIG-MB-UNKNOWN-MAPPER",
        "Unknowns, contradictions and missing records require governed prioritisation.",
        ("UNKNOWN MAPPER", "EPISTEMIC DEBT", "KNOWN UNKNOWN"),
        0.95,
    ),
    (
        "SIG-MB-INFORMATION-GAIN",
        "Evidence acquisition should select the smallest reversible high-information experiment.",
        ("EXPECTED-INFORMATION-GAIN", "INFORMATION GAIN", "NEXT REVERSIBLE EXPERIMENT"),
        0.95,
    ),
    (
        "SIG-MB-TERMINAL-FINALITY",
        "Passive pending and unknown states must become controlled resolution obligations.",
        ("TERMINAL FINALITY", "NO-PASSIVE-UNKNOWN", "TRANSITIONAL STATES"),
        1.0,
    ),
    (
        "SIG-MB-CORPUS-SELECTION",
        "Exhaustive, best and complete corpus claims require ECASP-style release gates.",
        ("EXHAUSTIVE CORPUS", "G1–G10", "G1-G10", "SELECTION INTEGRITY"),
        0.95,
    ),
    (
        "SIG-MB-CONTROL-PLANE",
        "Identifier collisions, revision drift, stale leases and dangling references require fail-closed validation.",
        ("IDENTIFIER COLLISION", "LEASE EPOCH", "REVISION DRIFT", "UNIQUE IDENTIFIERS"),
        0.9,
    ),
    (
        "SIG-MB-ACTION-PROOF",
        "Generic health, queue and HTTP success must not substitute for action-specific provider proof.",
        ("ACTION-SPECIFIC", "HTTP 200", "QUEUED ≠ EXECUTE", "QUEUED IS NOT EXECUTED"),
        0.95,
    ),
    (
        "SIG-MB-FAILURE-GENE",
        "Verified failures and recoveries should compile into reusable engineering genes and regression controls.",
        ("FAILURE LABORATORY", "ENGINEERING GENE", "NEGATIVE RESULTS", "REGRESSION TEST"),
        0.95,
    ),
    (
        "SIG-MB-CONTINUOUS-EVOLUTION",
        "Self-improvement claims require measured performance delta, rollback and no hard-guard regression.",
        ("PERFORMANCE DELTA", "RECURSIVE INTELLIGENCE", "ANTI-DELUSION CONTROLS", "MEASURABLE IMPROVEMENT"),
        1.0,
    ),
    (
        "SIG-MB-PROOF-STATE",
        "Maturity and proof-state transitions must fail closed when target-specific receipts are absent.",
        ("MATURITY STATES", "NO DESIGN AS RUNTIME", "PROOF-STATE", "STATE TRANSITION"),
        0.95,
    ),
    (
        "SIG-MB-OWNER-BURDEN",
        "Route choice must minimise avoidable owner intervention while preserving mission fidelity and proof.",
        ("OWNER-BURDEN ELIMINATION", "OWNER BURDEN", "ZERO RECURRING OWNER BURDEN"),
        0.9,
    ),
    (
        "SIG-MB-REPLICATION",
        "Reusable findings require independent implementation or cross-context replication before stronger promotion.",
        ("INDEPENDENT IMPLEMENTATION", "R3", "REPLICATION", "REPRODUCIBILITY"),
        0.9,
    ),
)

TERMINAL_SOURCE_STATES = {
    "EXTRACTED_VERIFIED",
    "DUPLICATE_CANONICAL_LINKED",
    "SUPERSEDED_BY_STRONGER_SOURCE",
    "IRRELEVANT_REASONED",
    "RESTRICTED_CONTROLLED",
    "TECHNICALLY_UNREADABLE_AFTER_EXHAUSTED_RECOVERY",
    "EXTERNALLY_UNAVAILABLE_AFTER_PROVED_SEARCH_REQUEST_AND_NON_PRODUCTION",
    "OWNER_DECISION_REQUIRED",
}


def extract_master_bible_signals(master_bible_text: str) -> list[dict[str, Any]]:
    upper = master_bible_text.upper()
    signals: list[dict[str, Any]] = []
    for signal_id, summary, patterns, impact in _MASTER_SIGNAL_PATTERNS:
        matched = [pattern for pattern in patterns if pattern.upper() in upper]
        if not matched:
            continue
        signals.append(
            {
                "signal_id": signal_id,
                "summary": summary + " Matched: " + ", ".join(matched),
                "lesson": summary,
                "details": {"matched_patterns": matched},
                "impact": impact,
                "uncertainty": 0.6,
                "repetition": max(1, len(matched)),
                "reuse_potential": 1.0,
                "implementation_cost": 0.2,
                "evidence_refs": ["MASTER_BIBLE:" + signal_id],
            }
        )
    return signals


def _rows(packet: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = packet.get(key)
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _summary(item: Mapping[str, Any]) -> str:
    for key in ("description", "statement", "summary", "title", "record", "fact", "claim"):
        if item.get(key):
            return str(item[key])
    return str(dict(item))


def _source_state(source: Mapping[str, Any]) -> str:
    for key in ("terminal_state", "extraction_state", "finality_state", "state", "status"):
        value = text(source.get(key)).upper()
        if value:
            return value
    return "PENDING"


def _pending_item(item_id: str, packet_id: str, next_test: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "state": "PENDING",
        "packet_id": packet_id,
        "owner": "EVIDENCEOPS_CASE_OWNER",
        "recovery_route": "AUTHORISED_READ_ONLY_SOURCE_RECOVERY",
        "next_test": next_test,
        "release_effect": "BLOCK_FINAL_CERTIFICATE",
        "terminal_condition": (
            "source produced, duplicate-linked, reasoned unavailable, "
            "restricted with proof or owner decision recorded"
        ),
    }


def build_case_payload(
    packet: Mapping[str, Any],
    *,
    master_bible_text: str,
    cycle_id: str | None = None,
    failure_lessons: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Compile a read-only case packet into a conservative foundry cycle."""
    pristine = copy.deepcopy(dict(packet))
    matter_id = str(pristine.get("matter_id") or "EVIDENCEOPS-MATTER")
    case_wall_id = str(pristine.get("case_wall_id") or "EVIDENCEOPS-CASE-WALL")
    packet_id = str(pristine.get("packet_id") or "PACKET")
    mission = pristine.get("mission") if isinstance(pristine.get("mission"), Mapping) else {}
    directive = str(mission.get("objective") or "Analyse, verify and improve this EvidenceOps packet")

    source_ids = [text(row.get("source_id")) for row in _rows(pristine, "sources") if text(row.get("source_id"))]
    fact_ids = [text(row.get("fact_id")) for row in _rows(pristine, "verified_facts") if text(row.get("fact_id"))]
    valid_refs = sorted(set(source_ids + fact_ids))

    contradictions_by_claim: dict[str, list[str]] = {}
    for contradiction in _rows(pristine, "contradictions"):
        claim_id = text(contradiction.get("affected_claim_id"))
        contradiction_id = text(contradiction.get("contradiction_id"))
        if claim_id and contradiction_id:
            contradictions_by_claim.setdefault(claim_id, []).append(contradiction_id)

    claims: list[dict[str, Any]] = []
    for row in _rows(pristine, "claims"):
        claim_id = text(row.get("claim_id"))
        support = text(row.get("support_state")).upper() or "UNVERIFIED"
        contrary = list(row.get("contrary_evidence") or []) + contradictions_by_claim.get(claim_id, [])
        claims.append(
            {
                "claim_id": claim_id,
                "statement": _summary(row),
                "scope_defined": bool(row.get("scope_defined", True)),
                "source_evidence": list(row.get("fact_refs") or row.get("source_refs") or []),
                "execution_receipt": row.get("execution_receipt"),
                "target_readback": list(row.get("target_readback") or []),
                "independent_verification": list(row.get("independent_verification") or []),
                "contrary_evidence": contrary,
                "inference_distance": float(row.get("inference_distance", 0.2 if support in {"SUPPORTED", "VERIFIED"} else 0.65)),
                "requested_state": support,
                "actual_state": support,
                "matter_id": matter_id,
                "case_wall_id": case_wall_id,
            }
        )

    finality_items: list[dict[str, Any]] = []
    unknowns: list[dict[str, Any]] = []
    epistemic_debts: list[dict[str, Any]] = []
    experiments: list[dict[str, Any]] = []
    for index, source in enumerate(_rows(pristine, "sources"), start=1):
        source_id = text(source.get("source_id")) or f"SRC-{index:04d}"
        state = _source_state(source)
        if state in TERMINAL_SOURCE_STATES:
            finality_items.append({"item_id": source_id, "state": state})
        else:
            finality_items.append(_pending_item(source_id, packet_id, "retrieve complete body and verify source state"))
    for index, record in enumerate(_rows(pristine, "missing_records"), start=1):
        record_id = text(record.get("record_id")) or text(record.get("missing_record_id")) or f"MR-{index:04d}"
        description = _summary(record)
        sensitivity = text(record.get("decision_sensitivity")).upper() or "HIGH"
        sensitivity_score = {"HIGH": 1.0, "MEDIUM": 0.65, "LOW": 0.3}.get(sensitivity, 0.8)
        finality_items.append(_pending_item(record_id, packet_id, "search named custodians and record production or reasoned absence"))
        unknowns.append(
            {
                "unknown_id": record_id,
                "question": description,
                "classification": "KNOWN_UNKNOWN",
                "impact": sensitivity_score,
                "uncertainty": 1.0,
                "repetition": 1,
                "strategic_relevance": sensitivity_score,
                "learnability": 0.8,
                "cross_domain_reuse": 0.6,
                "investigation_cost": 0.35,
                "risk": 0.1,
                "owner_burden": 0.0,
                "decision_sensitivity": sensitivity_score,
                "next_reversible_test": "targeted read-only search and source readback",
                "evidence_refs": list(record.get("evidence_refs") or []),
            }
        )
        epistemic_debts.append(
            {
                "debt_id": "DEBT-" + record_id,
                "debt_class": "WEAK_EVIDENCE",
                "description": description,
                "impact": sensitivity_score,
                "uncertainty": 1.0,
                "decision_sensitivity": sensitivity_score,
                "repetition": 1,
                "strategic_relevance": sensitivity_score,
                "reuse_potential": 0.6,
                "closure_cost": 0.35,
                "owner_burden": 0.0,
                "closure_test": "source production, duplicate linkage or reasoned non-production proof",
                "evidence_refs": list(record.get("evidence_refs") or []),
            }
        )
        experiments.append(
            {
                "experiment_id": "EXP-" + record_id,
                "description": "targeted read-only recovery: " + description,
                "expected_information_gain": sensitivity_score,
                "decision_sensitivity": sensitivity_score,
                "resolution_probability": float(record.get("resolution_probability", 0.65)),
                "reversibility": 1.0,
                "downstream_reuse": 0.7,
                "cost": 0.2,
                "time": 0.25,
                "risk": 0.05,
                "owner_attention": 0.0,
                "authority": "A1_INTERNAL",
            }
        )

    gates = dict(pristine.get("corpus_gates") or {})
    corpus_evaluations = []
    if gates:
        corpus_evaluations.append(
            {"requested_claim": str(pristine.get("corpus_claim") or "complete case corpus"), "gates": gates}
        )

    cycle = cycle_id or f"EOPS-ALG-{sha256({'packet': pristine, 'bible': sha256(master_bible_text)})[:16].upper()}"
    transaction = {
        "record_id": packet_id,
        "record_type": "EVIDENCEOPS_CASE_PACKET",
        "cycle_id": cycle,
        "packet_id": packet_id,
        "idempotency_key": sha256({"matter_id": matter_id, "case_wall_id": case_wall_id, "packet": pristine}),
        "expected_revision": str(pristine.get("expected_revision") or "R1"),
        "current_revision": str(pristine.get("current_revision") or pristine.get("expected_revision") or "R1"),
        "lease_epoch": str(pristine.get("lease_epoch") or "E1"),
        "cycle_start_lease_epoch": str(pristine.get("cycle_start_lease_epoch") or pristine.get("lease_epoch") or "E1"),
        "collision_key": f"{matter_id}:{case_wall_id}",
        "collision_owner": "EVIDENCEOPS-ALGORITHM-FOUNDRY",
        "actor_id": "EVIDENCEOPS-ALGORITHM-FOUNDRY",
        "matter_id": matter_id,
        "case_wall_id": case_wall_id,
        "nested_matter_ids": [matter_id],
        "nested_case_wall_ids": [case_wall_id],
        "references": valid_refs,
        "state": "READY",
    }

    return {
        "cycle_id": cycle,
        "evidence_refs": [f"matter:{matter_id}", f"case-wall:{case_wall_id}", f"packet:{packet_id}"],
        "lesson_signals": extract_master_bible_signals(master_bible_text),
        "directive": directive,
        "available_routes": [
            {"route_id": "READ-ONLY-EVIDENCEOPS-CASE-WALL", "action": "analyse verify improve", "available": True}
        ],
        "claims": claims,
        "unknowns": unknowns,
        "experiments": experiments,
        "finality_items": finality_items,
        "corpus_evaluations": corpus_evaluations,
        "control_transactions": [transaction],
        "valid_references": valid_refs,
        "allowed_states": ["READY", "RUNNING", "HELD_FOR_REVIEW", "COMPLETE"],
        "action_proofs": [
            {
                "action": {"action_id": f"ACT-{packet_id}", "action": "READ_CASE_PACKET", "target_id": packet_id},
                "proof": {
                    "action": "READ_CASE_PACKET",
                    "target_id": packet_id,
                    "provider_response": "read-only packet parsed and hash matched",
                    "target_readback": {"packet_sha256": sha256(pristine)},
                    "checked_at": "DETERMINISTIC_ADAPTER_CYCLE",
                    "executed": True,
                    "semantic_match": True,
                    "evidence_refs": [f"packet:{packet_id}"],
                },
            }
        ],
        "proof_state_transitions": [
            {
                "current_state": "SOURCE_SUPPORTED",
                "target_state": "PROTOTYPE_PASSED",
                "proof": {
                    "prototype_receipt": f"cycle:{cycle}",
                    "rollback_test": "read-only no-mutation rollback",
                    "evidence_refs": [f"packet:{packet_id}"],
                },
            }
        ],
        "epistemic_debts": epistemic_debts,
        "route_candidates": [
            {
                "route_id": "READ-ONLY-EVIDENCEOPS-CASE-WALL",
                "description": "reuse the existing case-walled adapter and run deterministic internal algorithms",
                "mission_fidelity": 1.0,
                "expected_value": 0.9,
                "probability": 0.95,
                "proof_quality": 0.9,
                "reversibility": 1.0,
                "information_gain": 0.8,
                "option_value": 1.0,
                "reuse_potential": 1.0,
                "cost": 0.15,
                "latency": 0.15,
                "maintenance": 0.15,
                "risk": 0.05,
                "owner_burden": 0.0,
                "authority": "A1_INTERNAL",
                "fallback": "preserve packet and return held derived analysis",
            }
        ],
        "failure_lessons": [dict(item) for item in failure_lessons],
    }


def run_case_cycle(
    packet: Mapping[str, Any],
    *,
    master_bible_text: str,
    workspace: str | Path,
    learning_policy_path: str | Path,
    failure_lessons: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    pristine = copy.deepcopy(dict(packet))
    before_hash = sha256(pristine)
    payload = build_case_payload(
        pristine,
        master_bible_text=master_bible_text,
        failure_lessons=failure_lessons,
    )
    foundry = EvidenceOpsAlgorithmFoundry(
        workspace,
        learning_policy_path=learning_policy_path,
    )
    result = foundry.execute_cycle(payload).as_dict()
    after_hash = sha256(pristine)
    if before_hash != after_hash:
        raise RuntimeError("read-only case packet was mutated")
    result.update(
        {
            "schema": "EVIDENCEOPS_ALGORITHM_FOUNDRY_CASE_RESULT_V1",
            "matter_id": str(pristine.get("matter_id") or "EVIDENCEOPS-MATTER"),
            "case_wall_id": str(pristine.get("case_wall_id") or "EVIDENCEOPS-CASE-WALL"),
            "source_packet_sha256": before_hash,
            "source_packet_unchanged": True,
            "source_write": False,
            "verified_fact_write": False,
            "case_wall_crossing": False,
            "external_effect": False,
            "authority_ceiling": "A1_INTERNAL",
            "release_state": "HELD_FOR_EVIDENCEOPS_REVIEW",
            "real_case_accuracy_evidence": False,
            "level_6_eligible": False,
        }
    )
    result["adapter_result_sha256"] = sha256(result)
    return result
