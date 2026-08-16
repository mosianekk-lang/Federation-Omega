from __future__ import annotations

from dataclasses import asdict
import re
from typing import Mapping

from ao_harmonic_v3 import AOHarmonicV3, CostClass, WorkloadCostProfile
from ao_harmonic_v3.forest_omega import ForestOmegaContext


EVENT_SCHEMA = "BUBBLES-FOREST-BACKGROUND-EVENT-V1"
RECEIPT_SCHEMA = "BUBBLES-FOREST-BACKGROUND-RECEIPT-V1"

_ALLOWED_FIELDS = frozenset({
    "schema",
    "event_id",
    "source_class",
    "event_class",
    "fingerprint_sha256",
    "matter_class",
    "materiality",
    "consequence",
    "uncertainty",
    "dependency_density",
    "adversarial_complexity",
    "deadline_risk",
    "evidence_risk",
    "owner_only",
    "provider_readback_missing",
    "route_failure",
    "objective_exhausted",
    "material_strategy_change",
    "private_content_included",
})

_SOURCE_CLASSES = frozenset({
    "GMAIL_METADATA",
    "DRIVE_METADATA",
    "FEDERATION_STATE",
    "PROVIDER_HEALTH",
    "DEADLINE_SIGNAL",
    "SYSTEM_EVENT",
})

_EVENT_CLASSES = frozenset({
    "NEW_ITEM",
    "STATE_CHANGE",
    "DEADLINE_CHANGE",
    "EVIDENCE_CHANGE",
    "PROVIDER_CHANGE",
    "FAILURE",
    "RECOVERY",
    "NO_MATERIAL_CHANGE",
})

_MATTER_CLASSES = frozenset({"LEGAL", "EVIDENCE", "SYSTEM", "PLATFORM", "GENERAL"})
_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class BackgroundEventError(ValueError):
    pass


def _bounded_score(event: Mapping[str, object], key: str, default: float) -> float:
    raw = event.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise BackgroundEventError(f"{key} must be a number between 0 and 1")
    score = float(raw)
    if not 0.0 <= score <= 1.0:
        raise BackgroundEventError(f"{key} must be between 0 and 1")
    return score


def _flag(event: Mapping[str, object], key: str, default: bool = False) -> bool:
    value = event.get(key, default)
    if not isinstance(value, bool):
        raise BackgroundEventError(f"{key} must be boolean")
    return value


def validate_event(raw: Mapping[str, object]) -> dict[str, object]:
    unknown = sorted(set(raw).difference(_ALLOWED_FIELDS))
    if unknown:
        raise BackgroundEventError(
            "Sanitized event contains unsupported fields: " + ", ".join(unknown)
        )
    if raw.get("schema") != EVENT_SCHEMA:
        raise BackgroundEventError(f"Unsupported background event schema: {raw.get('schema')!r}")
    if _flag(raw, "private_content_included", False):
        raise BackgroundEventError("Private message/document content is prohibited in the public background event envelope")

    event_id = str(raw.get("event_id", ""))
    if not _ID_RE.fullmatch(event_id):
        raise BackgroundEventError("event_id must be a short opaque identifier")

    fingerprint = str(raw.get("fingerprint_sha256", "")).lower()
    if not _SHA_RE.fullmatch(fingerprint):
        raise BackgroundEventError("fingerprint_sha256 must be a lowercase SHA-256 digest")

    source_class = str(raw.get("source_class", ""))
    event_class = str(raw.get("event_class", ""))
    matter_class = str(raw.get("matter_class", "GENERAL"))
    if source_class not in _SOURCE_CLASSES:
        raise BackgroundEventError(f"Unsupported source_class: {source_class!r}")
    if event_class not in _EVENT_CLASSES:
        raise BackgroundEventError(f"Unsupported event_class: {event_class!r}")
    if matter_class not in _MATTER_CLASSES:
        raise BackgroundEventError(f"Unsupported matter_class: {matter_class!r}")

    return {
        "schema": EVENT_SCHEMA,
        "event_id": event_id,
        "source_class": source_class,
        "event_class": event_class,
        "fingerprint_sha256": fingerprint,
        "matter_class": matter_class,
        "materiality": _bounded_score(raw, "materiality", 0.5),
        "consequence": _bounded_score(raw, "consequence", 0.5),
        "uncertainty": _bounded_score(raw, "uncertainty", 0.5),
        "dependency_density": _bounded_score(raw, "dependency_density", 0.5),
        "adversarial_complexity": _bounded_score(raw, "adversarial_complexity", 0.5),
        "deadline_risk": _flag(raw, "deadline_risk"),
        "evidence_risk": _flag(raw, "evidence_risk"),
        "owner_only": _flag(raw, "owner_only"),
        "provider_readback_missing": _flag(raw, "provider_readback_missing"),
        "route_failure": _flag(raw, "route_failure"),
        "objective_exhausted": _flag(raw, "objective_exhausted"),
        "material_strategy_change": _flag(raw, "material_strategy_change"),
        "private_content_included": False,
    }


