from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from hashlib import sha256
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


class AuthorityState(str, Enum):
    CURRENT_VERIFIED = "CURRENT_VERIFIED"
    RECHECK_REQUIRED = "RECHECK_REQUIRED"
    SUPERSEDED = "SUPERSEDED"
    CONFLICTED = "CONFLICTED"
    UNVERIFIED = "UNVERIFIED"


class PropositionState(str, Enum):
    VERIFIED_LAW = "VERIFIED_LAW"
    VERIFIED_WITH_LIMITATION = "VERIFIED_WITH_LIMITATION"
    DISPUTED_LAW = "DISPUTED_LAW"
    STRATEGIC_OPTION = "STRATEGIC_OPTION"
    UNVERIFIED = "UNVERIFIED"
    QUARANTINED = "QUARANTINED"


class TriangleState(str, Enum):
    CLOSED = "CLOSED"
    MISSING_LAW = "MISSING_LAW"
    MISSING_CLAIM = "MISSING_CLAIM"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    MULTIPLE_GAPS = "MULTIPLE_GAPS"


class CounselRole(str, Enum):
    PRIMARY_ANALYST = "PRIMARY_ANALYST"
    EMPLOYER_RED_TEAM = "EMPLOYER_RED_TEAM"
    NEUTRAL_DECISION_MAKER = "NEUTRAL_DECISION_MAKER"


class OutcomeClass(str, Enum):
    LEGAL_ERROR = "LEGAL_ERROR"
    EVIDENCE_FAILURE = "EVIDENCE_FAILURE"
    PROCEDURAL_FAILURE = "PROCEDURAL_FAILURE"
    FACTUAL_FINDING = "FACTUAL_FINDING"
    DISCRETIONARY_OUTCOME = "DISCRETIONARY_OUTCOME"
    STRATEGIC_FAILURE = "STRATEGIC_FAILURE"
    STRATEGIC_SUCCESS = "STRATEGIC_SUCCESS"
    UNCLASSIFIED = "UNCLASSIFIED"


class ReleaseState(str, Enum):
    PASS = "PASS"
    PASS_WITH_LIMITATIONS = "PASS_WITH_LIMITATIONS"
    HOLD_FOR_AUTHORITY = "HOLD_FOR_AUTHORITY"
    HOLD_FOR_SOURCE = "HOLD_FOR_SOURCE"
    REFRAME = "REFRAME"
    SEPARATE_CAUSES = "SEPARATE_CAUSES"
    LEGAL_RESEARCH_REQUIRED = "LEGAL_RESEARCH_REQUIRED"
    DO_NOT_FILE = "DO_NOT_FILE"
    RESYNC_REQUIRED = "RESYNC_REQUIRED"


class MaturityLevel(str, Enum):
    DESIGN_ONLY = "DESIGN_ONLY"
    DETERMINISTIC_TESTED = "DETERMINISTIC_TESTED"
    SHADOW_VALIDATED = "SHADOW_VALIDATED"
    CANARY_VALIDATED = "CANARY_VALIDATED"
    WORKFLOW_VERIFIED = "WORKFLOW_VERIFIED"
    OPERATIONAL_VERIFIED = "OPERATIONAL_VERIFIED"


@dataclass(frozen=True)
class AuthorityRecord:
    authority_id: str
    citation: str
    source_ref: str
    verified_on: Optional[date] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    later_treatment_checked: bool = False
    state: AuthorityState = AuthorityState.UNVERIFIED
    revalidation_days: int = 30

    def status_on(self, on_date: date) -> AuthorityState:
        if self.state in {AuthorityState.SUPERSEDED, AuthorityState.CONFLICTED, AuthorityState.UNVERIFIED}:
            return self.state
        if self.effective_from and on_date < self.effective_from:
            return AuthorityState.RECHECK_REQUIRED
        if self.effective_to and on_date > self.effective_to:
            return AuthorityState.SUPERSEDED
        if not self.verified_on:
            return AuthorityState.UNVERIFIED
        if on_date - self.verified_on > timedelta(days=self.revalidation_days):
            return AuthorityState.RECHECK_REQUIRED
        if not self.later_treatment_checked:
            return AuthorityState.RECHECK_REQUIRED
        return AuthorityState.CURRENT_VERIFIED


