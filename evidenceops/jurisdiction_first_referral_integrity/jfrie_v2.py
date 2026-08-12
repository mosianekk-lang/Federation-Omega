"""JFRIE v2 executable assurance foundation.

This is a bounded A1_INTERNAL implementation slice for the canonical JFRIE
v2.0 / EACIA control.  It wraps the existing v1.1 deterministic legal gate,
adds execution-assurance receipts and implements the canonical T001-T012
pollution/regression family.  It deliberately does *not* claim full v2 parity.

Source existence is not execution proof.  High-risk release remains fail-closed
and provider/external effects are outside this module's authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from .jfrie import Decision, GateState, ReferralInput
from .jfrie_v11 import AuditSignals, V11Evaluation, evaluate_v11


VERSION = "2.0.0-foundation.1"
AUTHORITY_CEILING = "A1_INTERNAL"


class V2Decision(str, Enum):
    PASS = "PASS"
    PASS_WITH_LIMITATIONS = "PASS_WITH_LIMITATIONS"
    HOLD_FOR_AUTHORITY = "HOLD_FOR_AUTHORITY"
    HOLD_FOR_SOURCE = "HOLD_FOR_SOURCE"
    REFRAME = "REFRAME"
    SEPARATE_CAUSES = "SEPARATE_CAUSES"
    DO_NOT_FILE = "DO_NOT_FILE"
    LEGAL_RESEARCH_REQUIRED = "LEGAL_RESEARCH_REQUIRED"
    RESYNC_REQUIRED = "RESYNC_REQUIRED"
    QUARANTINED = "QUARANTINED"
    RECALL_REQUIRED = "RECALL_REQUIRED"


class HashScope(str, Enum):
    PROVIDER_NATIVE = "PROVIDER_NATIVE"
    ACQUISITION_BYTES = "ACQUISITION_BYTES"
    DECODED_ATTACHMENT = "DECODED_ATTACHMENT"
    CANONICAL_SEMANTIC = "CANONICAL_SEMANTIC"
    RENDERED_CONTENT = "RENDERED_CONTENT"
    DERIVATIVE_COPY = "DERIVATIVE_COPY"


@dataclass(frozen=True)
class GateExecutionReceipt:
    gate_id: str
    object_id: str
    source_ids: tuple[str, ...]
    test_performed: str
    expected_result: str
    observed_result: str
    state: GateState
    unresolved_limitation: str
    tool_version: str
    executed_at: str
    independent_second_pass_state: str
    release_effect: str

    def validate(self) -> "GateExecutionReceipt":
        required = (
            self.gate_id,
            self.object_id,
            self.test_performed,
            self.expected_result,
            self.observed_result,
            self.unresolved_limitation,
            self.tool_version,
            self.executed_at,
            self.independent_second_pass_state,
            self.release_effect,
        )
        if not all(str(value).strip() for value in required):
            raise ValueError("JFRIE v2 execution receipt is incomplete")
        if not self.source_ids:
            raise ValueError("JFRIE v2 execution receipt requires exact source IDs")
        return self


@dataclass(frozen=True)
class V2ExecutionContext:
    object_id: str
    source_ids: tuple[str, ...]
    executed_at: str
    node_version_current: bool = True
    node_readback_complete: bool = True
    self_tests_pass: bool = True
    independent_second_pass_state: str = "NOT_REQUIRED"
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False

    def validate(self) -> "V2ExecutionContext":
        if not self.object_id.strip() or not self.source_ids or not self.executed_at.strip():
            raise ValueError("JFRIE v2 execution context is incomplete")
        if self.authority_ceiling != AUTHORITY_CEILING or self.external_effect:
            raise ValueError("JFRIE v2 foundation cannot expand authority or create external effects")
        return self


@dataclass(frozen=True)
class V2Signals:
    # T002: apparent repetition must collapse to true independent support.
    apparent_support_count: int = 1
    independent_source_count: int = 1

    # T003: later date drift requires explicit reconciliation.
    originating_dispute_date: str = ""
    derivative_dispute_date: str = ""

    # T004/T005: transmission and silence must not become knowledge/agreement.
    communication_sent: bool = False
    knowledge_claim_material: bool = False
    reading_or_knowledge_proven: bool = False
    silence_treated_as_agreement: bool = False

    # T006/T007/T010/T012 contamination and recall controls.
    excluded_matter_reintroduced: bool = False
    primary_source_invalidates_material_claim: bool = False
    quarantined_claim_reappears: bool = False
    release_previously_occurred: bool = False

    # T009 attachment completeness.
    referenced_attachment_count: int = 0
    verified_attachment_count: int = 0

    # T011 generated-detector promotion remains shadow-gated.
    generated_detector_candidate: bool = False
    detector_shadow_passed: bool = False
    detector_false_positive_rate_acceptable: bool = False

    # EA-07 / EA-08 executable assurance.
    hash_present: bool = False
    hash_scope: HashScope | None = None
    material_authority_claim: bool = False
    role_and_authority_separately_sourced: bool = True


@dataclass(frozen=True)
class V2Evaluation:
    base: V11Evaluation
    receipts: tuple[GateExecutionReceipt, ...]
    detector_hits: tuple[str, ...]
    decision: V2Decision
    release_blocked: bool
    detector_promotion_allowed: bool
    evidence_note: Mapping[str, object]


def _base_decision(decision: Decision) -> V2Decision:
    mapping = {
        Decision.PASS: V2Decision.PASS,
        Decision.PASS_WITH_LIMITATIONS: V2Decision.PASS_WITH_LIMITATIONS,
        Decision.HOLD_FOR_AUTHORITY: V2Decision.HOLD_FOR_AUTHORITY,
        Decision.REFRAME: V2Decision.REFRAME,
        Decision.SEPARATE_CAUSES: V2Decision.SEPARATE_CAUSES,
        Decision.DO_NOT_FILE: V2Decision.DO_NOT_FILE,
        Decision.LEGAL_RESEARCH_REQUIRED: V2Decision.LEGAL_RESEARCH_REQUIRED,
    }
    return mapping.get(decision, V2Decision.DO_NOT_FILE)


def _receipt(
    context: V2ExecutionContext,
    gate_id: str,
    state: GateState,
    observed: str,
    *,
    test: str,
    release_effect: str = "NONE",
    limitation: str = "NONE",
) -> GateExecutionReceipt:
    return GateExecutionReceipt(
        gate_id=gate_id,
        object_id=context.object_id,
        source_ids=context.source_ids,
        test_performed=test,
        expected_result="PASS_OR_EXPLICIT_FAIL_CLOSED",
        observed_result=observed,
        state=state,
        unresolved_limitation=limitation,
        tool_version=f"JFRIE_V2_FOUNDATION/{VERSION}",
        executed_at=context.executed_at,
        independent_second_pass_state=context.independent_second_pass_state,
        release_effect=release_effect,
    ).validate()


def evaluate_v2(
    referral: ReferralInput,
    audit_signals: AuditSignals,
    signals: V2Signals,
    context: V2ExecutionContext,
) -> V2Evaluation:
    """Execute the bounded v2 assurance foundation over the v1.1 baseline."""

    context.validate()
    base = evaluate_v11(referral, audit_signals)
    receipts: list[GateExecutionReceipt] = []
    hits: list[str] = []
    hard_decisions: list[V2Decision] = []
    warnings = False

    # EA-02: every inherited mandatory gate gets an execution receipt.
    for gate in (*base.base.gates, *base.regression_gates):
        effect = "BLOCK" if gate.hard and gate.state == GateState.FAIL else (
            "LIMITATION" if gate.state == GateState.WARN else "NONE"
        )
        receipts.append(_receipt(
            context,
            f"INHERITED:{gate.gate}",
            gate.state,
            gate.reason,
            test="execute inherited JFRIE v1.0/v1.1 gate",
            release_effect=effect,
            limitation="Inherited gate result preserved without semantic upgrade.",
        ))

    # T008 / C092-C094: publication/readback is not node activation.
    node_ok = context.node_version_current and context.node_readback_complete and context.self_tests_pass
    receipts.append(_receipt(
        context,
        "C092_C094_NODE_SYNCHRONISATION",
        GateState.PASS if node_ok else GateState.FAIL,
        "current version/readback/self-tests verified" if node_ok else "node stale, unread, or self-tests unproven",
        test="verify version-pinned activation and node readback",
        release_effect="NONE" if node_ok else "BLOCK",
    ))
    if not node_ok:
        hits.append("D017_STALE_NODE")
        hard_decisions.append(V2Decision.RESYNC_REQUIRED)

    # T002 / C007: repeated derivatives do not multiply independent support.
    repeated_derivative = signals.apparent_support_count > signals.independent_source_count
    if repeated_derivative:
        hits.append("C007_DERIVATIVE_SOURCE_DETECTION")
        warnings = True
    receipts.append(_receipt(
        context,
        "C007_DERIVATIVE_SOURCE_DETECTION",
        GateState.WARN if repeated_derivative else GateState.PASS,
        f"apparent={signals.apparent_support_count}; independent={signals.independent_source_count}",
        test="compare apparent support count with independent-source count",
        release_effect="LIMITATION" if repeated_derivative else "NONE",
        limitation="Repeated derivatives are collapsed to true independent support." if repeated_derivative else "NONE",
    ))

    # T003 / D003: later date drift is release-blocking until explained.
    date_drift = bool(
        signals.originating_dispute_date
        and signals.derivative_dispute_date
        and signals.originating_dispute_date != signals.derivative_dispute_date
    )
    if date_drift:
        hits.append("D003_DATE_DRIFT")
        hard_decisions.append(V2Decision.REFRAME)
    receipts.append(_receipt(
        context,
        "D003_DATE_DRIFT",
        GateState.FAIL if date_drift else GateState.PASS,
        "material date drift detected" if date_drift else "no material originating/derivative date drift supplied",
        test="compare originating and derivative dispute dates",
        release_effect="BLOCK" if date_drift else "NONE",
    ))

    # T004 / D005: sent/delivered is not knowledge.
    knowledge_inflation = (
        signals.communication_sent
        and signals.knowledge_claim_material
        and not signals.reading_or_knowledge_proven
    )
    if knowledge_inflation:
        hits.append("D005_TRANSMISSION_TO_KNOWLEDGE")
        hard_decisions.append(V2Decision.HOLD_FOR_SOURCE)
    receipts.append(_receipt(
        context,
        "D005_TRANSMISSION_TO_KNOWLEDGE",
        GateState.FAIL if knowledge_inflation else GateState.PASS,
        "knowledge asserted from transmission without separate proof" if knowledge_inflation else "no unsupported transmission-to-knowledge escalation",
        test="separate transmission proof from reading/knowledge proof",
        release_effect="BLOCK" if knowledge_inflation else "NONE",
    ))

    # T005 / D006: silence is not agreement.
    if signals.silence_treated_as_agreement:
        hits.append("D006_SILENCE_TO_AGREEMENT")
        hard_decisions.append(V2Decision.REFRAME)
    receipts.append(_receipt(
        context,
        "D006_SILENCE_TO_AGREEMENT",
        GateState.FAIL if signals.silence_treated_as_agreement else GateState.PASS,
        "silence/non-response used as agreement" if signals.silence_treated_as_agreement else "no silence-to-agreement escalation",
        test="test whether non-response is being used as acceptance/agreement",
        release_effect="BLOCK" if signals.silence_treated_as_agreement else "NONE",
    ))

    # T006 / D016: excluded matters cannot be resurrected by copied history.
    if signals.excluded_matter_reintroduced:
        hits.append("D016_EXCLUDED_MATTER_RESURRECTION")
        hard_decisions.append(V2Decision.QUARANTINED)
    receipts.append(_receipt(
        context,
        "D016_EXCLUDED_MATTER_RESURRECTION",
        GateState.FAIL if signals.excluded_matter_reintroduced else GateState.PASS,
        "excluded matter reintroduced" if signals.excluded_matter_reintroduced else "no excluded-matter resurrection",
        test="scan active state for excluded-matter reintroduction",
        release_effect="BLOCK" if signals.excluded_matter_reintroduced else "NONE",
    ))

    # T007/T012 / C075 + C080: invalidated primary source triggers downgrade/recall.
    if signals.primary_source_invalidates_material_claim:
        hits.extend(("C075_AUTOMATIC_DOWNGRADE", "C080_POST_RELEASE_INTEGRITY_MONITOR"))
        hard_decisions.append(
            V2Decision.RECALL_REQUIRED if signals.release_previously_occurred else V2Decision.QUARANTINED
        )
    receipts.append(_receipt(
        context,
        "C075_C080_SOURCE_INVALIDATION",
        GateState.FAIL if signals.primary_source_invalidates_material_claim else GateState.PASS,
        "material claim invalidated by primary source" if signals.primary_source_invalidates_material_claim else "no supplied primary-source invalidation",
        test="test current/released claim against newly authoritative primary source",
        release_effect="RECALL" if signals.primary_source_invalidates_material_claim and signals.release_previously_occurred else (
            "BLOCK" if signals.primary_source_invalidates_material_claim else "NONE"
        ),
    ))

    # T009 / D013: referenced attachments must actually exist and be verified.
    attachments_missing = signals.verified_attachment_count < signals.referenced_attachment_count
    if attachments_missing:
        hits.append("D013_MISSING_ATTACHMENT")
        hard_decisions.append(V2Decision.HOLD_FOR_SOURCE)
    receipts.append(_receipt(
        context,
        "D013_MISSING_ATTACHMENT",
        GateState.FAIL if attachments_missing else GateState.PASS,
        f"referenced={signals.referenced_attachment_count}; verified={signals.verified_attachment_count}",
        test="reconcile referenced and verified attachment counts",
        release_effect="BLOCK" if attachments_missing else "NONE",
    ))

    # T010 / D019: quarantined propositions cannot return through paraphrase.
    if signals.quarantined_claim_reappears:
        hits.append("D019_QUARANTINED_REUSE")
        hard_decisions.append(V2Decision.QUARANTINED)
    receipts.append(_receipt(
        context,
        "D019_QUARANTINED_REUSE",
        GateState.FAIL if signals.quarantined_claim_reappears else GateState.PASS,
        "quarantined claim family reappeared" if signals.quarantined_claim_reappears else "no quarantined-claim reuse supplied",
        test="scan semantic claim family against quarantine state",
        release_effect="BLOCK" if signals.quarantined_claim_reappears else "NONE",
    ))

    # T011 / C098: generated detectors stay shadow-only until measured and safe.
    detector_promotion_allowed = (
        signals.generated_detector_candidate
        and signals.detector_shadow_passed
        and signals.detector_false_positive_rate_acceptable
    )
    detector_hold = signals.generated_detector_candidate and not detector_promotion_allowed
    if detector_hold:
        hits.append("C098_AUTOMATED_CAPABILITY_PROMOTION_HELD")
        warnings = True
    receipts.append(_receipt(
        context,
        "C098_AUTOMATED_CAPABILITY_PROMOTION",
        GateState.WARN if detector_hold else GateState.PASS,
        "generated detector remains shadow-only" if detector_hold else "no unsafe generated-detector promotion",
        test="require shadow pass and acceptable false-positive rate before detector promotion",
        release_effect="NO_PROMOTION" if detector_hold else "NONE",
        limitation="Candidate detector has no release authority until separately promoted." if detector_hold else "NONE",
    ))

    # EA-07: a claimed hash without an explicit byte/semantic scope is invalid.
    hash_ok = (not signals.hash_present) or signals.hash_scope is not None
    if not hash_ok:
        hits.append("EA07_UNSCOPED_HASH")
        hard_decisions.append(V2Decision.HOLD_FOR_SOURCE)
    receipts.append(_receipt(
        context,
        "EA07_HASH_SCOPE",
        GateState.PASS if hash_ok else GateState.FAIL,
        "hash scope explicit or no hash claim made" if hash_ok else "hash present without declared scope",
        test="require explicit hash object/byte scope",
        release_effect="NONE" if hash_ok else "BLOCK",
    ))

    # EA-08: role/title evidence and authority/mandate evidence remain separate claims.
    authority_ok = (not signals.material_authority_claim) or signals.role_and_authority_separately_sourced
    if not authority_ok:
        hits.append("EA08_ROLE_AUTHORITY_CONFLATION")
        hard_decisions.append(V2Decision.HOLD_FOR_AUTHORITY)
    receipts.append(_receipt(
        context,
        "EA08_ROLE_NOT_AUTHORITY",
        GateState.PASS if authority_ok else GateState.FAIL,
        "role and authority separately sourced or no material authority claim" if authority_ok else "role/title is being used as authority proof",
        test="separate role-at-date evidence from act-specific authority evidence",
        release_effect="NONE" if authority_ok else "BLOCK",
    ))

    # Inherited v1/v1.1 hard gates remain absolute.
    inherited = _base_decision(base.decision)
    if base.release_blocked:
        hard_decisions.append(inherited)
    elif base.decision != Decision.PASS:
        warnings = True

    # Strongest fail-closed state wins. Recall/quarantine/source/authority precede reframe.
    precedence = (
        V2Decision.RECALL_REQUIRED,
        V2Decision.QUARANTINED,
        V2Decision.RESYNC_REQUIRED,
        V2Decision.HOLD_FOR_SOURCE,
        V2Decision.HOLD_FOR_AUTHORITY,
        V2Decision.SEPARATE_CAUSES,
        V2Decision.LEGAL_RESEARCH_REQUIRED,
        V2Decision.REFRAME,
        V2Decision.DO_NOT_FILE,
    )
    decision = next((item for item in precedence if item in hard_decisions), None)
    if decision is None:
        decision = V2Decision.PASS_WITH_LIMITATIONS if warnings else V2Decision.PASS

    release_blocked = decision not in {V2Decision.PASS, V2Decision.PASS_WITH_LIMITATIONS}

    # EA-02 self-test: the emitted receipts themselves must be structurally complete.
    for item in receipts:
        item.validate()

    evidence_note = {
        "engine_version": VERSION,
        "authority_ceiling": AUTHORITY_CEILING,
        "object_id": context.object_id,
        "source_ids": context.source_ids,
        "node_sync_state": "ACTIVE" if node_ok else "RESYNC_REQUIRED",
        "execution_receipt_count": len(receipts),
        "detector_hits": tuple(hits),
        "release_decision": decision.value,
        "release_blocked": release_blocked,
        "executable_v2_parity": "FOUNDATION_ONLY_NOT_FULL_PARITY",
        "external_effect": False,
    }

    return V2Evaluation(
        base=base,
        receipts=tuple(receipts),
        detector_hits=tuple(hits),
        decision=decision,
        release_blocked=release_blocked,
        detector_promotion_allowed=detector_promotion_allowed,
        evidence_note=evidence_note,
    )


def release_allowed_v2(evaluation: V2Evaluation) -> bool:
    return (not evaluation.release_blocked) and evaluation.decision in {
        V2Decision.PASS,
        V2Decision.PASS_WITH_LIMITATIONS,
    }
