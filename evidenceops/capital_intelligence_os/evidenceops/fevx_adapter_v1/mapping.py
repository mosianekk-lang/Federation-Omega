from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .core import digest


def _patch_known_keys(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {
            key: copy.deepcopy(replacements[key])
            if key in replacements
            else _patch_known_keys(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_patch_known_keys(item, replacements) for item in value]
    return copy.deepcopy(value)


def build_base_inputs(
    packet: dict[str, Any], repo_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    mission_template = repo_root / "systems/fevx-cse-runtime/mission.json"
    genome_template = repo_root / "systems/fevx-cse-runtime/intent_genome.json"
    if not mission_template.is_file() or not genome_template.is_file():
        raise FileNotFoundError("verified CSE v1 mission or genome template is absent")

    mission = json.loads(mission_template.read_text(encoding="utf-8"))
    genome = json.loads(genome_template.read_text(encoding="utf-8"))
    objective = packet["mission"]["objective"]
    requested_outcome = packet["mission"]["requested_outcome"]
    replacements = {
        "mission_id": packet["packet_id"],
        "objective": objective,
        "requested_outcome": requested_outcome,
        "intended_outcome": requested_outcome,
        "ultimate_outcome": requested_outcome,
        "owner": "Kagiso Kim Mosiane",
    }
    mission = _patch_known_keys(mission, replacements)
    genome = _patch_known_keys(genome, replacements)

    mission["evidenceops_context"] = {
        "packet_id": packet["packet_id"],
        "matter_id": packet["matter_id"],
        "case_wall_id": packet["case_wall_id"],
        "objective": objective,
        "requested_outcome": requested_outcome,
        "source_ids": [row["source_id"] for row in packet["sources"]],
        "fact_ids": [row["fact_id"] for row in packet["verified_facts"]],
        "claim_ids": [row["claim_id"] for row in packet["claims"]],
        "missing_record_ids": [
            row.get("record_id", f"MISSING-{index + 1}")
            for index, row in enumerate(packet["missing_records"])
        ],
        "packet_sha256": digest(packet),
        "external_effect": False,
        "verified_fact_write": False,
    }
    genome["evidenceops_constraints"] = {
        "read_only": True,
        "case_wall_id": packet["case_wall_id"],
        "external_effect": False,
        "verified_fact_write": False,
        "source_mutation": False,
    }
    return mission, genome


def build_frontier_context(packet: dict[str, Any]) -> dict[str, Any]:
    claims = packet["claims"]
    supported_claims = {
        row["claim_id"] for row in claims if row.get("support_state") == "SUPPORTED"
    }
    assumptions = [
        {"item": row["claim_id"], "tested": False, "statement": row["statement"]}
        for row in claims
        if row.get("support_state") in {"UNVERIFIED", "PARTIALLY_SUPPORTED"}
    ]
    expected_variables = [
        row.get("record_id", f"MISSING-{index + 1}")
        for index, row in enumerate(packet["missing_records"])
    ]
    observed_variables = [row["fact_id"] for row in packet["verified_facts"]]
    expected_stakeholders = [row["stakeholder_id"] for row in packet["stakeholders"]]
    represented_stakeholders = [
        row["stakeholder_id"]
        for row in packet["stakeholders"]
        if row.get("represented_by_evidence", False)
    ]
    actors = [
        {
            "id": row["stakeholder_id"],
            "influence": row.get("influence", 0.5),
            "alignment": row.get("alignment", 0.0),
            "constraint": row.get("constraint", 0.0),
        }
        for row in packet["stakeholders"]
    ]
    causal_edges = [
        {
            "cause": row.get("possible_cause", row.get("contradiction_id", "UNKNOWN")),
            "effect": row.get("affected_claim_id", "case_confidence"),
            "strength": row.get("strength", -0.3),
            "confidence": row.get("confidence", 0.5),
        }
        for row in packet["contradictions"]
    ] or [
        {
            "cause": "missing_evidence",
            "effect": "case_confidence",
            "strength": -0.5,
            "confidence": 0.8,
        }
    ]
    routes = [
        {
            "id": row["strategy_id"],
            "value": row.get("value", 0.5),
            "probability": row.get("probability", 0.5),
            "option_value": row.get("option_value", 0.2),
            "information_gain": row.get("information_gain", 0.2),
            "cost": row.get("cost", 0.1),
            "risk": row.get("risk", 0.1),
            "owner_attention": row.get("owner_attention", 0.1),
            "reversibility": row.get("reversibility", 0.8),
        }
        for row in packet["strategies"]
    ]
    deliberation = [
        {
            "position": route["id"],
            "assumptions": [f"ASSUMPTION-{index + 1}"],
            "reputation": 0.7 - index * 0.05,
            "confidence": route["probability"],
            "probability": route["probability"],
        }
        for index, route in enumerate(routes)
    ]
    while len(deliberation) < 3:
        index = len(deliberation)
        deliberation.append(
            {
                "position": f"INDEPENDENT-{index + 1}",
                "assumptions": [f"INDEPENDENT-ASSUMPTION-{index + 1}"],
                "reputation": 0.55,
                "confidence": 0.5,
                "probability": 0.5,
            }
        )
    outcome_values = {
        row.get("step_id", f"OUT-{index + 1}"): 1.0 if row.get("verified") else 0.0
        for index, row in enumerate(packet["outcome_chain"])
    }
    selected_route = routes[0]["id"] if routes else "HOLD"
    alternatives = [
        {
            "id": row["id"],
            "expected_value": row["value"] * row["probability"],
            "feasible_at_time": True,
        }
        for row in routes
    ]
    memory_events = [
        {
            "signature": "EVIDENCEOPS_SOURCE_AS_COMPLETION",
            "kind": "BOUNDARY",
            "outcome": "FAILURE",
            "lesson": "Source existence is not proof of requested outcome.",
            "repair": "REQUIRE_TARGET_READBACK",
            "reliable": True,
        },
        {
            "signature": "EVIDENCEOPS_SOURCE_AS_COMPLETION",
            "kind": "BOUNDARY",
            "outcome": "FAILURE",
            "lesson": "Artifact creation must remain distinct from fulfilment.",
            "repair": "REQUIRE_PRAXIS_OUTCOME_CHAIN",
            "reliable": True,
        },
    ]
    present_organs = [
        "evidence_intake", "verified_fact_register", "chronology",
        "contradiction_register",
    ]
    required_organs = [*present_organs, "case_intelligence_adapter"]
    return {
        "claims": [row["claim_id"] for row in claims],
        "evidence": sorted(supported_claims),
        "assumptions": assumptions,
        "expected_variables": expected_variables,
        "observed_variables": observed_variables,
        "expected_stakeholders": expected_stakeholders,
        "represented_stakeholders": represented_stakeholders,
        "low_value_gaps": [],
        "task_type": "EVIDENCEOPS_CASE_INTELLIGENCE",
        "competence_history": [
            {
                "task_type": "EVIDENCEOPS_CASE_INTELLIGENCE",
                "success": True,
                "calibration": 0.7,
                "failure_mode": "",
            },
            {
                "task_type": "EVIDENCEOPS_CASE_INTELLIGENCE",
                "success": False,
                "calibration": 0.45,
                "failure_mode": "MISSING_PRIMARY_EVIDENCE",
            },
        ],
        "missing_inputs": expected_variables,
        "distribution_shift": 0.1,
        "memory_events": memory_events,
        "mission_genome": {
            "required_organs": required_organs,
            "optional_organs": ["settlement_simulator", "public_release"],
            "signal_to_organ": {
                "case_intelligence_required": "case_intelligence_adapter"
            },
        },
        "present_organs": present_organs,
        "unhealthy_organs": [],
        "used_organs": present_organs,
        "environment_signals": ["case_intelligence_required"],
        "actors": actors,
        "institutional_intervention": {
            "alignment_delta": {
                row["stakeholder_id"]: row.get("intervention_alignment_delta", 0.0)
                for row in packet["stakeholders"]
            }
        },
        "causal_edges": causal_edges,
        "world_intervention": {"target": causal_edges[0]["cause"], "magnitude": 0.5},
        "world_target_metric": "case_confidence",
        "world_baseline": 0.5,
        "unresolved_confounders": expected_variables,
        "strategy_routes": routes,
        "deliberation_proposals": deliberation,
        "decision_passport": {
            "selected_route": selected_route,
            "alternatives": alternatives,
        },
        "observed_outcome_value": sum(outcome_values.values()) / max(1, len(outcome_values)),
        "decision_steps": [
            {"id": key, "baseline": 0.0, "observed_after": value}
            for key, value in outcome_values.items()
        ],
        "human_capability": {"legal_values": 0.9, "analysis": 0.7, "general": 0.7},
        "machine_capability": {"legal_values": 0.3, "analysis": 0.75, "general": 0.65},
        "joint_task": {
            "type": "legal_values",
            "values_sensitive": True,
            "learning_objective": "IMPROVE_EVIDENCE_LINKED_OWNER_DECISION_QUALITY",
        },
        "case_wall_id": packet["case_wall_id"],
        "matter_id": packet["matter_id"],
        "external_effect": False,
    }