@dataclass(frozen=True)
class LegalProposition:
    text: str
    authority_ids: Tuple[str, ...]
    proposition_state: PropositionState = PropositionState.UNVERIFIED
    matter_id: Optional[str] = None
    legal_route: Optional[str] = None
    element_ids: Tuple[str, ...] = ()

    @property
    def proposition_id(self) -> str:
        normalized = " ".join(self.text.lower().split())
        payload = "|".join(
            [normalized, *(sorted(self.authority_ids)), self.matter_id or "", self.legal_route or ""]
        )
        return f"LP-{sha256(payload.encode('utf-8')).hexdigest()[:16]}"


@dataclass
class LegalPropositionLedger:
    authorities: Dict[str, AuthorityRecord] = field(default_factory=dict)
    propositions: Dict[str, LegalProposition] = field(default_factory=dict)

    def add_authority(self, record: AuthorityRecord) -> None:
        self.authorities[record.authority_id] = record

    def add_proposition(self, proposition: LegalProposition) -> str:
        proposition_id = proposition.proposition_id
        self.propositions[proposition_id] = proposition
        return proposition_id

    def proposition_authority_state(self, proposition_id: str, on_date: date) -> AuthorityState:
        proposition = self.propositions[proposition_id]
        if not proposition.authority_ids:
            return AuthorityState.UNVERIFIED
        states = [self.authorities[a].status_on(on_date) for a in proposition.authority_ids if a in self.authorities]
        if len(states) != len(proposition.authority_ids):
            return AuthorityState.UNVERIFIED
        if AuthorityState.SUPERSEDED in states:
            return AuthorityState.SUPERSEDED
        if AuthorityState.CONFLICTED in states:
            return AuthorityState.CONFLICTED
        if AuthorityState.UNVERIFIED in states:
            return AuthorityState.UNVERIFIED
        if AuthorityState.RECHECK_REQUIRED in states:
            return AuthorityState.RECHECK_REQUIRED
        return AuthorityState.CURRENT_VERIFIED

    def dependants_for_authority(self, authority_id: str) -> Tuple[str, ...]:
        return tuple(
            proposition_id
            for proposition_id, proposition in self.propositions.items()
            if authority_id in proposition.authority_ids
        )


@dataclass(frozen=True)
class ClaimLawEvidenceTriangle:
    element_id: str
    law_proposition_id: Optional[str]
    factual_claim_id: Optional[str]
    evidence_source_ids: Tuple[str, ...] = ()

    @property
    def state(self) -> TriangleState:
        missing = []
        if not self.law_proposition_id:
            missing.append("law")
        if not self.factual_claim_id:
            missing.append("claim")
        if not self.evidence_source_ids:
            missing.append("evidence")
        if not missing:
            return TriangleState.CLOSED
        if len(missing) > 1:
            return TriangleState.MULTIPLE_GAPS
        return {
            "law": TriangleState.MISSING_LAW,
            "claim": TriangleState.MISSING_CLAIM,
            "evidence": TriangleState.MISSING_EVIDENCE,
        }[missing[0]]


@dataclass(frozen=True)
class CounselSubmission:
    role: CounselRole
    conclusion: str
    authorities: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()
    uncertainties: Tuple[str, ...] = ()


@dataclass
class IndependentCounselPanel:
    """Collects sealed independent submissions and exposes them only at integration."""

    _sealed: Dict[CounselRole, CounselSubmission] = field(default_factory=dict)
    _integrated: bool = False

    def submit(self, submission: CounselSubmission) -> None:
        if self._integrated:
            raise RuntimeError("panel already integrated")
        if submission.role in self._sealed:
            raise ValueError(f"duplicate role submission: {submission.role}")
        self._sealed[submission.role] = submission

    def role_status(self) -> Mapping[CounselRole, bool]:
        return {role: role in self._sealed for role in CounselRole}

    def integrate(self) -> Tuple[CounselSubmission, ...]:
        required = set(CounselRole)
        missing = required.difference(self._sealed)
        if missing:
            raise ValueError(f"missing independent counsel roles: {sorted(r.value for r in missing)}")
        self._integrated = True
        return tuple(self._sealed[role] for role in CounselRole)


@dataclass(frozen=True)
class OutcomeLearningEvent:
    description: str
    legal_rule_rejected: bool = False
    proof_deficiency: bool = False
    procedural_defect: bool = False
    factual_finding: bool = False
    discretion_exercised: bool = False
    strategy_failed: bool = False
    strategy_succeeded: bool = False

    @property
    def classification(self) -> OutcomeClass:
        flags = [
            (self.legal_rule_rejected, OutcomeClass.LEGAL_ERROR),
            (self.proof_deficiency, OutcomeClass.EVIDENCE_FAILURE),
            (self.procedural_defect, OutcomeClass.PROCEDURAL_FAILURE),
            (self.factual_finding, OutcomeClass.FACTUAL_FINDING),
            (self.discretion_exercised, OutcomeClass.DISCRETIONARY_OUTCOME),
            (self.strategy_failed, OutcomeClass.STRATEGIC_FAILURE),
            (self.strategy_succeeded, OutcomeClass.STRATEGIC_SUCCESS),
        ]
        active = [classification for enabled, classification in flags if enabled]
        return active[0] if len(active) == 1 else OutcomeClass.UNCLASSIFIED

    @property
    def may_auto_promote_doctrine(self) -> bool:
        return False


