from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Mapping, Sequence, Tuple

from .lex_omega import ReleaseState


FOREST_FIRST_DOCTRINE_ID = "FFJOS-CANONICAL-001"


def _norm(value: str) -> str:
    return " ".join(value.strip().split())


def _stable_id(prefix: str, parts: Sequence[str]) -> str:
    payload = "|".join(_norm(part).casefold() for part in parts)
    return f"{prefix}-{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


class RiskSignalState(str, Enum):
    USER_SUPPLIED_RISK_SIGNAL = "USER_SUPPLIED_RISK_SIGNAL"
    CORROBORATED_RISK_SIGNAL = "CORROBORATED_RISK_SIGNAL"
    DISCONFIRMED = "DISCONFIRMED"
    UNRESOLVED = "UNRESOLVED"


class ProtectivePosture(str, Enum):
    NORMAL = "NORMAL"
    PROTECTIVE_READINESS = "PROTECTIVE_READINESS"
    ADVERSARIAL_READINESS = "ADVERSARIAL_READINESS"


class ClaimThreshold(str, Enum):
    RISK_HYPOTHESIS = "RISK_HYPOTHESIS"
    EXTERNAL_ACCUSATION = "EXTERNAL_ACCUSATION"


class DefectClass(str, Enum):
    D1_HARMLESS_WORDING = "D1_HARMLESS_WORDING"
    D2_AMBIGUITY = "D2_AMBIGUITY"
    D3_JURISDICTIONAL_EXPOSURE = "D3_JURISDICTIONAL_EXPOSURE"
    D4_APPARENT_CONCESSION = "D4_APPARENT_CONCESSION"
    D5_INCORRECT_AI_PROPOSITION = "D5_INCORRECT_AI_PROPOSITION"
    D6_ADVERSE_RELIANCE = "D6_ADVERSE_RELIANCE"
    D7_ACCRUAL_OR_DEADLINE_ERROR = "D7_ACCRUAL_OR_DEADLINE_ERROR"
    D8_ROUTE_CONTAMINATION = "D8_ROUTE_CONTAMINATION"
    D9_REMEDY_BEFORE_CAUSE = "D9_REMEDY_BEFORE_CAUSE"
    D10_UNSUPPORTED_ACCUSATION = "D10_UNSUPPORTED_ACCUSATION"


@dataclass(frozen=True)
class RiskSignal:
    description: str
    state: RiskSignalState = RiskSignalState.USER_SUPPLIED_RISK_SIGNAL
    observed_indicators: Tuple[str, ...] = ()
    corroborating_evidence_refs: Tuple[str, ...] = ()
    competing_explanations: Tuple[str, ...] = ()
    reversible_protective_actions: Tuple[str, ...] = ()
    falsification_tests: Tuple[str, ...] = ()

    @property
    def signal_id(self) -> str:
        return _stable_id("FF-RISK", (self.description, self.state.value))

    @property
    def protective_action_allowed(self) -> bool:
        return self.state is not RiskSignalState.DISCONFIRMED

    @property
    def accusation_proved(self) -> bool:
        return (
            self.state is RiskSignalState.CORROBORATED_RISK_SIGNAL
            and bool(self.corroborating_evidence_refs)
        )


@dataclass(frozen=True)
class MeritsClaim:
    claim_id: str
    text: str
    evidence_refs: Tuple[str, ...] = ()
    disputed: bool = False
    uncertainty: str = ""


@dataclass
class MeritsGenome:
    matter_id: str
    claims: Mapping[str, MeritsClaim] = field(default_factory=dict)
    chronology_refs: Tuple[str, ...] = ()
    policy_refs: Tuple[str, ...] = ()
    witness_refs: Tuple[str, ...] = ()
    prejudice_refs: Tuple[str, ...] = ()
    unresolved_questions: Tuple[str, ...] = ()

    @property
    def genome_id(self) -> str:
        claim_parts = tuple(
            f"{claim_id}:{_norm(claim.text)}:{','.join(sorted(claim.evidence_refs))}"
            for claim_id, claim in sorted(self.claims.items())
        )
        return _stable_id("FF-MERITS", (self.matter_id, *claim_parts))


