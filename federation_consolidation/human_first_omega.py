"""Deterministic Human-First Omega constitutional gate.

This module is deliberately provider-neutral. It decides whether a proposed
operation may continue silently inside the A0/A1 internal envelope or must be
held for human judgment. It does not itself execute provider effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


_AUTHORITY_RANK = {
    "A0_READ_ONLY": 0,
    "A1_INTERNAL": 1,
    "A2_EXTERNAL_REVERSIBLE": 2,
    "A3_CONSEQUENTIAL": 3,
}


@dataclass(frozen=True)
class HumanMissionContract:
    mission_id: str
    owner: str
    intent: str
    success_conditions: tuple[str, ...]
    non_goals: tuple[str, ...] = ()
    authority_ceiling: str = "A1_INTERNAL"
    privacy_level: str = "PRIVATE"
    interruption_budget: int = 1
    cognitive_budget_minutes: int = 10
    reversibility_required: bool = True
    proof_required: bool = True
    stop_conditions: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not self.mission_id.strip():
            errors.append("MISSION_ID_REQUIRED")
        if not self.owner.strip():
            errors.append("OWNER_REQUIRED")
        if not self.intent.strip():
            errors.append("INTENT_REQUIRED")
        if not self.success_conditions:
            errors.append("SUCCESS_CONDITION_REQUIRED")
        if self.authority_ceiling not in _AUTHORITY_RANK:
            errors.append("UNKNOWN_AUTHORITY_CEILING")
        if self.interruption_budget < 0:
            errors.append("INVALID_INTERRUPTION_BUDGET")
        if self.cognitive_budget_minutes < 0:
            errors.append("INVALID_COGNITIVE_BUDGET")
        return tuple(errors)


@dataclass(frozen=True)
class ActionProposal:
    action_id: str
    description: str
    authority_required: str = "A1_INTERNAL"
    external_effect: bool = False
    irreversible: bool = False
    material_objective_change: bool = False
    owner_only_fact_or_value_judgment: bool = False
    privacy_envelope_expansion: bool = False
    consequential: bool = False
    teach_back_required: bool = False
    requested_owner_interrupt: bool = False
    expected_owner_minutes: int = 0
    readback_plan_present: bool = False


@dataclass(frozen=True)
class GateDecision:
    allow: bool
    human_required: bool
    suppress_interrupt: bool
    mode: str
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _rank(authority: str) -> int:
    return _AUTHORITY_RANK.get(authority, 99)


def evaluate(contract: HumanMissionContract, action: ActionProposal) -> GateDecision:
    """Evaluate a proposal against the Human-First constitutional envelope."""

    contract_errors = list(contract.validate())
    if contract_errors:
        return GateDecision(
            allow=False,
            human_required=True,
            suppress_interrupt=False,
            mode="BLOCK_INVALID_HUMAN_MISSION_CONTRACT",
            reasons=tuple(contract_errors),
        )

    reasons: list[str] = []

    if _rank(action.authority_required) > _rank(contract.authority_ceiling):
        reasons.append("AUTHORITY_CEILING_EXCEEDED")
    if action.material_objective_change:
        reasons.append("MATERIAL_OBJECTIVE_CHANGE")
    if action.owner_only_fact_or_value_judgment:
        reasons.append("OWNER_ONLY_FACT_OR_VALUE_JUDGMENT")
    if action.irreversible:
        reasons.append("IRREVERSIBLE_ACTION")
    if action.privacy_envelope_expansion:
        reasons.append("PRIVACY_ENVELOPE_EXPANSION")
    if action.consequential:
        reasons.append("CONSEQUENTIAL_ACTION")
    if action.external_effect:
        reasons.append("EXTERNAL_EFFECT")
        if not action.readback_plan_present:
            reasons.append("READBACK_PLAN_REQUIRED")
    if action.teach_back_required:
        reasons.append("TEACH_BACK_REQUIRED")
    if action.expected_owner_minutes > contract.cognitive_budget_minutes:
        reasons.append("OWNER_COGNITIVE_BUDGET_EXCEEDED")

    if reasons:
        return GateDecision(
            allow=False,
            human_required=True,
            suppress_interrupt=False,
            mode="HOLD_FOR_HUMAN_JUDGMENT",
            reasons=tuple(dict.fromkeys(reasons)),
        )

    suppress_interrupt = action.requested_owner_interrupt
    return GateDecision(
        allow=True,
        human_required=False,
        suppress_interrupt=suppress_interrupt,
        mode="AUTO_CONTINUE_SILENT" if suppress_interrupt else "AUTO_CONTINUE",
        reasons=("SAFE_WITHIN_HUMAN_MISSION_CONTRACT",),
    )


def human_value_score(
    *,
    mission_progress: float,
    outcome_quality: float,
    option_preservation: float,
    comprehension: float,
    proof_confidence: float,
    avoided_work: float,
    avoided_surprise: float,
    owner_minutes: float,
    debug_minutes: float,
    unnecessary_interruptions: float,
    financial_cost: float,
    privacy_exposure: float,
    irreversibility: float,
) -> float:
    """Return a transparent, bounded human-value score in the range [-100, 100]."""

    upside = sum(
        (
            mission_progress,
            outcome_quality,
            option_preservation,
            comprehension,
            proof_confidence,
            avoided_work,
            avoided_surprise,
        )
    )
    downside = sum(
        (
            owner_minutes,
            debug_minutes,
            unnecessary_interruptions,
            financial_cost,
            privacy_exposure,
            irreversibility,
        )
    )
    raw = upside - downside
    return max(-100.0, min(100.0, round(raw, 4)))


def batch_requires_human(
    contract: HumanMissionContract, actions: Iterable[ActionProposal]
) -> tuple[ActionProposal, ...]:
    """Return only proposals that genuinely require human judgment.

    This supports decision bundling: safe operations continue without creating
    approval fatigue, while owner-reserved decisions can be surfaced together.
    """

    return tuple(action for action in actions if evaluate(contract, action).human_required)
