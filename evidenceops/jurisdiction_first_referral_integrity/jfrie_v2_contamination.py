"""JFRIE v2.0 / EACIA proposition, prompt and template contamination slice.

This slice is deliberately independent of detector/monitor slice 2 and depends only
on the admitted v2 core. It identifies provenance laundering and propagation risk;
it does not decide legal merits or create external effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import re
from typing import Dict, Iterable, Mapping, Sequence

from .jfrie_v2 import (
    AUTHORITY_CEILING,
    ContaminationState,
    IntegrityGraph,
    ProvenanceClass,
)


CONTAMINATION_SCANNER_VERSION = "2.0.0-contamination-slice-3"
FULL_V2_PARITY = False


class AssertionKind(str, Enum):
    FACT = "FACT"
    OBSERVATION = "OBSERVATION"
    INFERENCE = "INFERENCE"
    CAUSATION = "CAUSATION"
    LEGAL_CONCLUSION = "LEGAL_CONCLUSION"
    ALLEGATION = "ALLEGATION"


class SignalSeverity(str, Enum):
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class ArtifactState(str, Enum):
    CLEAN = "CLEAN"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    TAINTED = "TAINTED"


@dataclass(frozen=True)
class PropositionInput:
    proposition_id: str
    text: str
    asserted_kind: AssertionKind
    origin_class: ProvenanceClass
    disclosed_origin_class: ProvenanceClass
    source_ids: tuple[str, ...]
    inference_basis_ids: tuple[str, ...] = ()
    causation_basis_ids: tuple[str, ...] = ()
    authority_ref: str = ""
    human_verified: bool = False

    def validate(self) -> "PropositionInput":
        if not self.proposition_id.strip() or not self.text.strip():
            raise ValueError("proposition identity/text are required")
        return self


@dataclass(frozen=True)
class PromptTemplateInput:
    template_id: str
    text: str
    origin_class: ProvenanceClass
    source_ref: str
    promotes_unverified_to_verified: bool = False
    suppresses_source_citation: bool = False
    suppresses_adverse_evidence: bool = False
    overrides_release_gate: bool = False

    def validate(self) -> "PromptTemplateInput":
        if not self.template_id.strip() or not self.text.strip() or not self.source_ref.strip():
            raise ValueError("template identity/text/source are required")
        return self


@dataclass(frozen=True)
class ContaminationSignal:
    signal_id: str
    code: str
    severity: SignalSeverity
    object_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class ArtifactNode:
    artifact_id: str
    parent_artifact_ids: tuple[str, ...] = ()
    template_ids: tuple[str, ...] = ()
    state: ArtifactState = ArtifactState.CLEAN

    def validate(self) -> "ArtifactNode":
        if not self.artifact_id.strip():
            raise ValueError("artifact_id is required")
        if self.artifact_id in self.parent_artifact_ids:
            raise ValueError("artifact cannot be its own parent")
        return self


@dataclass(frozen=True)
class ArtifactContaminationResult:
    states: Mapping[str, ArtifactState]
    contaminated_roots: tuple[str, ...]
    affected_descendants: tuple[str, ...]
    unaffected_artifacts: tuple[str, ...]


class JfrieV2ContaminationScanner:
    """Fail-closed laundering and prompt/template contamination scanner."""

    weak_fact_classes = {
        ProvenanceClass.AI_ORIGIN,
        ProvenanceClass.DERIVATIVE_SUMMARY,
        ProvenanceClass.INFERENCE,
        ProvenanceClass.UNVERIFIED,
        ProvenanceClass.CONTRADICTED,
        ProvenanceClass.QUARANTINED,
    }

    primary_fact_classes = {
        ProvenanceClass.PRIMARY_EVIDENCE,
        ProvenanceClass.OFFICIAL_AUTHORITY,
        ProvenanceClass.VERIFIED_SECONDARY,
    }

    _prompt_review_patterns: tuple[tuple[str, str], ...] = (
        ("IGNORE_PRIOR_CONTROL", r"\bignore\s+(all\s+)?(previous|prior)\b"),
        ("ASSUME_TRUE", r"\b(assume|treat)\s+.{0,30}\b(true|verified|proved)\b"),
        ("SUPPRESS_CITATION_LANGUAGE", r"\b(no|without)\s+(source|citation|provenance)\b"),
        ("BYPASS_GATE_LANGUAGE", r"\b(bypass|skip|override)\s+.{0,30}\b(gate|validation|verification|approval)\b"),
    )

    @staticmethod
    def _signal_id(code: str, object_ids: Iterable[str]) -> str:
        material = code + "|" + "|".join(sorted(object_ids))
        return "JFRIE-C-" + sha256(material.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _signal(
        code: str,
        severity: SignalSeverity,
        object_ids: Sequence[str],
        detail: str,
    ) -> ContaminationSignal:
        ids = tuple(object_ids)
        return ContaminationSignal(
            JfrieV2ContaminationScanner._signal_id(code, ids),
            code,
            severity,
            ids,
            detail,
        )

    def scan_proposition(
        self,
        proposition: PropositionInput,
        graph: IntegrityGraph,
    ) -> tuple[ContaminationSignal, ...]:
        proposition.validate()
        signals: list[ContaminationSignal] = []
        missing_sources = tuple(
            sorted(source_id for source_id in proposition.source_ids if source_id not in graph.sources)
        )
        if missing_sources:
            signals.append(
                self._signal(
                    "UNREGISTERED_PROPOSITION_SOURCE",
                    SignalSeverity.BLOCK,
                    (proposition.proposition_id, *missing_sources),
                    "proposition references unregistered source provenance",
                )
            )

        if proposition.origin_class is not proposition.disclosed_origin_class:
            signals.append(
                self._signal(
                    "ORIGIN_CLASS_DISCLOSURE_MISMATCH",
                    SignalSeverity.BLOCK,
                    (proposition.proposition_id,),
                    f"actual={proposition.origin_class.value}; disclosed={proposition.disclosed_origin_class.value}",
                )
            )

        registered_classes = {
            graph.sources[source_id].provenance_class
            for source_id in proposition.source_ids
            if source_id in graph.sources
        }
        has_primary_support = bool(registered_classes & self.primary_fact_classes)

        if proposition.asserted_kind is AssertionKind.FACT:
            if proposition.origin_class in self.weak_fact_classes:
                signals.append(
                    self._signal(
                        "INFERENCE_OR_DERIVATIVE_LAUNDERED_AS_FACT",
                        SignalSeverity.BLOCK,
                        (proposition.proposition_id,),
                        "weak/derivative/AI/inference origin cannot be presented as verified fact by label alone",
                    )
                )
            if not has_primary_support:
                signals.append(
                    self._signal(
                        "FACT_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT",
                        SignalSeverity.BLOCK,
                        (proposition.proposition_id, *proposition.source_ids),
                        "fact assertion lacks primary/official/verified-secondary source support",
                    )
                )

        if proposition.asserted_kind is AssertionKind.INFERENCE:
            if not proposition.inference_basis_ids:
                signals.append(
                    self._signal(
                        "INFERENCE_WITHOUT_EXPLICIT_BASIS",
                        SignalSeverity.BLOCK,
                        (proposition.proposition_id,),
                        "inference requires explicit proposition/source basis",
                    )
                )

        if proposition.asserted_kind is AssertionKind.CAUSATION:
            if not proposition.causation_basis_ids:
                signals.append(
                    self._signal(
                        "CAUSATION_WITHOUT_EXPLICIT_BASIS",
                        SignalSeverity.BLOCK,
                        (proposition.proposition_id,),
                        "causation assertion requires explicit causal basis",
                    )
                )
            if not has_primary_support:
                signals.append(
                    self._signal(
                        "CAUSATION_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT",
                        SignalSeverity.BLOCK,
                        (proposition.proposition_id, *proposition.source_ids),
                        "causation cannot be promoted solely from derivative/AI/inference support",
                    )
                )

        if proposition.asserted_kind is AssertionKind.LEGAL_CONCLUSION and not proposition.authority_ref.strip():
            signals.append(
                self._signal(
                    "LEGAL_CONCLUSION_WITHOUT_AUTHORITY_PROVENANCE",
                    SignalSeverity.BLOCK,
                    (proposition.proposition_id,),
                    "legal conclusion requires explicit current/applicable authority provenance",
                )
            )

        if proposition.origin_class is ProvenanceClass.AI_ORIGIN and not proposition.human_verified:
            signals.append(
                self._signal(
                    "AI_ORIGIN_REQUIRES_HUMAN_OR_INDEPENDENT_VERIFICATION",
                    SignalSeverity.REVIEW,
                    (proposition.proposition_id,),
                    "AI-origin text remains AI-origin and requires independent/human verification before high-confidence use",
                )
            )
        return tuple(signals)

    def scan_template(self, template: PromptTemplateInput) -> tuple[ContaminationSignal, ...]:
        template.validate()
        signals: list[ContaminationSignal] = []
        hard_flags = (
            ("TEMPLATE_PROMOTES_UNVERIFIED_TO_VERIFIED", template.promotes_unverified_to_verified),
            ("TEMPLATE_SUPPRESSES_SOURCE_CITATION", template.suppresses_source_citation),
            ("TEMPLATE_SUPPRESSES_ADVERSE_EVIDENCE", template.suppresses_adverse_evidence),
            ("TEMPLATE_OVERRIDES_RELEASE_GATE", template.overrides_release_gate),
        )
        for code, enabled in hard_flags:
            if enabled:
                signals.append(
                    self._signal(
                        code,
                        SignalSeverity.BLOCK,
                        (template.template_id,),
                        "explicit template control would weaken JFRIE proof/release integrity",
                    )
                )
        for code, pattern in self._prompt_review_patterns:
            if re.search(pattern, template.text, flags=re.IGNORECASE | re.DOTALL):
                signals.append(
                    self._signal(
                        f"PROMPT_LANGUAGE_REVIEW:{code}",
                        SignalSeverity.REVIEW,
                        (template.template_id,),
                        "heuristic prompt-language match requires review; text match alone is not a misconduct finding",
                    )
                )
        unique = {signal.signal_id: signal for signal in signals}
        return tuple(unique[key] for key in sorted(unique))

    def scan_propositions(
        self,
        propositions: Sequence[PropositionInput],
        graph: IntegrityGraph,
    ) -> tuple[ContaminationSignal, ...]:
        signals = [
            signal
            for proposition in propositions
            for signal in self.scan_proposition(proposition, graph)
        ]
        unique = {signal.signal_id: signal for signal in signals}
        return tuple(unique[key] for key in sorted(unique))

    def propagate_artifact_contamination(
        self,
        artifacts: Sequence[ArtifactNode],
        *,
        contaminated_template_ids: Iterable[str] = (),
        directly_tainted_artifact_ids: Iterable[str] = (),
    ) -> ArtifactContaminationResult:
        nodes: Dict[str, ArtifactNode] = {}
        for artifact in artifacts:
            artifact.validate()
            if artifact.artifact_id in nodes:
                raise ValueError("duplicate artifact identity")
            nodes[artifact.artifact_id] = artifact
        for artifact in artifacts:
            missing = [parent for parent in artifact.parent_artifact_ids if parent not in nodes]
            if missing:
                raise ValueError("artifact references missing parent(s): " + ",".join(sorted(missing)))

        contaminated_templates = set(contaminated_template_ids)
        directly_tainted = set(directly_tainted_artifact_ids)
        unknown_tainted = sorted(directly_tainted - set(nodes))
        if unknown_tainted:
            raise ValueError("unknown directly tainted artifact(s): " + ",".join(unknown_tainted))

        states: Dict[str, ArtifactState] = {
            artifact_id: node.state for artifact_id, node in nodes.items()
        }
        roots: set[str] = set()
        for artifact_id, node in nodes.items():
            if artifact_id in directly_tainted or set(node.template_ids) & contaminated_templates:
                states[artifact_id] = ArtifactState.TAINTED
                roots.add(artifact_id)

        changed = True
        while changed:
            changed = False
            for artifact_id, node in nodes.items():
                if states[artifact_id] is ArtifactState.TAINTED:
                    continue
                parent_states = {states[parent] for parent in node.parent_artifact_ids}
                if ArtifactState.TAINTED in parent_states or ArtifactState.NEEDS_REVIEW in parent_states:
                    if states[artifact_id] is not ArtifactState.NEEDS_REVIEW:
                        states[artifact_id] = ArtifactState.NEEDS_REVIEW
                        changed = True

        affected = tuple(
            sorted(
                artifact_id
                for artifact_id, state in states.items()
                if state is not ArtifactState.CLEAN and artifact_id not in roots
            )
        )
        unaffected = tuple(
            sorted(
                artifact_id
                for artifact_id, state in states.items()
                if state is ArtifactState.CLEAN
            )
        )
        return ArtifactContaminationResult(
            states=dict(sorted(states.items())),
            contaminated_roots=tuple(sorted(roots)),
            affected_descendants=affected,
            unaffected_artifacts=unaffected,
        )

    @staticmethod
    def blocking_signals(signals: Sequence[ContaminationSignal]) -> tuple[ContaminationSignal, ...]:
        return tuple(signal for signal in signals if signal.severity is SignalSeverity.BLOCK)


__all__ = [
    "ARTIFACT_STATE" if False else "ArtifactState",
    "CONTAMINATION_SCANNER_VERSION",
    "FULL_V2_PARITY",
    "ArtifactContaminationResult",
    "ArtifactNode",
    "AssertionKind",
    "ContaminationSignal",
    "JfrieV2ContaminationScanner",
    "PromptTemplateInput",
    "PropositionInput",
    "SignalSeverity",
]
