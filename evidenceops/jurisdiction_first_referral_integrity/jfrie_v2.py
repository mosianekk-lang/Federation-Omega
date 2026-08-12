"""JFRIE v2.0 / EACIA executable core-parity slice.

This module preserves the admitted JFRIE v1/v1.1 referral gates and adds the
minimum v2 evidence-contamination/release controls needed for proof-bound legal
workflows. It is A1 internal only and does not claim full C001-C100 parity.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict, Iterable, Mapping, Optional, Sequence

from .jfrie import Evaluation, ReferralInput, evaluate as evaluate_v1, release_allowed as v1_release_allowed


V2_VERSION = "2.0.0-core-parity-slice-1"
AUTHORITY_CEILING = "A1_INTERNAL"
FULL_V2_PARITY = False


class ProvenanceClass(str, Enum):
    PRIMARY_EVIDENCE = "PRIMARY_EVIDENCE"
    OFFICIAL_AUTHORITY = "OFFICIAL_AUTHORITY"
    VERIFIED_SECONDARY = "VERIFIED_SECONDARY"
    USER_SUPPLIED = "USER_SUPPLIED"
    WITNESS_ASSERTION = "WITNESS_ASSERTION"
    PARTY_ASSERTION = "PARTY_ASSERTION"
    AI_ORIGIN = "AI_ORIGIN"
    DERIVATIVE_SUMMARY = "DERIVATIVE_SUMMARY"
    INFERENCE = "INFERENCE"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"
    QUARANTINED = "QUARANTINED"


class ClaimStatus(str, Enum):
    VERIFIED = "VERIFIED"
    VERIFIED_WITH_LIMITATION = "VERIFIED_WITH_LIMITATION"
    USER_SUPPLIED = "USER_SUPPLIED"
    INFERENCE = "INFERENCE"
    UNVERIFIED = "UNVERIFIED"
    CONTRADICTED = "CONTRADICTED"
    DISPUTED = "DISPUTED"
    STALE = "STALE"
    QUARANTINED = "QUARANTINED"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class ContaminationState(str, Enum):
    CLEAN = "CLEAN"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    QUARANTINED = "QUARANTINED"
    TAINTED = "TAINTED"
    RECALL_REQUIRED = "RECALL_REQUIRED"


class LineageRelation(str, Enum):
    ORIGINATES_FROM = "ORIGINATES_FROM"
    QUOTES = "QUOTES"
    SUMMARISES = "SUMMARISES"
    INFERS_FROM = "INFERS_FROM"
    CONTRADICTS = "CONTRADICTS"
    QUALIFIES = "QUALIFIES"
    SUPERSEDES = "SUPERSEDES"
    COPIED_FROM = "COPIED_FROM"
    DEPENDS_ON = "DEPENDS_ON"


class ReleaseState(str, Enum):
    RELEASE_CLEARED = "RELEASE_CLEARED"
    HOLD = "HOLD"
    RECALL_REQUIRED = "RECALL_REQUIRED"


SOURCE_TIER: Mapping[ProvenanceClass, int] = {
    ProvenanceClass.PRIMARY_EVIDENCE: 1,
    ProvenanceClass.OFFICIAL_AUTHORITY: 2,
    ProvenanceClass.VERIFIED_SECONDARY: 3,
    ProvenanceClass.USER_SUPPLIED: 5,
    ProvenanceClass.WITNESS_ASSERTION: 5,
    ProvenanceClass.PARTY_ASSERTION: 5,
    ProvenanceClass.AI_ORIGIN: 6,
    ProvenanceClass.DERIVATIVE_SUMMARY: 6,
    ProvenanceClass.INFERENCE: 7,
    ProvenanceClass.UNVERIFIED: 8,
    ProvenanceClass.CONTRADICTED: 9,
    ProvenanceClass.QUARANTINED: 10,
}

RELEASABLE_CLAIM_STATES = {
    ClaimStatus.VERIFIED,
    ClaimStatus.VERIFIED_WITH_LIMITATION,
}


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    provenance_class: ProvenanceClass
    authenticated: bool = False
    parent_source_id: Optional[str] = None
    notes: str = ""

    def validate(self) -> "SourceRecord":
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if self.parent_source_id == self.source_id:
            raise ValueError("source cannot be its own parent")
        return self


@dataclass(frozen=True)
class ClaimRecord:
    claim_id: str
    exact_text: str
    normalized_text: str
    matter_id: str
    workstream_id: str
    origin_type: ProvenanceClass
    origin_reference: str
    source_ids: tuple[str, ...]
    evidence_status: ClaimStatus
    authority_status: str
    created_at: str
    last_verified_at: str
    dependency_ids: tuple[str, ...] = ()
    contradiction_ids: tuple[str, ...] = ()
    contamination_state: ContaminationState = ContaminationState.CLEAN
    release_eligibility: bool = False
    legal_category: str = ""
    authority_ref: str = ""
    supersedes_claim_id: str = ""
    superseded_by_claim_id: str = ""

    def validate(self) -> "ClaimRecord":
        required = (
            self.claim_id,
            self.exact_text,
            self.normalized_text,
            self.matter_id,
            self.workstream_id,
            self.origin_reference,
            self.created_at,
            self.last_verified_at,
        )
        if not all(str(value).strip() for value in required):
            raise ValueError("material claim is missing a required v2 identity/provenance field")
        if self.evidence_status in RELEASABLE_CLAIM_STATES and not self.source_ids:
            raise ValueError("verified material claim requires source provenance")
        if self.legal_category.strip() and not self.authority_ref.strip():
            raise ValueError("legal category requires authority provenance")
        if self.origin_type is ProvenanceClass.AI_ORIGIN and self.evidence_status is ClaimStatus.VERIFIED and not self.source_ids:
            raise ValueError("AI-origin proposition cannot self-verify")
        if self.contamination_state in {
            ContaminationState.QUARANTINED,
            ContaminationState.TAINTED,
            ContaminationState.RECALL_REQUIRED,
        } and self.release_eligibility:
            raise ValueError("contaminated claim cannot remain release eligible")
        return self


@dataclass(frozen=True)
class LineageEdge:
    from_id: str
    relation: LineageRelation
    to_id: str

    def validate(self) -> "LineageEdge":
        if not self.from_id.strip() or not self.to_id.strip():
            raise ValueError("lineage endpoints are required")
        if self.from_id == self.to_id:
            raise ValueError("self-lineage is not allowed")
        return self


@dataclass(frozen=True)
class ClaimMutation:
    claim_id: str
    prior_text: str
    new_text: str
    prior_status: ClaimStatus
    new_status: ClaimStatus
    actor: str
    reason: str
    timestamp: str


@dataclass(frozen=True)
class QuarantineResult:
    claim_id: str
    contamination_radius: tuple[str, ...]
    affected_artifacts: tuple[str, ...]
    recall_required: bool
    reason: str


@dataclass(frozen=True)
class ReleaseRequest:
    referral: ReferralInput
    claim_ids: tuple[str, ...]
    mandatory_gates: Mapping[str, bool]
    owner_exclusions_passed: bool
    jfrie_recheck_passed: bool
    readback_ref: str
    snapshot_ref: str
    excluded_matter_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReleaseDecisionV2:
    state: ReleaseState
    allowed: bool
    blockers: tuple[str, ...]
    v1_evaluation: Evaluation
    claim_ids: tuple[str, ...]
    readback_ref: str
    snapshot_ref: str
    authority_ceiling: str = AUTHORITY_CEILING
    external_effect: bool = False


class IntegrityGraph:
    """Deterministic claim/source lineage and contamination graph."""

    def __init__(self) -> None:
        self.sources: Dict[str, SourceRecord] = {}
        self.claims: Dict[str, ClaimRecord] = {}
        self.lineage: list[LineageEdge] = []
        self.mutations: list[ClaimMutation] = []
        self.artifact_claim_dependencies: Dict[str, set[str]] = {}

    def register_source(self, source: SourceRecord) -> SourceRecord:
        source.validate()
        if source.parent_source_id and source.parent_source_id not in self.sources:
            raise ValueError("parent source must be registered first")
        existing = self.sources.get(source.source_id)
        if existing and existing != source:
            raise ValueError("source identity conflict")
        self.sources[source.source_id] = source
        return source

    def register_claim(self, claim: ClaimRecord) -> ClaimRecord:
        claim.validate()
        missing = [source_id for source_id in claim.source_ids if source_id not in self.sources]
        if missing:
            raise ValueError("claim references unregistered source(s): " + ",".join(sorted(missing)))
        existing = self.claims.get(claim.claim_id)
        if existing and existing != claim:
            raise ValueError("claim identity conflict; use revise_claim to preserve mutation history")
        self.claims[claim.claim_id] = claim
        return claim

    def add_lineage(self, edge: LineageEdge) -> LineageEdge:
        edge.validate()
        if edge.from_id not in self.sources and edge.from_id not in self.claims:
            raise ValueError("lineage from_id is unregistered")
        if edge.to_id not in self.sources and edge.to_id not in self.claims:
            raise ValueError("lineage to_id is unregistered")
        if edge not in self.lineage:
            self.lineage.append(edge)
        return edge

    def bind_artifact(self, artifact_id: str, claim_ids: Iterable[str]) -> None:
        if not artifact_id.strip():
            raise ValueError("artifact_id is required")
        claim_set = set(claim_ids)
        if not claim_set or not claim_set.issubset(self.claims):
            raise ValueError("artifact dependencies must be registered claims")
        self.artifact_claim_dependencies.setdefault(artifact_id, set()).update(claim_set)

    def source_root(self, source_id: str) -> str:
        if source_id not in self.sources:
            raise KeyError(source_id)
        seen: set[str] = set()
        current = source_id
        while self.sources[current].parent_source_id:
            if current in seen:
                raise ValueError("source lineage cycle")
            seen.add(current)
            parent = self.sources[current].parent_source_id
            assert parent is not None
            current = parent
        return current

    def independent_source_roots(self, source_ids: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted({self.source_root(source_id) for source_id in source_ids}))

    def best_source(self, source_ids: Iterable[str]) -> SourceRecord:
        values = [self.sources[source_id] for source_id in source_ids]
        if not values:
            raise ValueError("at least one source is required")
        return min(
            values,
            key=lambda source: (
                SOURCE_TIER[source.provenance_class],
                not source.authenticated,
                source.source_id,
            ),
        )

    def revise_claim(
        self,
        claim_id: str,
        *,
        new_text: str,
        new_normalized_text: str,
        new_status: ClaimStatus,
        actor: str,
        reason: str,
        timestamp: str,
        source_ids: Optional[Sequence[str]] = None,
    ) -> ClaimRecord:
        claim = self.claims[claim_id]
        if not all(value.strip() for value in (new_text, new_normalized_text, actor, reason, timestamp)):
            raise ValueError("claim revision requires text, actor, reason and timestamp")
        next_sources = tuple(source_ids) if source_ids is not None else claim.source_ids
        missing = [source_id for source_id in next_sources if source_id not in self.sources]
        if missing:
            raise ValueError("revision references unregistered source(s)")
        revised = replace(
            claim,
            exact_text=new_text,
            normalized_text=new_normalized_text,
            evidence_status=new_status,
            source_ids=next_sources,
            last_verified_at=timestamp,
            release_eligibility=False,
        ).validate()
        self.mutations.append(
            ClaimMutation(
                claim_id=claim_id,
                prior_text=claim.exact_text,
                new_text=new_text,
                prior_status=claim.evidence_status,
                new_status=new_status,
                actor=actor,
                reason=reason,
                timestamp=timestamp,
            )
        )
        self.claims[claim_id] = revised
        return revised

    def mark_release_eligible(self, claim_id: str, *, timestamp: str) -> ClaimRecord:
        """Explicitly promote a clean, source-bound claim into release eligibility.

        Verification and cleanliness do not themselves imply release eligibility.
        Any later revision or quarantine resets this flag and requires a fresh check.
        """
        if not timestamp.strip():
            raise ValueError("release-eligibility decision requires timestamp")
        claim = self.claims[claim_id]
        blockers: list[str] = []
        if claim.evidence_status not in RELEASABLE_CLAIM_STATES:
            blockers.append("CLAIM_NOT_VERIFIED")
        if claim.contamination_state is not ContaminationState.CLEAN:
            blockers.append("CLAIM_NOT_CLEAN")
        if claim.contradiction_ids:
            blockers.append("UNRESOLVED_CONTRADICTIONS")
        if not claim.source_ids:
            blockers.append("SOURCE_PROVENANCE_MISSING")
        if claim.legal_category and not claim.authority_ref:
            blockers.append("LEGAL_AUTHORITY_MISSING")
        if blockers:
            raise ValueError("release eligibility blocked: " + ",".join(blockers))
        eligible = replace(
            claim,
            release_eligibility=True,
            last_verified_at=timestamp,
        ).validate()
        self.claims[claim_id] = eligible
        return eligible

    def dependent_claims(self, claim_id: str) -> tuple[str, ...]:
        if claim_id not in self.claims:
            raise KeyError(claim_id)
        affected: set[str] = set()
        frontier = [claim_id]
        while frontier:
            current = frontier.pop()
            for candidate in self.claims.values():
                if current in candidate.dependency_ids and candidate.claim_id not in affected:
                    affected.add(candidate.claim_id)
                    frontier.append(candidate.claim_id)
        affected.discard(claim_id)
        return tuple(sorted(affected))

    def affected_artifacts(self, claim_ids: Iterable[str]) -> tuple[str, ...]:
        affected = set(claim_ids)
        return tuple(
            sorted(
                artifact_id
                for artifact_id, dependencies in self.artifact_claim_dependencies.items()
                if dependencies & affected
            )
        )

    def quarantine_claim(self, claim_id: str, *, reason: str, timestamp: str) -> QuarantineResult:
        if not reason.strip() or not timestamp.strip():
            raise ValueError("quarantine requires reason and timestamp")
        claim = self.claims[claim_id]
        dependents = self.dependent_claims(claim_id)
        radius = tuple(sorted({claim_id, *dependents}))
        artifacts = self.affected_artifacts(radius)
        self.claims[claim_id] = replace(
            claim,
            evidence_status=ClaimStatus.QUARANTINED,
            contamination_state=ContaminationState.QUARANTINED,
            release_eligibility=False,
            last_verified_at=timestamp,
        )
        for dependent_id in dependents:
            dependent = self.claims[dependent_id]
            self.claims[dependent_id] = replace(
                dependent,
                contamination_state=ContaminationState.NEEDS_REVIEW,
                release_eligibility=False,
                last_verified_at=timestamp,
            )
        return QuarantineResult(claim_id, radius, artifacts, bool(artifacts), reason)

    @staticmethod
    def synchronization_verified(readback_ref: str) -> bool:
        return bool(readback_ref and readback_ref.strip())


class JfrieV2Core:
    """v1/v1.1-preserving v2 integrity and release firewall."""

    def __init__(self, graph: Optional[IntegrityGraph] = None) -> None:
        self.graph = graph or IntegrityGraph()

    def evaluate_release(self, request: ReleaseRequest) -> ReleaseDecisionV2:
        baseline = evaluate_v1(request.referral)
        blockers: list[str] = []

        if not v1_release_allowed(baseline):
            blockers.append("V1_REFERRAL_GATE_NOT_RELEASABLE")
        failed_mandatory = sorted(
            name for name, passed in request.mandatory_gates.items() if not passed
        )
        if failed_mandatory:
            blockers.append("MANDATORY_GATE_FAILED:" + ",".join(failed_mandatory))
        if not request.claim_ids:
            blockers.append("NO_RELEASE_CLAIMS")
        if not request.owner_exclusions_passed:
            blockers.append("OWNER_EXCLUSIONS_NOT_CLEARED")
        if not request.jfrie_recheck_passed:
            blockers.append("POST_REPAIR_JFRIE_RECHECK_REQUIRED")
        if not request.readback_ref.strip():
            blockers.append("NODE_READBACK_REQUIRED")
        if not request.snapshot_ref.strip():
            blockers.append("VERSION_IDENTIFIABLE_RELEASE_SNAPSHOT_REQUIRED")

        excluded = set(request.excluded_matter_ids)
        for claim_id in request.claim_ids:
            claim = self.graph.claims.get(claim_id)
            if claim is None:
                blockers.append(f"UNREGISTERED_CLAIM:{claim_id}")
                continue
            if claim.matter_id in excluded:
                blockers.append(f"EXCLUDED_MATTER_CLAIM:{claim_id}")
            if claim.evidence_status not in RELEASABLE_CLAIM_STATES:
                blockers.append(
                    f"CLAIM_NOT_RELEASE_VERIFIED:{claim_id}:{claim.evidence_status.value}"
                )
            if claim.contamination_state is not ContaminationState.CLEAN:
                blockers.append(
                    f"CLAIM_CONTAMINATED:{claim_id}:{claim.contamination_state.value}"
                )
            if claim.contradiction_ids:
                blockers.append(f"UNRESOLVED_CONTRADICTION:{claim_id}")
            if claim.legal_category and not claim.authority_ref:
                blockers.append(f"LEGAL_AUTHORITY_MISSING:{claim_id}")
            if not claim.source_ids:
                blockers.append(f"CLAIM_PROVENANCE_MISSING:{claim_id}")
            if not claim.release_eligibility:
                blockers.append(f"CLAIM_RELEASE_ELIGIBILITY_FALSE:{claim_id}")

        allowed = not blockers
        return ReleaseDecisionV2(
            state=ReleaseState.RELEASE_CLEARED if allowed else ReleaseState.HOLD,
            allowed=allowed,
            blockers=tuple(blockers),
            v1_evaluation=baseline,
            claim_ids=request.claim_ids,
            readback_ref=request.readback_ref,
            snapshot_ref=request.snapshot_ref,
        )

    def invalidate_and_recall(
        self,
        claim_id: str,
        *,
        reason: str,
        timestamp: str,
    ) -> QuarantineResult:
        return self.graph.quarantine_claim(
            claim_id,
            reason=reason,
            timestamp=timestamp,
        )


__all__ = [
    "AUTHORITY_CEILING",
    "FULL_V2_PARITY",
    "V2_VERSION",
    "ClaimMutation",
    "ClaimRecord",
    "ClaimStatus",
    "ContaminationState",
    "IntegrityGraph",
    "JfrieV2Core",
    "LineageEdge",
    "LineageRelation",
    "ProvenanceClass",
    "QuarantineResult",
    "ReleaseDecisionV2",
    "ReleaseRequest",
    "ReleaseState",
    "SourceRecord",
]
