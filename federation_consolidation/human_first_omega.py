"""Deterministic Human-First Omega constitutional gate.

This module is deliberately provider-neutral. It decides whether a proposed
operation may continue silently inside the Human Mission Contract or must be
held for human judgment. It does not itself execute provider effects or mint
provider authority.
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
    authorized_external_effect_classes: tuple[str, ...] = ()
    authorization_refs: tuple[str, ...] = ()

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
        if any(not item.strip() for item in self.authorized_external_effect_classes):
            errors.append("INVALID_AUTHORIZED_EFFECT_CLASS")
        if any(not item.strip() for item in self.authorization_refs):
            errors.append("INVALID_AUTHORIZATION_REF")
        return tuple(errors)


@dataclass(frozen=True)
class ActionProposal:
    action_id: str
    description: str
    authority_required: str = "A1_INTERNAL"
    external_effect: bool = False
    effect_class: str = "NONE"
    authorization_ref: str | None = None
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


@dataclass(frozen=True)
class RecoveryState:
    """State for the Solve-Before-Report / Outcome-First escalation policy."""

    issue_id: str
    issue_summary: str
    resolved: bool = False
    verified: bool = False
    solution_summary: str = ""
    attempts: tuple[str, ...] = ()
    exact_blocker: str = ""
    best_next_route: str = ""
    residual_risk: str = ""
    material_residual_risk: bool = False
    recovery_exhausted: bool = False
    owner_decision_required: bool = False
    owner_decision_request: str = ""
    authority_expansion_required: bool = False
    privacy_expansion_required: bool = False
    irreversible_action_required: bool = False
    objective_conflict: bool = False


@dataclass(frozen=True)
class OutcomeFirstDecision:
    owner_visible: bool
    human_required: bool
    continue_recovery: bool
    report_mode: str
    headline: str
    details: tuple[str, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _rank(authority: str) -> int:
    return _AUTHORITY_RANK.get(authority, 99)


def _external_effect_is_preauthorized(
    contract: HumanMissionContract, action: ActionProposal
) -> bool:
    """Return true only for an explicitly scoped owner-authorized effect.

    The action cannot self-mint authority: both its effect class and its
    authorization reference must already exist in the Human Mission Contract.
    """

    if not action.external_effect:
        return False
    if not action.effect_class or action.effect_class == "NONE":
        return False
    if not action.authorization_ref:
        return False
    return (
        action.effect_class in contract.authorized_external_effect_classes
        and action.authorization_ref in contract.authorization_refs
    )


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
        if not _external_effect_is_preauthorized(contract, action):
            reasons.append("EXTERNAL_EFFECT_REQUIRES_OWNER_AUTHORIZATION")
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


def outcome_first_decision(state: RecoveryState) -> OutcomeFirstDecision:
    """Apply the Solve-Before-Report / Outcome-First escalation invariant.

    Recoverable problems remain inside the system until a solution is verified
    or a genuine owner-reserved escalation condition exists. Material risk is
    never hidden, and an unverified repair is never reported as complete.
    """

    escalation_reasons: list[str] = []
    if state.owner_decision_required:
        escalation_reasons.append("OWNER_DECISION_REQUIRED")
    if state.authority_expansion_required:
        escalation_reasons.append("AUTHORITY_EXPANSION_REQUIRED")
    if state.privacy_expansion_required:
        escalation_reasons.append("PRIVACY_EXPANSION_REQUIRED")
    if state.irreversible_action_required:
        escalation_reasons.append("IRREVERSIBLE_ACTION_REQUIRED")
    if state.objective_conflict:
        escalation_reasons.append("OBJECTIVE_CONFLICT")
    if state.material_residual_risk:
        escalation_reasons.append("MATERIAL_RESIDUAL_RISK")
    if state.recovery_exhausted:
        escalation_reasons.append("RECOVERY_EXHAUSTED")

    if state.resolved and state.verified:
        details: list[str] = []
        if state.solution_summary:
            details.append(f"Solution: {state.solution_summary}")
        if state.residual_risk:
            details.append(f"Residual risk: {state.residual_risk}")
        if escalation_reasons:
            if state.owner_decision_request:
                details.append(f"Owner decision: {state.owner_decision_request}")
            return OutcomeFirstDecision(
                owner_visible=True,
                human_required=True,
                continue_recovery=False,
                report_mode="REPORT_OUTCOME_WITH_MATERIAL_ESCALATION",
                headline=f"Resolved with residual decision: {state.issue_id}",
                details=tuple(details),
                reasons=tuple(escalation_reasons),
            )
        return OutcomeFirstDecision(
            owner_visible=True,
            human_required=False,
            continue_recovery=False,
            report_mode="REPORT_VERIFIED_SOLUTION_OUTCOME",
            headline=f"Resolved: {state.issue_id}",
            details=tuple(details),
            reasons=("VERIFIED_SOLUTION",),
        )

    if not escalation_reasons:
        return OutcomeFirstDecision(
            owner_visible=False,
            human_required=False,
            continue_recovery=True,
            report_mode="CONTINUE_RECOVERY_SILENT",
            headline="",
            details=(),
            reasons=("UNRESOLVED_BUT_RECOVERABLE", "OWNER_INTERRUPTION_SUPPRESSED"),
        )

    details: list[str] = []
    if state.solution_summary:
        details.append(f"Best current outcome: {state.solution_summary}")
    if state.attempts:
        details.append(f"Repairs attempted: {'; '.join(state.attempts)}")
    if state.exact_blocker:
        details.append(f"Remaining blocker: {state.exact_blocker}")
    if state.best_next_route:
        details.append(f"Best next route: {state.best_next_route}")
    if state.owner_decision_request:
        details.append(f"Owner decision: {state.owner_decision_request}")
    if state.residual_risk:
        details.append(f"Residual risk: {state.residual_risk}")

    return OutcomeFirstDecision(
        owner_visible=True,
        human_required=True,
        continue_recovery=False,
        report_mode="ESCALATE_PRECISE_UNRESOLVED_DECISION",
        headline=f"Resolution needs owner decision: {state.issue_id}",
        details=tuple(details),
        reasons=tuple(escalation_reasons),
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

    This supports decision bundling: safe and explicitly pre-authorized
    reversible operations can continue without approval fatigue, while genuine
    owner-reserved decisions surface together.
    """

    return tuple(action for action in actions if evaluate(contract, action).human_required)