def run_background_event(raw: Mapping[str, object]) -> dict[str, object]:
    event = validate_event(raw)
    runtime = AOHarmonicV3()

    cost_decision = runtime.cost.evaluate(WorkloadCostProfile(
        workload_id="BUBBLES_FOREST_BACKGROUND_EVENT",
        cost_class=CostClass.C0_INCLUDED_FREE,
        estimated_monthly_cost=0.0,
        already_paid_or_included=True,
        event_driven=True,
        scale_to_zero=True,
        hard_cap_or_quota_available=False,
        essential=bool(event["deadline_risk"] or event["evidence_risk"]),
        owner_approved=False,
        cheaper_route_available=False,
        notes="Public standard GitHub-hosted runner; sanitized event envelope only.",
    ))

    high_stakes = bool(
        event["matter_class"] == "LEGAL"
        or event["materiality"] >= 0.70
        or event["deadline_risk"]
        or event["evidence_risk"]
    )
    route_alternatives = (
        {
            "route_id": "PRIVATE_REASONING_WAKE",
            "route_type": "WAKE_PRIVATE_REASONING",
            "available": True,
            "authorised": True,
            "feasibility": 0.95,
            "proof_strength": 0.85,
            "reversibility": 1.0,
            "speed": 0.85,
            "strategic_value": 0.95 if high_stakes else 0.55,
            "owner_burden": 0.20,
            "privacy_cost": 0.05,
            "maintenance_cost": 0.05,
            "information_gain": 0.90,
        },
        {
            "route_id": "DEFER_UNTIL_MATERIAL_DELTA",
            "route_type": "DEFER",
            "available": not high_stakes,
            "authorised": True,
            "feasibility": 1.0,
            "proof_strength": 0.70,
            "reversibility": 1.0,
            "speed": 1.0,
            "strategic_value": 0.80 if not high_stakes else 0.10,
            "owner_burden": 0.0,
            "privacy_cost": 0.0,
            "maintenance_cost": 0.0,
            "information_gain": 0.20,
        },
    )

    forest = runtime.forest.run(ForestOmegaContext(
        matter_id=f"PRIVATE_{event['matter_class']}_MATTER",
        objective="Classify a sanitized state-change signal and protect the objective without exposing private content",
        desired_outcome="Wake private reasoning only when the signal is materially decision-changing or owner-only",
        high_stakes=high_stakes,
        consequential_action_planned=False,
        consequence=float(event["consequence"]),
        uncertainty=float(event["uncertainty"]),
        dependency_density=float(event["dependency_density"]),
        adversarial_complexity=float(event["adversarial_complexity"]),
        root_hypotheses=(
            "The sanitized event may represent a material change requiring private-context recomputation",
            "The event may be non-material and should not interrupt the owner",
        ),
        tree_facts=(
            f"source_class={event['source_class']}",
            f"event_class={event['event_class']}",
            f"materiality_band={'HIGH' if event['materiality'] >= 0.70 else 'LOW_OR_MODERATE'}",
        ),
        evidence_dependencies=("PRIVATE_PROVIDER_READBACK",) if event["provider_readback_missing"] else (),
        cross_lane_risks=("DEADLINE",) if event["deadline_risk"] else (),
        route_alternatives=route_alternatives,
        credible_risk_signal_present=bool(event["materiality"] >= 0.70 or event["deadline_risk"] or event["evidence_risk"]),
        provider_readback_required_but_missing=bool(event["provider_readback_missing"]),
        route_failure_detected=bool(event["route_failure"]),
        objective_exhausted=bool(event["objective_exhausted"]),
        owner_only_dependency=bool(event["owner_only"]),
        material_strategy_change=bool(event["material_strategy_change"]),
        trigger_refs=(event["fingerprint_sha256"],),
    ))

    owner_wake = bool(
        event["owner_only"]
        or event["deadline_risk"]
        or event["material_strategy_change"]
        or event["objective_exhausted"]
        or event["materiality"] >= 0.85
    )
    private_reasoning_wake = bool(
        owner_wake
        or event["evidence_risk"]
        or event["materiality"] >= 0.70
        or event["provider_readback_missing"]
    )

    return {
        "schema": RECEIPT_SCHEMA,
        "state": "SUCCESS",
        "event": event,
        "cost": asdict(cost_decision),
        "forest": {
            "engine_id": forest.engine_id,
            "architecture_cycle": list(forest.architecture_cycle),
            "adaptive_horizon_depth": forest.horizon["adaptive_depth"],
            "selected_path": forest.decision["selected_path"],
            "route_recovery": forest.route_recovery,
            "truth_class": forest.truth_class,
        },
        "private_reasoning_wake_required": private_reasoning_wake,
        "owner_wake_required": owner_wake,
        "external_effect": False,
        "authority_ceiling": "A1_INTERNAL",
        "truth_boundary": (
            "This receipt processes sanitized metadata/control signals only. It contains no private message or document body, "
            "performs no provider mutation, does not establish a legal fact, and does not replace private evidence review."
        ),
    }


__all__ = [
    "BackgroundEventError",
    "EVENT_SCHEMA",
    "RECEIPT_SCHEMA",
    "run_background_event",
    "validate_event",
]