@dataclass
class MaturityTracker:
    level: MaturityLevel = MaturityLevel.DESIGN_ONLY
    evidence: List[str] = field(default_factory=list)

    _order: Tuple[MaturityLevel, ...] = (
        MaturityLevel.DESIGN_ONLY,
        MaturityLevel.DETERMINISTIC_TESTED,
        MaturityLevel.SHADOW_VALIDATED,
        MaturityLevel.CANARY_VALIDATED,
        MaturityLevel.WORKFLOW_VERIFIED,
        MaturityLevel.OPERATIONAL_VERIFIED,
    )

    def promote(self, target: MaturityLevel, proof_refs: Sequence[str]) -> None:
        current_index = self._order.index(self.level)
        target_index = self._order.index(target)
        if target_index != current_index + 1:
            raise ValueError("maturity promotion must be sequential")
        if not proof_refs:
            raise ValueError("maturity promotion requires proof")
        self.level = target
        self.evidence.extend(proof_refs)


@dataclass(frozen=True)
class LexOmegaResult:
    release_state: ReleaseState
    authority_issues: Tuple[str, ...]
    triangle_issues: Tuple[str, ...]
    counsel_conflicts: Tuple[str, ...]
    learning_classes: Tuple[OutcomeClass, ...]
    maturity: MaturityLevel
    jfrie_status: str


@dataclass
class LexOmegaCouncil:
    ledger: LegalPropositionLedger
    maturity: MaturityTracker = field(default_factory=MaturityTracker)

    PASSING_JFRIE_STATES: Tuple[str, ...] = ("PASS", "PASS_WITH_LIMITATIONS")

    def evaluate(
        self,
        *,
        on_date: date,
        proposition_ids: Iterable[str],
        triangles: Iterable[ClaimLawEvidenceTriangle],
        counsel_submissions: Sequence[CounselSubmission],
        outcome_events: Iterable[OutcomeLearningEvent],
        jfrie_status: str,
    ) -> LexOmegaResult:
        if jfrie_status not in self.PASSING_JFRIE_STATES:
            return LexOmegaResult(
                release_state=ReleaseState.DO_NOT_FILE,
                authority_issues=(),
                triangle_issues=(),
                counsel_conflicts=(),
                learning_classes=tuple(event.classification for event in outcome_events),
                maturity=self.maturity.level,
                jfrie_status=jfrie_status,
            )

        authority_issues: List[str] = []
        for proposition_id in proposition_ids:
            state = self.ledger.proposition_authority_state(proposition_id, on_date)
            if state != AuthorityState.CURRENT_VERIFIED:
                authority_issues.append(f"{proposition_id}:{state.value}")

        triangle_issues = [
            f"{triangle.element_id}:{triangle.state.value}"
            for triangle in triangles
            if triangle.state != TriangleState.CLOSED
        ]

        panel = IndependentCounselPanel()
        for submission in counsel_submissions:
            panel.submit(submission)
        integrated = panel.integrate()
        conclusions = {submission.conclusion.strip() for submission in integrated}
        counsel_conflicts: Tuple[str, ...] = ()
        if len(conclusions) > 1:
            counsel_conflicts = tuple(sorted(conclusions))

        learning_classes = tuple(event.classification for event in outcome_events)

        if authority_issues:
            release = ReleaseState.HOLD_FOR_AUTHORITY
        elif triangle_issues:
            release = ReleaseState.HOLD_FOR_SOURCE
        elif counsel_conflicts:
            release = ReleaseState.PASS_WITH_LIMITATIONS
        else:
            release = ReleaseState.PASS if jfrie_status == "PASS" else ReleaseState.PASS_WITH_LIMITATIONS

        return LexOmegaResult(
            release_state=release,
            authority_issues=tuple(authority_issues),
            triangle_issues=tuple(triangle_issues),
            counsel_conflicts=counsel_conflicts,
            learning_classes=learning_classes,
            maturity=self.maturity.level,
            jfrie_status=jfrie_status,
        )
