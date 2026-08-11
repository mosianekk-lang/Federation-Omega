"""JFRIE v1.1 regression layer.

Adds deterministic protections learned from referral-autopsy failures without
embedding private case facts in the public repository.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Sequence

from .jfrie import Decision, Evaluation, GateResult, GateState, ReferralInput, evaluate


@dataclass(frozen=True)
class AuditSignals:
    """Signals that test how an originating legal instrument was built and later used."""

    originating_instrument_verified: bool = True
    derivative_summary_conflicts: Sequence[str] = field(default_factory=tuple)
    administrative_processing_used_as_jurisdiction: bool = False
    closed_list_category_required: bool = False
    closed_list_category_explicit: bool = True
    dispute_date_basis: Optional[str] = None
    direct_agreement_enforcement: bool = False
    agreement_fact_refs: Sequence[str] = field(default_factory=tuple)
    agreement_authority_refs: Sequence[str] = field(default_factory=tuple)
    certificate_or_ruling_used_as_merits_proof: bool = False
    remedy_matches_cause: bool = True
    mixed_lane_authority: Mapping[str, str] = field(default_factory=dict)
    secondary_questionnaire_flags: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class V11Evaluation:
    base: Evaluation
    regression_gates: Sequence[GateResult]
    decision: Decision
    release_blocked: bool


def _result(name: str, hard: bool, state: GateState, reason: str) -> GateResult:
    return GateResult(name, hard, state, reason)


def evaluate_v11(referral: ReferralInput, signals: AuditSignals) -> V11Evaluation:
    """Run JFRIE v1.0 plus v1.1 referral-autopsy regression gates."""

    base = evaluate(referral)
    gates: list[GateResult] = []

    if signals.derivative_summary_conflicts:
        if signals.originating_instrument_verified:
            gates.append(_result(
                "original_form_overrides_derivative_summary",
                False,
                GateState.WARN,
                "Derivative summary conflict detected; verified originating instrument controls: "
                + "; ".join(signals.derivative_summary_conflicts),
            ))
        else:
            gates.append(_result(
                "original_form_overrides_derivative_summary",
                True,
                GateState.FAIL,
                "Derivative summaries conflict but the originating instrument has not been verified.",
            ))
    else:
        gates.append(_result(
            "original_form_overrides_derivative_summary",
            True,
            GateState.PASS if signals.originating_instrument_verified else GateState.FAIL,
            "Originating instrument verified." if signals.originating_instrument_verified
            else "Originating instrument not verified; derivative summaries may not substitute for it.",
        ))

    gates.append(_result(
        "administrative_processing_is_not_jurisdiction",
        True,
        GateState.FAIL if signals.administrative_processing_used_as_jurisdiction else GateState.PASS,
        "Administrative acceptance, registration, set-down or processing is not being used as proof of jurisdiction."
        if not signals.administrative_processing_used_as_jurisdiction
        else "Administrative acceptance/processing/set-down is being used as proof that jurisdiction exists. That inference is prohibited.",
    ))

    subtype_ok = (not signals.closed_list_category_required) or signals.closed_list_category_explicit
    gates.append(_result(
        "closed_list_statutory_subtype",
        True,
        GateState.PASS if subtype_ok else GateState.FAIL,
        "Required statutory subtype is explicit." if subtype_ok
        else "A closed-list statutory route is invoked but the originating theory leaves the statutory subtype implicit.",
    ))

    date_ok = bool(signals.dispute_date_basis and signals.dispute_date_basis.strip())
    gates.append(_result(
        "reasoned_dispute_date_basis",
        True,
        GateState.PASS if date_ok else GateState.FAIL,
        "Dispute date has a stated factual/legal basis." if date_ok
        else "A dispute date is asserted without a stated factual/legal accrual basis.",
    ))

    if signals.direct_agreement_enforcement:
        agreement_ok = bool(signals.agreement_fact_refs) and bool(signals.agreement_authority_refs)
        gates.append(_result(
            "agreement_and_authority_for_direct_enforcement",
            True,
            GateState.PASS if agreement_ok else GateState.FAIL,
            "Direct-enforcement theory has agreement and authority proof references." if agreement_ok
            else "Direct implementation/enforcement is sought without both agreement proof and authority/enforceability proof.",
        ))
    else:
        gates.append(_result(
            "agreement_and_authority_for_direct_enforcement",
            True,
            GateState.PASS,
            "No direct agreement-enforcement theory requires this gate.",
        ))

    gates.append(_result(
        "certificate_or_ruling_scope",
        True,
        GateState.FAIL if signals.certificate_or_ruling_used_as_merits_proof else GateState.PASS,
        "Procedural certificates/rulings are not being used to prove merits facts."
        if not signals.certificate_or_ruling_used_as_merits_proof
        else "A procedural certificate/ruling is being used to prove merits, agreement, entitlement or remedy. That inference is prohibited.",
    ))

    gates.append(_result(
        "remedy_cause_alignment",
        True,
        GateState.PASS if signals.remedy_matches_cause else GateState.FAIL,
        "Requested remedy is aligned to the selected cause/forum." if signals.remedy_matches_cause
        else "Requested remedy exceeds or does not match the selected cause/forum.",
    ))

    if referral.mixed_causes:
        missing = [lane for lane in referral.mixed_causes if not signals.mixed_lane_authority.get(lane)]
        gates.append(_result(
            "mixed_lane_authority_map",
            True,
            GateState.FAIL if missing else GateState.PASS,
            "Every mixed lane has an identified authority/procedural basis." if not missing
            else "Mixed legal/context lanes lack separate authority/procedural bases: " + ", ".join(missing),
        ))
    else:
        gates.append(_result(
            "mixed_lane_authority_map",
            True,
            GateState.PASS,
            "No mixed lane requires separate authority mapping.",
        ))

    if signals.secondary_questionnaire_flags:
        gates.append(_result(
            "secondary_questionnaire_separation",
            False,
            GateState.WARN,
            "Secondary form questionnaire flags are recorded separately and must not silently replace the primary dispute-type field: "
            + ", ".join(signals.secondary_questionnaire_flags),
        ))
    else:
        gates.append(_result(
            "secondary_questionnaire_separation",
            False,
            GateState.PASS,
            "No secondary questionnaire flag requires separation.",
        ))

    hard_fail = base.release_blocked or any(g.hard and g.state == GateState.FAIL for g in gates)
    warnings = any(g.state == GateState.WARN for g in gates)

    if hard_fail:
        if any(g.gate == "mixed_lane_authority_map" and g.state == GateState.FAIL for g in gates):
            decision = Decision.SEPARATE_CAUSES
        elif any(g.gate in {"closed_list_statutory_subtype", "administrative_processing_is_not_jurisdiction"} and g.state == GateState.FAIL for g in gates):
            decision = Decision.REFRAME
        elif any(g.gate == "agreement_and_authority_for_direct_enforcement" and g.state == GateState.FAIL for g in gates):
            decision = Decision.HOLD_FOR_AUTHORITY
        elif base.release_blocked:
            decision = base.decision
        else:
            decision = Decision.DO_NOT_FILE
    elif warnings or base.decision != Decision.PASS:
        decision = Decision.PASS_WITH_LIMITATIONS
    else:
        decision = Decision.PASS

    return V11Evaluation(base=base, regression_gates=tuple(gates), decision=decision, release_blocked=hard_fail)


def release_allowed_v11(evaluation: V11Evaluation) -> bool:
    return (not evaluation.release_blocked) and evaluation.decision in {
        Decision.PASS,
        Decision.PASS_WITH_LIMITATIONS,
    }
