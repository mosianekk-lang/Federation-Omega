"""Operational truth ingestion for FUSE Capability Truth v1.

This adapter compiles narrative/control-plane claims into EvidenceRef objects without
allowing the transport surface to increase maturity. Bible, ChatBridge, FKPF,
registry and model-memory claims remain bounded by claim semantics and provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from federation.capability_truth_v1 import (
    CapabilityTruthRecord,
    ClaimKind,
    EvidenceRef,
    Maturity,
    propagate_evidence,
)

SCHEMA = "FUSE-CAPABILITY-TRUTH-INGESTION-V1"
VERSION = "1.0.0"


class SourceClass(str, Enum):
    BIBLE_REQUIREMENT = "BIBLE_REQUIREMENT"
    BIBLE_DESIGN = "BIBLE_DESIGN"
    CHATBRIDGE_SUMMARY = "CHATBRIDGE_SUMMARY"
    FKPF_PROPAGATION = "FKPF_PROPAGATION"
    REGISTRY_ENTRY = "REGISTRY_ENTRY"
    MODEL_MEMORY = "MODEL_MEMORY"
    SOURCE_IMPLEMENTATION = "SOURCE_IMPLEMENTATION"
    TEST_RECEIPT = "TEST_RECEIPT"
    SOURCE_ADMISSION_RECEIPT = "SOURCE_ADMISSION_RECEIPT"
    CI_ADMISSION_RECEIPT = "CI_ADMISSION_RECEIPT"
    BINDING_RECEIPT = "BINDING_RECEIPT"
    HOST_RECEIPT = "HOST_RECEIPT"
    RUNTIME_RECEIPT = "RUNTIME_RECEIPT"
    PROVIDER_READBACK = "PROVIDER_READBACK"
    BEHAVIOURAL_RECEIPT = "BEHAVIOURAL_RECEIPT"
    VALUE_RECEIPT = "VALUE_RECEIPT"


SOURCE_TO_CLAIM: Mapping[SourceClass, ClaimKind] = {
    SourceClass.BIBLE_REQUIREMENT: ClaimKind.REQUIREMENT,
    SourceClass.BIBLE_DESIGN: ClaimKind.DESIGN,
    SourceClass.CHATBRIDGE_SUMMARY: ClaimKind.NARRATIVE_SUMMARY,
    SourceClass.FKPF_PROPAGATION: ClaimKind.NARRATIVE_SUMMARY,
    SourceClass.REGISTRY_ENTRY: ClaimKind.REGISTRY_LABEL,
    SourceClass.MODEL_MEMORY: ClaimKind.MODEL_MEMORY,
    SourceClass.SOURCE_IMPLEMENTATION: ClaimKind.IMPLEMENTATION,
    SourceClass.TEST_RECEIPT: ClaimKind.TEST_RESULT,
    SourceClass.SOURCE_ADMISSION_RECEIPT: ClaimKind.SOURCE_ADMISSION,
    SourceClass.CI_ADMISSION_RECEIPT: ClaimKind.CI_ADMISSION,
    SourceClass.BINDING_RECEIPT: ClaimKind.BINDING,
    SourceClass.HOST_RECEIPT: ClaimKind.HOST_RECEIPT,
    SourceClass.RUNTIME_RECEIPT: ClaimKind.RUNTIME_RECEIPT,
    SourceClass.PROVIDER_READBACK: ClaimKind.PROVIDER_READBACK,
    SourceClass.BEHAVIOURAL_RECEIPT: ClaimKind.BEHAVIOURAL_EVIDENCE,
    SourceClass.VALUE_RECEIPT: ClaimKind.VALUE_EVIDENCE,
}

DERIVED_SOURCES = {
    SourceClass.CHATBRIDGE_SUMMARY,
    SourceClass.FKPF_PROPAGATION,
}


@dataclass(frozen=True, slots=True)
class ClaimEnvelope:
    evidence_id: str
    capability_id: str
    source_class: SourceClass
    source_ref: str
    asserted_maturity: Maturity
    derived_from_evidence_id: str = ""
    fresh: bool = True
    independently_verified: bool = False

    def validate(self) -> "ClaimEnvelope":
        if not self.evidence_id.strip() or not self.capability_id.strip() or not self.source_ref.strip():
            raise ValueError("OPERATIONAL_CLAIM_IDENTITY_REQUIRED")
        if self.source_class in DERIVED_SOURCES and not self.derived_from_evidence_id.strip():
            raise ValueError("DERIVED_OPERATIONAL_CLAIM_REQUIRES_PROVENANCE")
        return self


class OperationalTruthCompiler:
    """Compile surface claims into maturity-bounded capability evidence."""

    def compile(
        self,
        envelope: ClaimEnvelope,
        *,
        evidence_index: Mapping[str, EvidenceRef] | None = None,
    ) -> EvidenceRef:
        envelope.validate()
        evidence_index = evidence_index or {}
        claim_kind = SOURCE_TO_CLAIM[envelope.source_class]

        if envelope.derived_from_evidence_id:
            parent = evidence_index.get(envelope.derived_from_evidence_id)
            if parent is None:
                raise ValueError("OPERATIONAL_CLAIM_PROVENANCE_NOT_FOUND")
            if parent.capability_id != envelope.capability_id:
                raise ValueError("OPERATIONAL_CLAIM_PROVENANCE_SUBJECT_MISMATCH")
            derived = propagate_evidence(
                parent,
                evidence_id=envelope.evidence_id,
                source_ref=envelope.source_ref,
                claim_kind=claim_kind,
                declared_maturity=envelope.asserted_maturity,
            )
            return EvidenceRef(
                evidence_id=derived.evidence_id,
                capability_id=derived.capability_id,
                claim_kind=derived.claim_kind,
                source_ref=derived.source_ref,
                declared_maturity=derived.declared_maturity,
                source_maturity=derived.source_maturity,
                fresh=bool(envelope.fresh and parent.fresh),
                independently_verified=False,
                metadata=derived.metadata + (("transport", envelope.source_class.value),),
            )

        return EvidenceRef(
            evidence_id=envelope.evidence_id,
            capability_id=envelope.capability_id,
            claim_kind=claim_kind,
            source_ref=envelope.source_ref,
            declared_maturity=envelope.asserted_maturity,
            fresh=envelope.fresh,
            independently_verified=envelope.independently_verified,
            metadata=(("transport", envelope.source_class.value),),
        ).validate()

    def compile_record(
        self,
        capability_id: str,
        envelopes: Iterable[ClaimEnvelope],
    ) -> CapabilityTruthRecord:
        compiled: list[EvidenceRef] = []
        index: dict[str, EvidenceRef] = {}
        pending = list(envelopes)
        while pending:
            progressed = False
            for envelope in tuple(pending):
                if envelope.capability_id != capability_id:
                    raise ValueError("OPERATIONAL_RECORD_CAPABILITY_MISMATCH")
                parent_id = envelope.derived_from_evidence_id
                if parent_id and parent_id not in index:
                    continue
                item = self.compile(envelope, evidence_index=index)
                compiled.append(item)
                index[item.evidence_id] = item
                pending.remove(envelope)
                progressed = True
            if not progressed:
                raise ValueError("OPERATIONAL_CLAIM_PROVENANCE_CYCLE_OR_MISSING_PARENT")
        return CapabilityTruthRecord(capability_id, tuple(compiled)).validate()


__all__ = [
    "SCHEMA",
    "VERSION",
    "ClaimEnvelope",
    "OperationalTruthCompiler",
    "SOURCE_TO_CLAIM",
    "SourceClass",
]
