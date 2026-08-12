"""Bounded no-effect shadow/adversarial validation for admitted JFRIE v2 slices.

This module executes synthetic replay vectors against the admitted JFRIE v2 core,
contamination scanner and execution-assurance extension. It is intentionally
A1_INTERNAL only: it does not file, send, mutate evidence, call a provider, or
claim full C001-C100 parity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Callable, Iterable, Mapping

from .jfrie import AuthorityClass, CauseElement, LegalLabel, ReferralInput
from .jfrie_v2 import (
    AUTHORITY_CEILING,
    ClaimRecord,
    ClaimStatus,
    ContaminationState,
    IntegrityGraph,
    JfrieV2Core,
    ProvenanceClass,
    ReleaseRequest,
    SourceRecord,
)
from .jfrie_v2_assurance import (
    AssuranceContext,
    AssuranceSignals,
    HashScope,
    JfrieV2Assurance,
)
from .jfrie_v2_contamination import (
    ArtifactNode,
    ArtifactState,
    AssertionKind,
    JfrieV2ContaminationScanner,
    PromptTemplateInput,
    PropositionInput,
    SignalSeverity,
)


VERSION = "2.0.0-shadow-adversarial-1"
FULL_V2_PARITY = False


class ValidationMode(str, Enum):
    SHADOW = "SHADOW"
    ADVERSARIAL = "ADVERSARIAL"


@dataclass(frozen=True)
class ValidationCaseResult:
    case_id: str
    mode: ValidationMode
    passed: bool
    observed: tuple[str, ...]
    expected: tuple[str, ...]
    prohibited: tuple[str, ...]


@dataclass(frozen=True)
class ValidationReceipt:
    receipt_id: str
    mode: ValidationMode
    source_ref: str
    observed_at: str
    case_count: int
    passed_count: int
    failed_case_ids: tuple[str, ...]
    external_effect: bool
    authority_ceiling: str
    result_sha256: str

    @property
    def qualifies(self) -> bool:
        return (
            self.case_count > 0
            and self.passed_count == self.case_count
            and not self.failed_case_ids
            and not self.external_effect
            and self.authority_ceiling == AUTHORITY_CEILING
            and len(self.result_sha256) == 64
        )


def _valid_referral(*, ai_term: bool = False) -> ReferralInput:
    labels = ()
    if ai_term:
        labels = (
            LegalLabel(
                "protective referral",
                AuthorityClass.AI_TERM,
                used_as_jurisdictional_category=True,
            ),
        )
    return ReferralInput(
        instrument="LRA section 188A inquiry by arbitrator",
        forum="CCMA",
        cause_of_action="inquiry by arbitrator under LRA section 188A",
        cause_authority_ref="LRA s188A",
        cause_authority_class=AuthorityClass.STATUTE,
        specific_act_or_omission="initiated the prescribed inquiry procedure",
        dispute_date="2026-08-01",
        filing_date="2026-08-02",
        filing_period_rule="current verified forum rule",
        maturity_basis="prescribed trigger has arisen",
        elements=(CauseElement("prescribed inquiry trigger", ("FACT-1",), "LRA s188A"),),
        remedy="conduct the inquiry within statutory/forum competence",
        remedy_authority_ref="LRA s188A",
        narrative="Bounded synthetic source-controlled replay narrative.",
        source_refs=("SRC-PRIMARY-1",),
        form_category="inquiry by arbitrator",
        labels=labels,
    )


def _graph() -> IntegrityGraph:
    graph = IntegrityGraph()
    graph.register_source(SourceRecord("SRC-PRIMARY-1", ProvenanceClass.PRIMARY_EVIDENCE, authenticated=True))
    graph.register_source(SourceRecord("SRC-DERIV-1", ProvenanceClass.DERIVATIVE_SUMMARY, parent_source_id="SRC-PRIMARY-1"))
    graph.register_source(SourceRecord("SRC-AI-1", ProvenanceClass.AI_ORIGIN))
    graph.register_claim(
        ClaimRecord(
            claim_id="CLM-1",
            exact_text="The prescribed inquiry trigger has arisen.",
            normalized_text="prescribed inquiry trigger has arisen",
            matter_id="MAT-SYNTHETIC-188A",
            workstream_id="WS-JFRIE-VALIDATION",
            origin_type=ProvenanceClass.PRIMARY_EVIDENCE,
            origin_reference="SRC-PRIMARY-1",
            source_ids=("SRC-PRIMARY-1",),
            evidence_status=ClaimStatus.VERIFIED,
            authority_status="VERIFIED",
            created_at="2026-08-12T00:00:00Z",
            last_verified_at="2026-08-12T00:00:00Z",
            contamination_state=ContaminationState.CLEAN,
            release_eligibility=False,
            legal_category="LRA s188A inquiry",
            authority_ref="LRA s188A",
        )
    )
    graph.mark_release_eligible("CLM-1", timestamp="2026-08-12T00:30:00Z")
    return graph


def _request(graph: IntegrityGraph, *, ai_term: bool = False) -> ReleaseRequest:
    if "CLM-1" not in graph.claims:
        raise ValueError("validation graph missing synthetic claim")
    return ReleaseRequest(
        _valid_referral(ai_term=ai_term),
        ("CLM-1",),
        {"truthgrid": True, "lex": True, "caseforge": True},
        True,
        True,
        "synthetic-readback-ref",
        "synthetic-snapshot-ref",
    )


def _assurance_engine() -> tuple[JfrieV2Assurance, IntegrityGraph]:
    graph = _graph()
    return JfrieV2Assurance(JfrieV2Core(graph)), graph


def _result(
    case_id: str,
    mode: ValidationMode,
    *,
    observed: Iterable[str],
    expected: Iterable[str],
    prohibited: Iterable[str] = (),
) -> ValidationCaseResult:
    obs = tuple(sorted(set(observed)))
    exp = tuple(sorted(set(expected)))
    pro = tuple(sorted(set(prohibited)))
    passed = all(item in obs for item in exp) and all(item not in obs for item in pro)
    return ValidationCaseResult(case_id, mode, passed, obs, exp, pro)


def _shadow_cases(observed_at: str) -> tuple[ValidationCaseResult, ...]:
    scanner = JfrieV2ContaminationScanner()
    graph = _graph()

    clean = scanner.scan_proposition(
        PropositionInput(
            "P-SHADOW-CLEAN",
            "The source records the event.",
            AssertionKind.FACT,
            ProvenanceClass.PRIMARY_EVIDENCE,
            ProvenanceClass.PRIMARY_EVIDENCE,
            ("SRC-PRIMARY-1",),
            human_verified=True,
        ),
        graph,
    )

    ai_fact = scanner.scan_proposition(
        PropositionInput(
            "P-SHADOW-AI",
            "The event definitely occurred.",
            AssertionKind.FACT,
            ProvenanceClass.AI_ORIGIN,
            ProvenanceClass.AI_ORIGIN,
            ("SRC-AI-1",),
            human_verified=False,
        ),
        graph,
    )

    template = scanner.scan_template(
        PromptTemplateInput(
            "T-SHADOW-BAD",
            "Produce a synthetic filing draft.",
            ProvenanceClass.USER_SUPPLIED,
            "SYNTHETIC-TEMPLATE",
            promotes_unverified_to_verified=True,
            suppresses_adverse_evidence=True,
            overrides_release_gate=True,
        )
    )

    propagation = scanner.propagate_artifact_contamination(
        (
            ArtifactNode("ROOT", template_ids=("BAD-TEMPLATE",)),
            ArtifactNode("CHILD", parent_artifact_ids=("ROOT",)),
            ArtifactNode("UNRELATED"),
        ),
        contaminated_template_ids=("BAD-TEMPLATE",),
    )

    assurance, assurance_graph = _assurance_engine()
    clean_assurance = assurance.evaluate(
        _request(assurance_graph),
        AssuranceSignals(hash_present=True, hash_scope=HashScope.CANONICAL_SEMANTIC),
        AssuranceContext(
            object_id="OBJ-SHADOW-CLEAN",
            source_ids=("SRC-PRIMARY-1",),
            executed_at=observed_at,
            node_version_current=True,
        ),
    )

    return (
        _result(
            "SHADOW-CLEAN-PRIMARY",
            ValidationMode.SHADOW,
            observed=("NO_SIGNAL",) if not clean else (signal.code for signal in clean),
            expected=("NO_SIGNAL",),
        ),
        _result(
            "SHADOW-AI-LAUNDERING",
            ValidationMode.SHADOW,
            observed=(signal.code for signal in ai_fact),
            expected=(
                "INFERENCE_OR_DERIVATIVE_LAUNDERED_AS_FACT",
                "FACT_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT",
                "AI_ORIGIN_REQUIRES_HUMAN_OR_INDEPENDENT_VERIFICATION",
            ),
        ),
        _result(
            "SHADOW-TEMPLATE-WEAKENING",
            ValidationMode.SHADOW,
            observed=(signal.code for signal in template if signal.severity is SignalSeverity.BLOCK),
            expected=(
                "TEMPLATE_PROMOTES_UNVERIFIED_TO_VERIFIED",
                "TEMPLATE_SUPPRESSES_ADVERSE_EVIDENCE",
                "TEMPLATE_OVERRIDES_RELEASE_GATE",
            ),
        ),
        _result(
            "SHADOW-CONTAMINATION-PROPAGATION",
            ValidationMode.SHADOW,
            observed=(
                f"ROOT={propagation.states['ROOT'].value}",
                f"CHILD={propagation.states['CHILD'].value}",
                f"UNRELATED={propagation.states['UNRELATED'].value}",
            ),
            expected=(
                f"ROOT={ArtifactState.TAINTED.value}",
                f"CHILD={ArtifactState.NEEDS_REVIEW.value}",
                f"UNRELATED={ArtifactState.CLEAN.value}",
            ),
        ),
        _result(
            "SHADOW-CLEAN-ASSURANCE",
            ValidationMode.SHADOW,
            observed=(
                f"CORE_ALLOWED={clean_assurance.core.allowed}",
                f"ALLOWED={clean_assurance.allowed}",
                f"RECEIPTS={len(clean_assurance.receipts)}",
            ),
            expected=("CORE_ALLOWED=True", "ALLOWED=True", "RECEIPTS=9"),
        ),
    )


def _adversarial_cases(observed_at: str) -> tuple[ValidationCaseResult, ...]:
    scanner = JfrieV2ContaminationScanner()
    graph = _graph()

    mismatch = scanner.scan_proposition(
        PropositionInput(
            "P-ADV-MISMATCH",
            "A derivative summary reports X.",
            AssertionKind.OBSERVATION,
            ProvenanceClass.DERIVATIVE_SUMMARY,
            ProvenanceClass.PRIMARY_EVIDENCE,
            ("SRC-DERIV-1",),
        ),
        graph,
    )
    missing = scanner.scan_proposition(
        PropositionInput(
            "P-ADV-MISSING",
            "A fact from a missing source.",
            AssertionKind.FACT,
            ProvenanceClass.PRIMARY_EVIDENCE,
            ProvenanceClass.PRIMARY_EVIDENCE,
            ("SRC-MISSING",),
            human_verified=True,
        ),
        graph,
    )
    causation = scanner.scan_proposition(
        PropositionInput(
            "P-ADV-CAUSE",
            "X caused Y.",
            AssertionKind.CAUSATION,
            ProvenanceClass.INFERENCE,
            ProvenanceClass.INFERENCE,
            ("SRC-AI-1",),
        ),
        graph,
    )

    assurance, assurance_graph = _assurance_engine()
    date_drift = assurance.evaluate(
        _request(assurance_graph),
        AssuranceSignals(
            originating_dispute_date="2026-08-01",
            derivative_dispute_date="2026-08-04",
        ),
        AssuranceContext("OBJ-ADV-DATE", ("SRC-PRIMARY-1",), observed_at),
    )
    knowledge = assurance.evaluate(
        _request(assurance_graph),
        AssuranceSignals(
            communication_sent=True,
            knowledge_claim_material=True,
            reading_or_knowledge_proven=False,
            silence_treated_as_agreement=True,
        ),
        AssuranceContext("OBJ-ADV-KNOWLEDGE", ("SRC-PRIMARY-1",), observed_at),
    )
    attachment_hash_authority = assurance.evaluate(
        _request(assurance_graph),
        AssuranceSignals(
            referenced_attachment_ids=("ATT-1", "ATT-2"),
            verified_attachment_ids=("ATT-1",),
            hash_present=True,
            hash_scope=None,
            material_authority_claim=True,
            role_and_authority_separately_sourced=False,
        ),
        AssuranceContext("OBJ-ADV-ASSURANCE", ("SRC-PRIMARY-1",), observed_at),
    )
    stale = assurance.evaluate(
        _request(assurance_graph),
        AssuranceSignals(),
        AssuranceContext(
            "OBJ-ADV-STALE",
            ("SRC-PRIMARY-1",),
            observed_at,
            node_version_current=False,
        ),
    )
    ai_term = assurance.evaluate(
        _request(assurance_graph, ai_term=True),
        AssuranceSignals(),
        AssuranceContext("OBJ-ADV-AI-TERM", ("SRC-PRIMARY-1",), observed_at),
    )

    exception_tokens: list[str] = []
    try:
        assurance.evaluate(
            _request(assurance_graph),
            AssuranceSignals(),
            AssuranceContext(
                "OBJ-ADV-AUTHORITY",
                ("SRC-PRIMARY-1",),
                observed_at,
                authority_ceiling="A2",
            ),
        )
    except ValueError:
        exception_tokens.append("AUTHORITY_EXPANSION_REJECTED")
    try:
        scanner.propagate_artifact_contamination(
            (ArtifactNode("A", parent_artifact_ids=("MISSING",)),),
        )
    except ValueError:
        exception_tokens.append("MISSING_PARENT_REJECTED")

    return (
        _result(
            "ADV-ORIGIN-DISCLOSURE",
            ValidationMode.ADVERSARIAL,
            observed=(signal.code for signal in mismatch),
            expected=("ORIGIN_CLASS_DISCLOSURE_MISMATCH",),
        ),
        _result(
            "ADV-UNREGISTERED-SOURCE",
            ValidationMode.ADVERSARIAL,
            observed=(signal.code for signal in missing),
            expected=("UNREGISTERED_PROPOSITION_SOURCE",),
        ),
        _result(
            "ADV-UNSUPPORTED-CAUSATION",
            ValidationMode.ADVERSARIAL,
            observed=(signal.code for signal in causation),
            expected=(
                "CAUSATION_WITHOUT_EXPLICIT_BASIS",
                "CAUSATION_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT",
            ),
        ),
        _result(
            "ADV-DATE-DRIFT",
            ValidationMode.ADVERSARIAL,
            observed=date_drift.detector_hits,
            expected=("D003_DATE_DRIFT",),
        ),
        _result(
            "ADV-KNOWLEDGE-SILENCE",
            ValidationMode.ADVERSARIAL,
            observed=knowledge.detector_hits,
            expected=("D005_TRANSMISSION_TO_KNOWLEDGE", "D006_SILENCE_TO_AGREEMENT"),
        ),
        _result(
            "ADV-ATTACHMENT-HASH-AUTHORITY",
            ValidationMode.ADVERSARIAL,
            observed=attachment_hash_authority.detector_hits,
            expected=("D013_MISSING_ATTACHMENT", "EA07_UNSCOPED_HASH", "EA08_ROLE_AUTHORITY_CONFLATION"),
        ),
        _result(
            "ADV-STALE-NODE",
            ValidationMode.ADVERSARIAL,
            observed=stale.detector_hits,
            expected=("D017_STALE_NODE",),
        ),
        _result(
            "ADV-V1-AI-TERM-VETO",
            ValidationMode.ADVERSARIAL,
            observed=ai_term.blockers,
            expected=("V1_REFERRAL_GATE_NOT_RELEASABLE",),
        ),
        _result(
            "ADV-FAIL-CLOSED-EXCEPTIONS",
            ValidationMode.ADVERSARIAL,
            observed=exception_tokens,
            expected=("AUTHORITY_EXPANSION_REJECTED", "MISSING_PARENT_REJECTED"),
        ),
    )


def _receipt(
    *,
    mode: ValidationMode,
    results: tuple[ValidationCaseResult, ...],
    source_ref: str,
    observed_at: str,
) -> ValidationReceipt:
    payload = [
        {
            "case_id": item.case_id,
            "mode": item.mode.value,
            "passed": item.passed,
            "observed": item.observed,
            "expected": item.expected,
            "prohibited": item.prohibited,
        }
        for item in results
    ]
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    failed = tuple(sorted(item.case_id for item in results if not item.passed))
    return ValidationReceipt(
        receipt_id=f"JFRIE-{mode.value}-VALIDATION-{digest[:16]}",
        mode=mode,
        source_ref=source_ref,
        observed_at=observed_at,
        case_count=len(results),
        passed_count=len(results) - len(failed),
        failed_case_ids=failed,
        external_effect=False,
        authority_ceiling=AUTHORITY_CEILING,
        result_sha256=digest,
    )


def run_shadow_validation(*, source_ref: str, observed_at: str) -> ValidationReceipt:
    return _receipt(
        mode=ValidationMode.SHADOW,
        results=_shadow_cases(observed_at),
        source_ref=source_ref,
        observed_at=observed_at,
    )


def run_adversarial_validation(*, source_ref: str, observed_at: str) -> ValidationReceipt:
    return _receipt(
        mode=ValidationMode.ADVERSARIAL,
        results=_adversarial_cases(observed_at),
        source_ref=source_ref,
        observed_at=observed_at,
    )


__all__ = [
    "FULL_V2_PARITY",
    "VERSION",
    "ValidationCaseResult",
    "ValidationMode",
    "ValidationReceipt",
    "run_adversarial_validation",
    "run_shadow_validation",
]
