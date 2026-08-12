"""Additive JFRIE v2 execution-assurance extension.

This module reuses the admitted JFRIE v2 core-parity slice and only adds
assurance controls that remain outside that slice: date-drift, transmission vs
knowledge, silence vs agreement, attachment completeness, version-current node
activation, scoped hashes, role-vs-authority separation, generated-detector
shadow gating, and per-control execution receipts.

It can narrow a core release decision but can never expand it. A1 internal;
no external effect, filing, evidence mutation, provider action or doctrine
self-promotion is authorized here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .jfrie_v2 import JfrieV2Core, ReleaseDecisionV2, ReleaseRequest, ReleaseState


VERSION = "2.0.0-assurance-extension-1"
AUTHORITY_CEILING = "A1_INTERNAL"


class AssuranceState(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class HashScope(str, Enum):
    PROVIDER_NATIVE = "PROVIDER_NATIVE"
    ACQUISITION_BYTES = "ACQUISITION_BYTES"
    DECODED_ATTACHMENT = "DECODED_ATTACHMENT"
    CANONICAL_SEMANTIC = "CANONICAL_SEMANTIC"
    RENDERED_CONTENT = "RENDERED_CONTENT"
    DERIVATIVE_COPY = "DERIVATIVE_COPY"


@dataclass(frozen=True)
class AssuranceContext:
    object_id: str
    source_ids: tuple[str, ...]
    executed_at: str
    node_version_current: bool = True
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False

    def validate(self) -> "AssuranceContext":
        if not self.object_id.strip() or not self.source_ids or not self.executed_at.strip():
            raise ValueError("assurance context requires object, exact sources and execution time")
        if self.authority_ceiling != AUTHORITY_CEILING or self.external_effect:
            raise ValueError("JFRIE v2 assurance cannot expand authority or create external effects")
        return self


@dataclass(frozen=True)
class AssuranceSignals:
    originating_dispute_date: str = ""
    derivative_dispute_date: str = ""

    communication_sent: bool = False
    knowledge_claim_material: bool = False
    reading_or_knowledge_proven: bool = False
    silence_treated_as_agreement: bool = False

    referenced_attachment_ids: tuple[str, ...] = ()
    verified_attachment_ids: tuple[str, ...] = ()

    hash_present: bool = False
    hash_scope: HashScope | None = None

    material_authority_claim: bool = False
    role_and_authority_separately_sourced: bool = True

    generated_detector_candidate: bool = False
    detector_shadow_passed: bool = False
    detector_false_positive_rate_acceptable: bool = False


@dataclass(frozen=True)
class AssuranceReceipt:
    control_id: str
    object_id: str
    source_ids: tuple[str, ...]
    test_performed: str
    expected_result: str
    observed_result: str
    state: AssuranceState
    unresolved_limitation: str
    tool_version: str
    executed_at: str
    release_effect: str

    def validate(self) -> "AssuranceReceipt":
        required = (
            self.control_id,
            self.object_id,
            self.test_performed,
            self.expected_result,
            self.observed_result,
            self.unresolved_limitation,
            self.tool_version,
            self.executed_at,
            self.release_effect,
        )
        if not all(str(value).strip() for value in required) or not self.source_ids:
            raise ValueError("incomplete JFRIE v2 assurance execution receipt")
        return self


@dataclass(frozen=True)
class AssuranceEvaluation:
    core: ReleaseDecisionV2
    allowed: bool
    state: ReleaseState
    blockers: tuple[str, ...]
    detector_hits: tuple[str, ...]
    receipts: tuple[AssuranceReceipt, ...]
    detector_promotion_allowed: bool


def _receipt(
    context: AssuranceContext,
    control_id: str,
    state: AssuranceState,
    observed: str,
    *,
    test: str,
    release_effect: str,
    limitation: str = "NONE",
) -> AssuranceReceipt:
    return AssuranceReceipt(
        control_id=control_id,
        object_id=context.object_id,
        source_ids=context.source_ids,
        test_performed=test,
        expected_result="PASS_OR_EXPLICIT_FAIL_CLOSED",
        observed_result=observed,
        state=state,
        unresolved_limitation=limitation,
        tool_version=f"JFRIE_V2_ASSURANCE/{VERSION}",
        executed_at=context.executed_at,
        release_effect=release_effect,
    ).validate()


class JfrieV2Assurance:
    """Fail-closed assurance wrapper around the admitted JFRIE v2 core."""

    def __init__(self, core: JfrieV2Core | None = None) -> None:
        self.core = core or JfrieV2Core()

    def evaluate(
        self,
        request: ReleaseRequest,
        signals: AssuranceSignals,
        context: AssuranceContext,
    ) -> AssuranceEvaluation:
        context.validate()
        core = self.core.evaluate_release(request)
        blockers = list(core.blockers)
        hits: list[str] = []
        receipts: list[AssuranceReceipt] = []

        receipts.append(_receipt(
            context,
            "EA02_CORE_RELEASE_EXECUTION",
            AssuranceState.PASS if core.allowed else AssuranceState.FAIL,
            f"core_state={core.state.value}; blockers={len(core.blockers)}",
            test="execute admitted JFRIE v2 core release firewall",
            release_effect="NONE" if core.allowed else "BLOCK",
            limitation="Core blockers are preserved verbatim; assurance may not clear them.",
        ))

        if not context.node_version_current:
            blockers.append("D017_STALE_NODE_VERSION")
            hits.append("D017_STALE_NODE")
        receipts.append(_receipt(
            context,
            "D017_STALE_NODE",
            AssuranceState.PASS if context.node_version_current else AssuranceState.FAIL,
            "current node version verified" if context.node_version_current else "node version stale or unverified",
            test="verify version-current node activation separately from stored readback",
            release_effect="NONE" if context.node_version_current else "BLOCK",
        ))

        date_drift = bool(
            signals.originating_dispute_date
            and signals.derivative_dispute_date
            and signals.originating_dispute_date != signals.derivative_dispute_date
        )
        if date_drift:
            blockers.append("D003_DATE_DRIFT_RECONCILIATION_REQUIRED")
            hits.append("D003_DATE_DRIFT")
        receipts.append(_receipt(
            context,
            "D003_DATE_DRIFT",
            AssuranceState.FAIL if date_drift else AssuranceState.PASS,
            "originating/derivative date conflict" if date_drift else "no supplied material date drift",
            test="compare originating-instrument date with derivative date",
            release_effect="BLOCK" if date_drift else "NONE",
        ))

        knowledge_inflation = (
            signals.communication_sent
            and signals.knowledge_claim_material
            and not signals.reading_or_knowledge_proven
        )
        if knowledge_inflation:
            blockers.append("D005_TRANSMISSION_DOES_NOT_PROVE_KNOWLEDGE")
            hits.append("D005_TRANSMISSION_TO_KNOWLEDGE")
        receipts.append(_receipt(
            context,
            "D005_TRANSMISSION_TO_KNOWLEDGE",
            AssuranceState.FAIL if knowledge_inflation else AssuranceState.PASS,
            "material knowledge inferred from transmission without proof" if knowledge_inflation else "no unsupported transmission-to-knowledge inference",
            test="separate transmission/delivery evidence from reading/knowledge evidence",
            release_effect="BLOCK" if knowledge_inflation else "NONE",
        ))

        if signals.silence_treated_as_agreement:
            blockers.append("D006_SILENCE_DOES_NOT_PROVE_AGREEMENT")
            hits.append("D006_SILENCE_TO_AGREEMENT")
        receipts.append(_receipt(
            context,
            "D006_SILENCE_TO_AGREEMENT",
            AssuranceState.FAIL if signals.silence_treated_as_agreement else AssuranceState.PASS,
            "silence/non-response used as agreement" if signals.silence_treated_as_agreement else "no silence-to-agreement escalation",
            test="test whether silence is being used as acceptance/agreement",
            release_effect="BLOCK" if signals.silence_treated_as_agreement else "NONE",
        ))

        referenced = set(signals.referenced_attachment_ids)
        verified = set(signals.verified_attachment_ids)
        missing = tuple(sorted(referenced - verified))
        if missing:
            blockers.append("D013_MISSING_ATTACHMENT:" + ",".join(missing))
            hits.append("D013_MISSING_ATTACHMENT")
        receipts.append(_receipt(
            context,
            "D013_MISSING_ATTACHMENT",
            AssuranceState.FAIL if missing else AssuranceState.PASS,
            "missing=" + ",".join(missing) if missing else "all referenced attachment IDs verified or none referenced",
            test="reconcile exact referenced attachment IDs against verified attachment IDs",
            release_effect="BLOCK" if missing else "NONE",
        ))

        hash_ok = (not signals.hash_present) or signals.hash_scope is not None
        if not hash_ok:
            blockers.append("EA07_UNSCOPED_HASH")
            hits.append("EA07_UNSCOPED_HASH")
        receipts.append(_receipt(
            context,
            "EA07_HASH_SCOPE",
            AssuranceState.PASS if hash_ok else AssuranceState.FAIL,
            "hash scope explicit or no hash claim" if hash_ok else "hash present without scope",
            test="require explicit hash scope",
            release_effect="NONE" if hash_ok else "BLOCK",
        ))

        authority_ok = (not signals.material_authority_claim) or signals.role_and_authority_separately_sourced
        if not authority_ok:
            blockers.append("EA08_ROLE_NOT_AUTHORITY")
            hits.append("EA08_ROLE_AUTHORITY_CONFLATION")
        receipts.append(_receipt(
            context,
            "EA08_ROLE_NOT_AUTHORITY",
            AssuranceState.PASS if authority_ok else AssuranceState.FAIL,
            "role and authority separately sourced or no material authority claim" if authority_ok else "role/title used as authority proof",
            test="separate role-at-date evidence from act-specific authority evidence",
            release_effect="NONE" if authority_ok else "BLOCK",
        ))

        detector_promotion_allowed = (
            signals.generated_detector_candidate
            and signals.detector_shadow_passed
            and signals.detector_false_positive_rate_acceptable
        )
        detector_held = signals.generated_detector_candidate and not detector_promotion_allowed
        if detector_held:
            hits.append("C098_AUTOMATED_CAPABILITY_PROMOTION_HELD")
        receipts.append(_receipt(
            context,
            "C098_AUTOMATED_CAPABILITY_PROMOTION",
            AssuranceState.WARN if detector_held else AssuranceState.PASS,
            "candidate remains shadow-only" if detector_held else "no unsafe detector promotion",
            test="require shadow pass plus acceptable false-positive rate before generated-detector promotion",
            release_effect="NO_PROMOTION" if detector_held else "NONE",
            limitation="Detector promotion is separate from artifact release authority." if detector_held else "NONE",
        ))

        unique_blockers = tuple(dict.fromkeys(blockers))
        allowed = core.allowed and not any(item not in core.blockers for item in unique_blockers)
        state = ReleaseState.RELEASE_CLEARED if allowed else ReleaseState.HOLD

        return AssuranceEvaluation(
            core=core,
            allowed=allowed,
            state=state,
            blockers=unique_blockers,
            detector_hits=tuple(hits),
            receipts=tuple(receipts),
            detector_promotion_allowed=detector_promotion_allowed,
        )


__all__ = [
    "AUTHORITY_CEILING",
    "VERSION",
    "AssuranceContext",
    "AssuranceEvaluation",
    "AssuranceReceipt",
    "AssuranceSignals",
    "AssuranceState",
    "HashScope",
    "JfrieV2Assurance",
]