@dataclass(frozen=True)
class LegalRouteCard:
    route_id: str
    forum: str
    jurisdiction_source: str
    cause_of_action: str
    challenged_act_or_omission: str
    operative_date: str
    operative_date_basis: str
    filing_period: str
    elements: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    primary_remedy: str
    strongest_adverse_argument: str
    awareness_date: str = ""
    alternative_remedy: str = ""
    overlap_risk: str = ""
    review_or_rescission_route: str = ""

    def completeness_issues(self) -> Tuple[str, ...]:
        required = {
            "forum": self.forum,
            "jurisdiction_source": self.jurisdiction_source,
            "cause_of_action": self.cause_of_action,
            "challenged_act_or_omission": self.challenged_act_or_omission,
            "operative_date": self.operative_date,
            "operative_date_basis": self.operative_date_basis,
            "filing_period": self.filing_period,
            "primary_remedy": self.primary_remedy,
            "strongest_adverse_argument": self.strongest_adverse_argument,
        }
        issues = [f"ROUTE_MISSING_{name.upper()}" for name, value in required.items() if not _norm(value)]
        if not self.elements:
            issues.append("ROUTE_MISSING_ELEMENTS")
        if not self.evidence_refs:
            issues.append("ROUTE_MISSING_EVIDENCE_REFS")
        return tuple(issues)


@dataclass(frozen=True)
class PositionChangeCard:
    subject: str
    current_position: str
    proposed_position: str
    proposer: str
    legal_basis: str
    factual_basis: str
    effect_if_accepted: str
    effect_if_rejected: str
    waiver_or_concession_risk: str
    recommendation: str
    evidence_supporting: Tuple[str, ...] = ()
    evidence_contradicting: Tuple[str, ...] = ()
    informed_human_decision: str = ""

    def unresolved_issues(self) -> Tuple[str, ...]:
        required = {
            "current_position": self.current_position,
            "proposed_position": self.proposed_position,
            "proposer": self.proposer,
            "legal_basis": self.legal_basis,
            "factual_basis": self.factual_basis,
            "effect_if_accepted": self.effect_if_accepted,
            "effect_if_rejected": self.effect_if_rejected,
            "waiver_or_concession_risk": self.waiver_or_concession_risk,
            "recommendation": self.recommendation,
            "informed_human_decision": self.informed_human_decision,
        }
        return tuple(
            f"POSITION_CHANGE_MISSING_{name.upper()}"
            for name, value in required.items()
            if not _norm(value)
        )


@dataclass(frozen=True)
class TeachBackCard:
    dispute_or_issue: str
    challenged_act: str
    operative_date_and_reason: str
    forum_jurisdiction_reason: str
    strongest_evidence: Tuple[str, ...]
    likely_opponent_argument: str
    requested_decision_or_remedy: str

    def unresolved_issues(self) -> Tuple[str, ...]:
        required = {
            "dispute_or_issue": self.dispute_or_issue,
            "challenged_act": self.challenged_act,
            "operative_date_and_reason": self.operative_date_and_reason,
            "forum_jurisdiction_reason": self.forum_jurisdiction_reason,
            "likely_opponent_argument": self.likely_opponent_argument,
            "requested_decision_or_remedy": self.requested_decision_or_remedy,
        }
        issues = [f"TEACHBACK_MISSING_{name.upper()}" for name, value in required.items() if not _norm(value)]
        if not self.strongest_evidence:
            issues.append("TEACHBACK_MISSING_EVIDENCE")
        return tuple(issues)


@dataclass(frozen=True)
class PleadingIntegrityFinding:
    defect: DefectClass
    intended_meaning: str
    filed_or_proposed_wording: str
    legal_consequence: str
    safer_formulation: str = ""
    remediation_route: str = ""
    evidence_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ForestFirstRequest:
    merits_genome: MeritsGenome
    route_card: LegalRouteCard
    teach_back: TeachBackCard
    risk_signals: Tuple[RiskSignal, ...] = ()
    position_changes: Tuple[PositionChangeCard, ...] = ()
    pleading_findings: Tuple[PleadingIntegrityFinding, ...] = ()
    proposed_external_accusations: Tuple[str, ...] = ()
    accusation_evidence_refs: Tuple[str, ...] = ()
    jfrie_status: str = "PASS"


@dataclass(frozen=True)
class ForestFirstResult:
    doctrine_id: str
    posture: ProtectivePosture
    release_state: ReleaseState
    protective_actions: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    accusation_release_allowed: bool
    merits_genome_id: str
    route_id: str


