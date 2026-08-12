"""JFRIE v2.0 / EACIA detector and post-release monitoring slice.

Builds on the admitted v2 core parity slice. Findings are deterministic review or
block signals; they do not decide legal merits. Release remains fail-closed and
provider/external effects remain outside this A1-internal module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Dict, Iterable, Mapping, Sequence

from .jfrie_v2 import (
    AUTHORITY_CEILING,
    ClaimRecord,
    ContaminationState,
    IntegrityGraph,
    JfrieV2Core,
    ProvenanceClass,
    ReleaseDecisionV2,
    ReleaseRequest,
    ReleaseState,
)


DETECTOR_VERSION = "2.0.0-detector-monitor-slice-2"
FULL_V2_PARITY = False


class FindingSeverity(str, Enum):
    INFO = "INFO"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class PostReleaseState(str, Enum):
    STABLE = "STABLE"
    RECALL_REQUIRED = "RECALL_REQUIRED"


@dataclass(frozen=True)
class DetectorFinding:
    finding_id: str
    code: str
    severity: FindingSeverity
    object_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class DetectorReport:
    graph_digest: str
    findings: tuple[DetectorFinding, ...]
    generated_at: str
    detector_version: str = DETECTOR_VERSION
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False

    @property
    def blocking(self) -> tuple[DetectorFinding, ...]:
        return tuple(item for item in self.findings if item.severity is FindingSeverity.BLOCK)

    @property
    def reviews(self) -> tuple[DetectorFinding, ...]:
        return tuple(item for item in self.findings if item.severity is FindingSeverity.REVIEW)


@dataclass(frozen=True)
class SourceVersionObservation:
    logical_source_id: str
    version_ref: str
    content_fingerprint: str
    observed_at: str
    authoritative: bool = True

    def validate(self) -> "SourceVersionObservation":
        if not all(
            str(value).strip()
            for value in (
                self.logical_source_id,
                self.version_ref,
                self.content_fingerprint,
                self.observed_at,
            )
        ):
            raise ValueError("source-version observation is incomplete")
        return self


@dataclass(frozen=True)
class EvidencePacket:
    packet_id: str
    expected_members: tuple[str, ...]
    present_members: tuple[str, ...]
    required: bool = True

    def validate(self) -> "EvidencePacket":
        if not self.packet_id.strip():
            raise ValueError("packet_id is required")
        if not self.expected_members:
            raise ValueError("packet expected-members cannot be empty")
        return self

    @property
    def missing_members(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.expected_members) - set(self.present_members)))


@dataclass(frozen=True)
class ReleaseSnapshot:
    release_id: str
    matter_id: str
    claim_ids: tuple[str, ...]
    claim_fingerprints: tuple[tuple[str, str], ...]
    source_fingerprints: tuple[tuple[str, str], ...]
    state_digest: str
    snapshot_ref: str
    captured_at: str


@dataclass(frozen=True)
class PostReleaseDecision:
    state: PostReleaseState
    recall_required: bool
    changed_claim_ids: tuple[str, ...]
    changed_source_ids: tuple[str, ...]
    prior_digest: str
    current_digest: str
    release_id: str
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False


class JfrieV2DetectorEngine:
    insufficient_release_support = {
        ProvenanceClass.AI_ORIGIN,
        ProvenanceClass.DERIVATIVE_SUMMARY,
        ProvenanceClass.INFERENCE,
        ProvenanceClass.UNVERIFIED,
        ProvenanceClass.CONTRADICTED,
        ProvenanceClass.QUARANTINED,
    }

    @staticmethod
    def _canonical(value: object) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _digest(value: object) -> str:
        return sha256(JfrieV2DetectorEngine._canonical(value)).hexdigest()

    @staticmethod
    def normalize_text(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", text.lower()))

    @classmethod
    def semantic_fingerprint(cls, text: str) -> str:
        return sha256(cls.normalize_text(text).encode("utf-8")).hexdigest()

    @classmethod
    def _tokens(cls, text: str) -> set[str]:
        return set(cls.normalize_text(text).split())

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left and not right:
            return 1.0
        union = left | right
        return 0.0 if not union else len(left & right) / len(union)

    @classmethod
    def graph_digest(cls, graph: IntegrityGraph) -> str:
        source_rows = [
            {
                "source_id": item.source_id,
                "provenance_class": item.provenance_class.value,
                "authenticated": item.authenticated,
                "parent_source_id": item.parent_source_id or "",
            }
            for item in sorted(graph.sources.values(), key=lambda value: value.source_id)
        ]
        claim_rows = [
            {
                "claim_id": item.claim_id,
                "exact_text": item.exact_text,
                "normalized_text": item.normalized_text,
                "matter_id": item.matter_id,
                "source_ids": sorted(item.source_ids),
                "status": item.evidence_status.value,
                "dependencies": sorted(item.dependency_ids),
                "contradictions": sorted(item.contradiction_ids),
                "contamination": item.contamination_state.value,
                "release_eligibility": item.release_eligibility,
                "authority_ref": item.authority_ref,
            }
            for item in sorted(graph.claims.values(), key=lambda value: value.claim_id)
        ]
        return cls._digest({"sources": source_rows, "claims": claim_rows})

    @staticmethod
    def _finding_id(code: str, object_ids: Iterable[str]) -> str:
        material = code + "|" + "|".join(sorted(object_ids))
        return "JFRIE-F-" + sha256(material.encode("utf-8")).hexdigest()[:16]

    def scan_semantic_duplicates(
        self,
        graph: IntegrityGraph,
        *,
        threshold: float = 0.85,
    ) -> tuple[DetectorFinding, ...]:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0,1]")
        findings: list[DetectorFinding] = []
        values = sorted(graph.claims.values(), key=lambda item: item.claim_id)
        for index, left in enumerate(values):
            for right in values[index + 1 :]:
                if left.matter_id != right.matter_id:
                    continue
                left_fp = self.semantic_fingerprint(left.normalized_text)
                right_fp = self.semantic_fingerprint(right.normalized_text)
                object_ids = (left.claim_id, right.claim_id)
                if left_fp == right_fp:
                    code = "SEMANTIC_DUPLICATE_EXACT"
                    detail = "normalized claim fingerprints are identical"
                else:
                    similarity = self._jaccard(
                        self._tokens(left.normalized_text),
                        self._tokens(right.normalized_text),
                    )
                    if similarity < threshold:
                        continue
                    code = "SEMANTIC_PARAPHRASE_CANDIDATE"
                    detail = f"token_jaccard={similarity:.6f}; review before treating as independent support"
                findings.append(
                    DetectorFinding(
                        self._finding_id(code, object_ids),
                        code,
                        FindingSeverity.REVIEW,
                        tuple(sorted(object_ids)),
                        detail,
                    )
                )
        return tuple(findings)

    def scan_dependency_cycles(self, graph: IntegrityGraph) -> tuple[DetectorFinding, ...]:
        findings: list[DetectorFinding] = []
        adjacency: Dict[str, tuple[str, ...]] = {}
        for claim in graph.claims.values():
            adjacency[claim.claim_id] = tuple(claim.dependency_ids)
            for dependency_id in claim.dependency_ids:
                if dependency_id not in graph.claims:
                    findings.append(
                        DetectorFinding(
                            self._finding_id(
                                "MISSING_DEPENDENCY_CLAIM",
                                (claim.claim_id, dependency_id),
                            ),
                            "MISSING_DEPENDENCY_CLAIM",
                            FindingSeverity.BLOCK,
                            (claim.claim_id, dependency_id),
                            "claim dependency points to an unregistered claim",
                        )
                    )

        visiting: list[str] = []
        visited: set[str] = set()
        cycles: set[tuple[str, ...]] = set()

        def visit(node: str) -> None:
            if node in visiting:
                start = visiting.index(node)
                cycles.add(tuple(sorted(set(visiting[start:]))))
                return
            if node in visited or node not in adjacency:
                return
            visiting.append(node)
            for child in adjacency[node]:
                visit(child)
            visiting.pop()
            visited.add(node)

        for claim_id in sorted(adjacency):
            visit(claim_id)
        for cycle in sorted(cycles):
            findings.append(
                DetectorFinding(
                    self._finding_id("CLAIM_DEPENDENCY_CYCLE", cycle),
                    "CLAIM_DEPENDENCY_CYCLE",
                    FindingSeverity.BLOCK,
                    cycle,
                    "circular claim support/dependency detected",
                )
            )
        return tuple(findings)

    def scan_copy_inflation(self, graph: IntegrityGraph) -> tuple[DetectorFinding, ...]:
        findings: list[DetectorFinding] = []
        for claim in sorted(graph.claims.values(), key=lambda item: item.claim_id):
            if len(claim.source_ids) < 2:
                continue
            roots = graph.independent_source_roots(claim.source_ids)
            if len(roots) < len(claim.source_ids):
                findings.append(
                    DetectorFinding(
                        self._finding_id(
                            "COPY_CORROBORATION_INFLATION_RISK",
                            (claim.claim_id, *claim.source_ids),
                        ),
                        "COPY_CORROBORATION_INFLATION_RISK",
                        FindingSeverity.REVIEW,
                        (claim.claim_id, *tuple(sorted(claim.source_ids))),
                        f"{len(claim.source_ids)} carriers collapse to {len(roots)} independent source root(s)",
                    )
                )
        return tuple(findings)

    def scan_release_support(self, graph: IntegrityGraph) -> tuple[DetectorFinding, ...]:
        findings: list[DetectorFinding] = []
        for claim in sorted(graph.claims.values(), key=lambda item: item.claim_id):
            if not claim.release_eligibility or not claim.source_ids:
                continue
            classes = {graph.sources[source_id].provenance_class for source_id in claim.source_ids}
            if classes and classes.issubset(self.insufficient_release_support):
                findings.append(
                    DetectorFinding(
                        self._finding_id(
                            "RELEASE_ELIGIBLE_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT",
                            (claim.claim_id, *claim.source_ids),
                        ),
                        "RELEASE_ELIGIBLE_WITHOUT_PRIMARY_OR_VERIFIED_SUPPORT",
                        FindingSeverity.BLOCK,
                        (claim.claim_id, *tuple(sorted(claim.source_ids))),
                        "release-eligible claim is supported only by AI/derivative/inference/unverified classes",
                    )
                )
        return tuple(findings)

    def scan_packets(self, packets: Sequence[EvidencePacket]) -> tuple[DetectorFinding, ...]:
        findings: list[DetectorFinding] = []
        for packet in packets:
            packet.validate()
            missing = packet.missing_members
            if not missing:
                continue
            severity = FindingSeverity.BLOCK if packet.required else FindingSeverity.REVIEW
            code = "REQUIRED_EVIDENCE_PACKET_INCOMPLETE" if packet.required else "OPTIONAL_EVIDENCE_PACKET_INCOMPLETE"
            findings.append(
                DetectorFinding(
                    self._finding_id(code, (packet.packet_id, *missing)),
                    code,
                    severity,
                    (packet.packet_id, *missing),
                    "missing packet member(s): " + ",".join(missing),
                )
            )
        return tuple(findings)

    def scan_source_versions(
        self,
        observations: Sequence[SourceVersionObservation],
    ) -> tuple[DetectorFinding, ...]:
        findings: list[DetectorFinding] = []
        by_version: Dict[tuple[str, str], list[SourceVersionObservation]] = {}
        by_logical: Dict[str, list[SourceVersionObservation]] = {}
        for observation in observations:
            observation.validate()
            if not observation.authoritative:
                continue
            by_version.setdefault(
                (observation.logical_source_id, observation.version_ref), []
            ).append(observation)
            by_logical.setdefault(observation.logical_source_id, []).append(observation)

        for (logical_id, version_ref), values in sorted(by_version.items()):
            fingerprints = {item.content_fingerprint for item in values}
            if len(fingerprints) > 1:
                findings.append(
                    DetectorFinding(
                        self._finding_id(
                            "SOURCE_VERSION_FINGERPRINT_CONFLICT",
                            (logical_id, version_ref, *sorted(fingerprints)),
                        ),
                        "SOURCE_VERSION_FINGERPRINT_CONFLICT",
                        FindingSeverity.BLOCK,
                        (logical_id, version_ref),
                        "same authoritative logical source/version has conflicting content fingerprints",
                    )
                )

        for logical_id, values in sorted(by_logical.items()):
            versions = {item.version_ref for item in values}
            if len(versions) > 1:
                findings.append(
                    DetectorFinding(
                        self._finding_id(
                            "MULTIPLE_AUTHORITATIVE_VERSIONS_REQUIRE_SUPERSESSION",
                            (logical_id, *sorted(versions)),
                        ),
                        "MULTIPLE_AUTHORITATIVE_VERSIONS_REQUIRE_SUPERSESSION",
                        FindingSeverity.REVIEW,
                        (logical_id, *tuple(sorted(versions))),
                        "multiple authoritative versions require explicit temporal/supersession resolution",
                    )
                )
        return tuple(findings)

    def scan(
        self,
        graph: IntegrityGraph,
        *,
        generated_at: str,
        packets: Sequence[EvidencePacket] = (),
        observations: Sequence[SourceVersionObservation] = (),
        semantic_threshold: float = 0.85,
    ) -> DetectorReport:
        if not generated_at.strip():
            raise ValueError("generated_at is required")
        findings = (
            *self.scan_semantic_duplicates(graph, threshold=semantic_threshold),
            *self.scan_dependency_cycles(graph),
            *self.scan_copy_inflation(graph),
            *self.scan_release_support(graph),
            *self.scan_packets(packets),
            *self.scan_source_versions(observations),
        )
        unique = {item.finding_id: item for item in findings}
        ordered = tuple(unique[key] for key in sorted(unique))
        return DetectorReport(
            graph_digest=self.graph_digest(graph),
            findings=ordered,
            generated_at=generated_at,
        )


class JfrieV2Assurance:
    """Detector-aware release wrapper around the admitted v2 core firewall."""

    def __init__(
        self,
        core: JfrieV2Core,
        detector: JfrieV2DetectorEngine | None = None,
    ) -> None:
        self.core = core
        self.detector = detector or JfrieV2DetectorEngine()

    def evaluate_release(
        self,
        request: ReleaseRequest,
        report: DetectorReport,
        *,
        accepted_review_finding_ids: Sequence[str] = (),
    ) -> ReleaseDecisionV2:
        baseline = self.core.evaluate_release(request)
        blockers = list(baseline.blockers)
        if report.graph_digest != self.detector.graph_digest(self.core.graph):
            blockers.append("DETECTOR_REPORT_STALE")
        for finding in report.blocking:
            blockers.append(f"DETECTOR_BLOCK:{finding.finding_id}:{finding.code}")
        accepted = set(accepted_review_finding_ids)
        for finding in report.reviews:
            if finding.finding_id not in accepted:
                blockers.append(f"DETECTOR_REVIEW_UNRESOLVED:{finding.finding_id}:{finding.code}")
        return ReleaseDecisionV2(
            state=ReleaseState.RELEASE_CLEARED if not blockers else ReleaseState.HOLD,
            allowed=not blockers,
            blockers=tuple(blockers),
            v1_evaluation=baseline.v1_evaluation,
            claim_ids=baseline.claim_ids,
            readback_ref=baseline.readback_ref,
            snapshot_ref=baseline.snapshot_ref,
        )


class PostReleaseMonitor:
    def __init__(self, detector: JfrieV2DetectorEngine | None = None) -> None:
        self.detector = detector or JfrieV2DetectorEngine()

    @staticmethod
    def _digest(value: object) -> str:
        return sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def _source_closure(
        self,
        graph: IntegrityGraph,
        claim_ids: Sequence[str],
    ) -> tuple[str, ...]:
        values: set[str] = set()
        frontier: list[str] = []
        for claim_id in claim_ids:
            claim = graph.claims[claim_id]
            frontier.extend(claim.source_ids)
        while frontier:
            source_id = frontier.pop()
            if source_id in values:
                continue
            values.add(source_id)
            parent = graph.sources[source_id].parent_source_id
            if parent:
                frontier.append(parent)
        return tuple(sorted(values))

    def _claim_fingerprint(self, claim: ClaimRecord) -> str:
        return self._digest(
            {
                "claim_id": claim.claim_id,
                "exact_text": claim.exact_text,
                "normalized_text": claim.normalized_text,
                "status": claim.evidence_status.value,
                "sources": sorted(claim.source_ids),
                "dependencies": sorted(claim.dependency_ids),
                "contradictions": sorted(claim.contradiction_ids),
                "contamination": claim.contamination_state.value,
                "release_eligibility": claim.release_eligibility,
                "authority_ref": claim.authority_ref,
            }
        )

    def _source_fingerprint(self, graph: IntegrityGraph, source_id: str) -> str:
        source = graph.sources[source_id]
        return self._digest(
            {
                "source_id": source.source_id,
                "provenance_class": source.provenance_class.value,
                "authenticated": source.authenticated,
                "parent_source_id": source.parent_source_id or "",
            }
        )

    def capture(
        self,
        *,
        decision: ReleaseDecisionV2,
        graph: IntegrityGraph,
        release_id: str,
        matter_id: str,
        snapshot_ref: str,
        captured_at: str,
    ) -> ReleaseSnapshot:
        if not decision.allowed:
            raise ValueError("cannot capture a release snapshot for a held release")
        if not all(value.strip() for value in (release_id, matter_id, snapshot_ref, captured_at)):
            raise ValueError("release snapshot identity is incomplete")
        claim_ids = tuple(sorted(decision.claim_ids))
        if not claim_ids:
            raise ValueError("release snapshot requires claims")
        for claim_id in claim_ids:
            if graph.claims[claim_id].matter_id != matter_id:
                raise ValueError("release snapshot matter mismatch")
        source_ids = self._source_closure(graph, claim_ids)
        claim_fingerprints = tuple(
            (claim_id, self._claim_fingerprint(graph.claims[claim_id]))
            for claim_id in claim_ids
        )
        source_fingerprints = tuple(
            (source_id, self._source_fingerprint(graph, source_id))
            for source_id in source_ids
        )
        state_digest = self._digest(
            {
                "claims": claim_fingerprints,
                "sources": source_fingerprints,
                "snapshot_ref": snapshot_ref,
            }
        )
        return ReleaseSnapshot(
            release_id=release_id,
            matter_id=matter_id,
            claim_ids=claim_ids,
            claim_fingerprints=claim_fingerprints,
            source_fingerprints=source_fingerprints,
            state_digest=state_digest,
            snapshot_ref=snapshot_ref,
            captured_at=captured_at,
        )

    def compare(
        self,
        snapshot: ReleaseSnapshot,
        graph: IntegrityGraph,
    ) -> PostReleaseDecision:
        prior_claims = dict(snapshot.claim_fingerprints)
        prior_sources = dict(snapshot.source_fingerprints)
        current_claims: Dict[str, str] = {}
        current_sources: Dict[str, str] = {}

        for claim_id in snapshot.claim_ids:
            if claim_id not in graph.claims:
                current_claims[claim_id] = "MISSING"
            else:
                current_claims[claim_id] = self._claim_fingerprint(graph.claims[claim_id])
        for source_id in prior_sources:
            if source_id not in graph.sources:
                current_sources[source_id] = "MISSING"
            else:
                current_sources[source_id] = self._source_fingerprint(graph, source_id)

        changed_claims = tuple(
            sorted(
                claim_id
                for claim_id, prior in prior_claims.items()
                if current_claims.get(claim_id) != prior
            )
        )
        changed_sources = tuple(
            sorted(
                source_id
                for source_id, prior in prior_sources.items()
                if current_sources.get(source_id) != prior
            )
        )
        current_digest = self._digest(
            {
                "claims": tuple(sorted(current_claims.items())),
                "sources": tuple(sorted(current_sources.items())),
                "snapshot_ref": snapshot.snapshot_ref,
            }
        )
        changed = bool(changed_claims or changed_sources or current_digest != snapshot.state_digest)
        return PostReleaseDecision(
            state=(
                PostReleaseState.RECALL_REQUIRED
                if changed
                else PostReleaseState.STABLE
            ),
            recall_required=changed,
            changed_claim_ids=changed_claims,
            changed_source_ids=changed_sources,
            prior_digest=snapshot.state_digest,
            current_digest=current_digest,
            release_id=snapshot.release_id,
        )


__all__ = [
    "DETECTOR_VERSION",
    "FULL_V2_PARITY",
    "DetectorFinding",
    "DetectorReport",
    "EvidencePacket",
    "FindingSeverity",
    "JfrieV2Assurance",
    "JfrieV2DetectorEngine",
    "PostReleaseDecision",
    "PostReleaseMonitor",
    "PostReleaseState",
    "ReleaseSnapshot",
    "SourceVersionObservation",
]
