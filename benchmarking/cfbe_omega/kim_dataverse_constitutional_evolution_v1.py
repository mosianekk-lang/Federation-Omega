from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Sequence


class AmendmentState(str, Enum):
    PROPOSED = "PROPOSED"
    HELD = "HELD"
    SHADOW_CANDIDATE = "SHADOW_CANDIDATE"
    OWNER_REVIEW_REQUIRED = "OWNER_REVIEW_REQUIRED"


@dataclass(frozen=True)
class ConstitutionalAmendment:
    amendment_id: str
    changes_owner_authority: bool
    changes_external_effect_policy: bool
    changes_proof_floor: bool
    changes_owner_intent: bool
    reversible: bool
    historical_replay_passed: bool
    adversarial_passed: bool
    rollback_verified: bool
    shadow_observed: bool
    independent_proof_refs: tuple[str, ...]
    measured_gain: float | None = None


@dataclass(frozen=True)
class AmendmentDecision:
    state: AmendmentState
    eligible_for_shadow: bool
    owner_review_required: bool
    self_promoted: bool
    reasons: tuple[str, ...]
    receipt: str


def evaluate_amendment(amendment: ConstitutionalAmendment) -> AmendmentDecision:
    if not amendment.amendment_id.strip():
        raise ValueError("amendment_id is required")
    reasons: list[str] = []
    owner_review = amendment.changes_owner_authority or amendment.changes_owner_intent
    if amendment.changes_proof_floor:
        reasons.append("PROOF_FLOOR_CHANGE_REQUIRES_OWNER_REVIEW")
        owner_review = True
    if amendment.changes_external_effect_policy:
        reasons.append("EXTERNAL_EFFECT_POLICY_CHANGE_REQUIRES_OWNER_REVIEW")
        owner_review = True
    if not amendment.reversible:
        reasons.append("IRREVERSIBLE_CHANGE")
        owner_review = True
    if not amendment.historical_replay_passed:
        reasons.append("HISTORICAL_REPLAY_REQUIRED")
    if not amendment.adversarial_passed:
        reasons.append("ADVERSARIAL_COURT_REQUIRED")
    if not amendment.rollback_verified:
        reasons.append("ROLLBACK_REQUIRED")
    if not amendment.independent_proof_refs:
        reasons.append("INDEPENDENT_PROOF_REQUIRED")
    if amendment.measured_gain is not None and amendment.measured_gain <= 0:
        reasons.append("NO_MEASURED_GAIN")

    eligible_for_shadow = (
        not owner_review
        and amendment.reversible
        and amendment.historical_replay_passed
        and amendment.adversarial_passed
        and amendment.rollback_verified
        and bool(amendment.independent_proof_refs)
        and (amendment.measured_gain is None or amendment.measured_gain > 0)
    )

    if owner_review:
        state = AmendmentState.OWNER_REVIEW_REQUIRED
    elif eligible_for_shadow:
        state = AmendmentState.SHADOW_CANDIDATE
    else:
        state = AmendmentState.HELD

    payload = {
        "amendment_id": amendment.amendment_id,
        "state": state.value,
        "eligible_for_shadow": eligible_for_shadow,
        "owner_review_required": owner_review,
        "self_promoted": False,
        "reasons": sorted(reasons),
        "external_effect_authorized": False,
        "authority_inherited": False,
    }
    receipt = "sha256:" + sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AmendmentDecision(
        state=state,
        eligible_for_shadow=eligible_for_shadow,
        owner_review_required=owner_review,
        self_promoted=False,
        reasons=tuple(sorted(reasons)),
        receipt=receipt,
    )


class CapabilityMarketAction(str, Enum):
    RETAIN = "RETAIN"
    CHALLENGE = "CHALLENGE"
    MERGE_REVIEW = "MERGE_REVIEW"
    RETIRE_REVIEW = "RETIRE_REVIEW"


@dataclass(frozen=True)
class CapabilityFitness:
    capability_id: str
    quality: float
    reliability: float
    evidence_strength: float
    reuse_count: int
    owner_burden: float
    maintenance_cost: float
    overlap_score: float = 0.0


@dataclass(frozen=True)
class CapabilityMarketDecision:
    capability_id: str
    score: float
    action: CapabilityMarketAction
    destructive_action_authorized: bool = False


def capability_market(fitness: Sequence[CapabilityFitness]) -> tuple[CapabilityMarketDecision, ...]:
    ids = [item.capability_id for item in fitness]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate capability_id")
    decisions = []
    for item in fitness:
        for value in (item.quality, item.reliability, item.evidence_strength, item.overlap_score):
            if not 0.0 <= value <= 1.0:
                raise ValueError("bounded fitness values must be within [0,1]")
        if item.reuse_count < 0 or item.owner_burden < 0 or item.maintenance_cost < 0:
            raise ValueError("fitness costs/counts must be non-negative")
        score = (
            item.quality * 0.25
            + item.reliability * 0.25
            + item.evidence_strength * 0.20
            + min(item.reuse_count / 10.0, 1.0) * 0.15
            - min(item.owner_burden / 60.0, 1.0) * 0.075
            - min(item.maintenance_cost / 100.0, 1.0) * 0.075
        )
        if item.overlap_score >= 0.9:
            action = CapabilityMarketAction.MERGE_REVIEW
        elif score < 0.25 and item.reuse_count == 0:
            action = CapabilityMarketAction.RETIRE_REVIEW
        elif score < 0.55:
            action = CapabilityMarketAction.CHALLENGE
        else:
            action = CapabilityMarketAction.RETAIN
        decisions.append(
            CapabilityMarketDecision(
                capability_id=item.capability_id,
                score=round(score, 6),
                action=action,
                destructive_action_authorized=False,
            )
        )
    return tuple(sorted(decisions, key=lambda item: (-item.score, item.capability_id)))