class ForestFirstJusticeGate:
    """Human-centred pre-release gate for high-stakes self-representation work.

    The gate implements the dual threshold "act on risk; accuse on proof" while
    preserving the existing LEX/JFRIE fail-closed release model. It does not
    establish legal jurisdiction by itself and may never override a JFRIE hard
    gate.
    """

    PASSING_JFRIE_STATES = {"PASS", "PASS_WITH_LIMITATIONS"}
    BLOCKING_DEFECTS = {
        DefectClass.D3_JURISDICTIONAL_EXPOSURE,
        DefectClass.D4_APPARENT_CONCESSION,
        DefectClass.D5_INCORRECT_AI_PROPOSITION,
        DefectClass.D7_ACCRUAL_OR_DEADLINE_ERROR,
        DefectClass.D8_ROUTE_CONTAMINATION,
        DefectClass.D9_REMEDY_BEFORE_CAUSE,
        DefectClass.D10_UNSUPPORTED_ACCUSATION,
    }

    def evaluate(self, request: ForestFirstRequest) -> ForestFirstResult:
        reasons: list[str] = []
        protective_actions: list[str] = []

        active_signals = [signal for signal in request.risk_signals if signal.protective_action_allowed]
        for signal in active_signals:
            protective_actions.extend(signal.reversible_protective_actions)

        posture = ProtectivePosture.NORMAL
        if active_signals:
            posture = ProtectivePosture.PROTECTIVE_READINESS
        if any(
            signal.state is RiskSignalState.CORROBORATED_RISK_SIGNAL
            or len(signal.observed_indicators) >= 2
            for signal in active_signals
        ):
            posture = ProtectivePosture.ADVERSARIAL_READINESS

        if request.jfrie_status not in self.PASSING_JFRIE_STATES:
            reasons.append("JFRIE_FAIL_CLOSED")

        reasons.extend(request.route_card.completeness_issues())
        reasons.extend(request.teach_back.unresolved_issues())
        for change in request.position_changes:
            reasons.extend(change.unresolved_issues())

        blocking_findings = [finding for finding in request.pleading_findings if finding.defect in self.BLOCKING_DEFECTS]
        if blocking_findings:
            reasons.extend(f"PLEADING_{finding.defect.value}" for finding in blocking_findings)

        accusation_release_allowed = not request.proposed_external_accusations
        if request.proposed_external_accusations:
            accusation_release_allowed = bool(request.accusation_evidence_refs)
            if not accusation_release_allowed:
                reasons.append("ACCUSATION_PROOF_REQUIRED")

        if request.jfrie_status not in self.PASSING_JFRIE_STATES:
            release = ReleaseState.DO_NOT_FILE
        elif any(code.startswith("ROUTE_") for code in reasons):
            release = ReleaseState.REFRAME
        elif any(code.startswith("POSITION_CHANGE_") for code in reasons):
            release = ReleaseState.PASS_WITH_LIMITATIONS
        elif any(code.startswith("TEACHBACK_") for code in reasons):
            release = ReleaseState.PASS_WITH_LIMITATIONS
        elif blocking_findings:
            release = ReleaseState.REFRAME
        elif not accusation_release_allowed:
            release = ReleaseState.PASS_WITH_LIMITATIONS
        elif request.jfrie_status == "PASS_WITH_LIMITATIONS":
            release = ReleaseState.PASS_WITH_LIMITATIONS
        else:
            release = ReleaseState.PASS

        return ForestFirstResult(
            doctrine_id=FOREST_FIRST_DOCTRINE_ID,
            posture=posture,
            release_state=release,
            protective_actions=tuple(dict.fromkeys(action for action in protective_actions if _norm(action))),
            reason_codes=tuple(dict.fromkeys(reasons)),
            accusation_release_allowed=accusation_release_allowed,
            merits_genome_id=request.merits_genome.genome_id,
            route_id=request.route_card.route_id,
        )


__all__ = [
    "ClaimThreshold",
    "DefectClass",
    "FOREST_FIRST_DOCTRINE_ID",
    "ForestFirstJusticeGate",
    "ForestFirstRequest",
    "ForestFirstResult",
    "LegalRouteCard",
    "MeritsClaim",
    "MeritsGenome",
    "PleadingIntegrityFinding",
    "PositionChangeCard",
    "ProtectivePosture",
    "RiskSignal",
    "RiskSignalState",
    "TeachBackCard",
]
