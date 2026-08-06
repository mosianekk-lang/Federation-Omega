"""EvidenceOps Jurisdiction-First Referral Integrity Engine (JFRIE) v1.0.

Deterministic internal release gate for jurisdiction-sensitive legal drafting.
It does not provide legal advice, file documents, mutate evidence, or replace
current authority verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


class AuthorityClass(str, Enum):
    STATUTE = "STATUTE"
    RULE = "RULE"
    OFFICIAL_FORM = "OFFICIAL_FORM"
    BINDING_CASE = "BINDING_CASE"
    PERSUASIVE_CASE = "PERSUASIVE_CASE"
    ESTABLISHED_USAGE = "ESTABLISHED_USAGE"
    PARTY_LABEL = "PARTY_LABEL"
    AI_TERM = "AI_TERM"
    UNVERIFIED = "UNVERIFIED"


class GateState(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class Decision(str, Enum):
    PASS = "PASS"
    PASS_WITH_LIMITATIONS = "PASS_WITH_LIMITATIONS"
    HOLD_FOR_AUTHORITY = "HOLD_FOR_AUTHORITY"
    REFRAME = "REFRAME"
    SEPARATE_CAUSES = "SEPARATE_CAUSES"
    AMEND_OR_CLARIFY = "AMEND_OR_CLARIFY"
    RE_REFER_IF_LEGALLY_OPEN = "RE_REFER_IF_LEGALLY_OPEN"
    DO_NOT_FILE = "DO_NOT_FILE"
    LEGAL_RESEARCH_REQUIRED = "LEGAL_RESEARCH_REQUIRED"


AUTHORITATIVE_LABEL_CLASSES = {
    AuthorityClass.STATUTE,
    AuthorityClass.RULE,
    AuthorityClass.OFFICIAL_FORM,
    AuthorityClass.BINDING_CASE,
    AuthorityClass.PERSUASIVE_CASE,
    AuthorityClass.ESTABLISHED_USAGE,
}

# Terms are indicators, not automatic legal errors. They become defects when used
# as the cause/category without a recognised authority source.
LEGAL_LOOKING_INDICATORS = {
    "protective referral",
    "protective filing",
    "employer conduct",
    "unfair conduct",
    "governance breach",
    "occupational detriment",
    "all rights reserved",
    "without waiver",
    "without prejudice",
}


@dataclass(frozen=True)
class LegalLabel:
    text: str
    authority_class: AuthorityClass
    authority_ref: Optional[str] = None
    used_as_jurisdictional_category: bool = False


@dataclass(frozen=True)
class CauseElement:
    name: str
    fact_refs: Sequence[str] = field(default_factory=tuple)
    authority_ref: Optional[str] = None


@dataclass
class ReferralInput:
    instrument: str
    forum: str
    cause_of_action: str
    cause_authority_ref: Optional[str]
    cause_authority_class: AuthorityClass
    specific_act_or_omission: str
    dispute_date: Optional[str]
    filing_date: Optional[str]
    filing_period_rule: Optional[str]
    maturity_basis: Optional[str]
    elements: Sequence[CauseElement]
    remedy: str
    remedy_authority_ref: Optional[str]
    narrative: str
    labels: Sequence[LegalLabel] = field(default_factory=tuple)
    mixed_causes: Sequence[str] = field(default_factory=tuple)
    source_refs: Sequence[str] = field(default_factory=tuple)
    form_category: Optional[str] = None
    separate_matter_controls: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class GateResult:
    gate: str
    hard: bool
    state: GateState
    reason: str


@dataclass(frozen=True)
class Evaluation:
    decision: Decision
    release_blocked: bool
    gates: Sequence[GateResult]
    cause_sentence: Optional[str]
    semantic_laundering_flags: Sequence[str]


def _nonempty(value: Optional[str]) -> bool:
    return bool(value and value.strip())


def _gate(gate: str, hard: bool, ok: bool, pass_reason: str, fail_reason: str) -> GateResult:
    return GateResult(gate, hard, GateState.PASS if ok else GateState.FAIL, pass_reason if ok else fail_reason)


def _terminology_gate(labels: Iterable[LegalLabel]) -> tuple[GateResult, List[str]]:
    flags: List[str] = []
    invalid_category_labels: List[str] = []
    for label in labels:
        normalized = label.text.strip().lower()
        suspicious = any(term in normalized for term in LEGAL_LOOKING_INDICATORS)
        if suspicious or label.authority_class in {AuthorityClass.PARTY_LABEL, AuthorityClass.AI_TERM, AuthorityClass.UNVERIFIED}:
            flags.append(f"{label.text} [{label.authority_class.value}]")
        if label.used_as_jurisdictional_category and label.authority_class not in AUTHORITATIVE_LABEL_CLASSES:
            invalid_category_labels.append(label.text)

    if invalid_category_labels:
        return (
            GateResult(
                "terminology_authority",
                True,
                GateState.FAIL,
                "Non-authoritative legal label used as jurisdictional category: " + ", ".join(invalid_category_labels),
            ),
            flags,
        )
    return (
        GateResult(
            "terminology_authority",
            True,
            GateState.PASS,
            "No PARTY_LABEL/AI_TERM/UNVERIFIED term substitutes for the jurisdictional category.",
        ),
        flags,
    )


def evaluate(referral: ReferralInput) -> Evaluation:
    gates: List[GateResult] = []

    gates.append(_gate(
        "instrument_identification", True, _nonempty(referral.instrument),
        f"Instrument identified: {referral.instrument}",
        "No exact statutory/procedural instrument identified.",
    ))

    cause_ok = (
        _nonempty(referral.cause_of_action)
        and _nonempty(referral.cause_authority_ref)
        and referral.cause_authority_class in AUTHORITATIVE_LABEL_CLASSES
    )
    gates.append(_gate(
        "cause_of_action", True, cause_ok,
        f"Recognised cause identified: {referral.cause_of_action}",
        "Cause of action is missing or not anchored in an authoritative legal source.",
    ))

    gates.append(_gate(
        "forum_jurisdiction", True, _nonempty(referral.forum) and cause_ok,
        f"Forum identified: {referral.forum}; cause authority is present.",
        "Forum/cause jurisdiction cannot be established from the input.",
    ))

    gates.append(_gate(
        "dispute_maturity", True, _nonempty(referral.specific_act_or_omission) and _nonempty(referral.maturity_basis),
        "A specific act/omission and maturity basis are identified.",
        "The filing risks referring an anticipated or undefined dispute rather than an arisen trigger.",
    ))

    accrual_ok = all((_nonempty(referral.dispute_date), _nonempty(referral.filing_date), _nonempty(referral.filing_period_rule)))
    gates.append(_gate(
        "accrual_and_time", True, accrual_ok,
        "Dispute date, filing date and filing-period rule are identified.",
        "Accrual/timing cannot be audited because a required date or time rule is missing.",
    ))

    elements_ok = bool(referral.elements) and all(_nonempty(e.name) and _nonempty(e.authority_ref) for e in referral.elements)
    gates.append(_gate(
        "elements", True, elements_ok,
        f"{len(referral.elements)} cause element(s) identified and authority-linked.",
        "Essential elements are missing or lack authority references.",
    ))

    fact_map_ok = elements_ok and all(bool(e.fact_refs) for e in referral.elements)
    gates.append(_gate(
        "fact_to_element", True, fact_map_ok,
        "Every identified element has at least one fact/source reference.",
        "One or more essential elements have no mapped fact/source reference.",
    ))

    remedy_ok = _nonempty(referral.remedy) and _nonempty(referral.remedy_authority_ref)
    gates.append(_gate(
        "remedy_competence", True, remedy_ok,
        "Requested relief has an identified authority basis.",
        "Requested relief is missing or lacks a forum-power authority reference.",
    ))

    category_consistent = not referral.form_category or referral.form_category.lower() in referral.cause_of_action.lower() or referral.cause_of_action.lower() in referral.form_category.lower()
    gates.append(GateResult(
        "characterisation_consistency",
        False,
        GateState.PASS if category_consistent else GateState.WARN,
        "Form category and pleaded cause are facially aligned." if category_consistent else "Form category and pleaded cause need explicit reconciliation.",
    ))

    mixed_state = GateState.WARN if len(set(referral.mixed_causes)) > 1 else GateState.PASS
    gates.append(GateResult(
        "mixed_cause_separation",
        False,
        mixed_state,
        "Multiple causes/context lanes require explicit separation." if mixed_state == GateState.WARN else "No unresolved mixed-cause collision detected.",
    ))

    terminology, flags = _terminology_gate(referral.labels)
    gates.append(terminology)

    source_ok = bool(referral.source_refs)
    gates.append(GateResult(
        "source_provenance",
        False,
        GateState.PASS if source_ok else GateState.WARN,
        "Source references supplied." if source_ok else "Material facts are not yet source-controlled.",
    ))

    parallel_state = GateState.PASS if referral.separate_matter_controls or not referral.mixed_causes else GateState.WARN
    gates.append(GateResult(
        "parallel_matter_separation",
        False,
        parallel_state,
        "Parallel-matter control is present or unnecessary." if parallel_state == GateState.PASS else "Related matters need an express no-merger/no-consolidation treatment.",
    ))

    hard_fail = any(g.hard and g.state == GateState.FAIL for g in gates)
    soft_warn = any((not g.hard) and g.state != GateState.PASS for g in gates)

    if hard_fail:
        if terminology.state == GateState.FAIL:
            decision = Decision.REFRAME
        elif not cause_ok or not elements_ok:
            decision = Decision.LEGAL_RESEARCH_REQUIRED
        elif not remedy_ok:
            decision = Decision.HOLD_FOR_AUTHORITY
        else:
            decision = Decision.DO_NOT_FILE
    elif soft_warn:
        if len(set(referral.mixed_causes)) > 1:
            decision = Decision.SEPARATE_CAUSES
        else:
            decision = Decision.PASS_WITH_LIMITATIONS
    else:
        decision = Decision.PASS

    cause_sentence = None
    if cause_ok and _nonempty(referral.dispute_date) and _nonempty(referral.specific_act_or_omission) and elements_ok and remedy_ok:
        element_names = ", ".join(e.name for e in referral.elements)
        cause_sentence = (
            f"On {referral.dispute_date}, the employer {referral.specific_act_or_omission}, "
            f"which constitutes {referral.cause_of_action} under {referral.cause_authority_ref} "
            f"because the pleaded elements are {element_names}, and the competent relief sought is {referral.remedy}."
        )

    return Evaluation(decision, hard_fail, tuple(gates), cause_sentence, tuple(flags))


def release_allowed(evaluation: Evaluation) -> bool:
    """Return True only when no hard gate failed and decision is releasable."""
    return (not evaluation.release_blocked) and evaluation.decision in {
        Decision.PASS,
        Decision.PASS_WITH_LIMITATIONS,
    }
