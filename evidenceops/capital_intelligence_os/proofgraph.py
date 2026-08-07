from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import uuid

from .models import Claim, EvidenceStatus


@dataclass(frozen=True)
class Contradiction:
    contradiction_id: str
    subject_id: str
    predicate: str
    claim_ids: tuple[str, str]
    values: tuple[str, str]
    severity: float


class ProofGraph:
    """Minimal deterministic evidence graph with contradiction and impact logic."""

    def __init__(self) -> None:
        self.claims: dict[str, Claim] = {}
        self.by_key: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.dependencies: dict[str, set[str]] = defaultdict(set)
        self.reverse_dependencies: dict[str, set[str]] = defaultdict(set)
        self.contradictions: dict[str, Contradiction] = {}

    def add_dependency(self, source_subject: str, dependent_subject: str) -> None:
        if source_subject == dependent_subject:
            return
        self.dependencies[source_subject].add(dependent_subject)
        self.reverse_dependencies[dependent_subject].add(source_subject)

    def add_claim(self, claim: Claim) -> list[Contradiction]:
        claim.validate()
        if claim.claim_id in self.claims:
            existing = self.claims[claim.claim_id]
            if existing.fingerprint() != claim.fingerprint():
                raise ValueError("claim_id collision with different content")
            return []
        if claim.supersedes and claim.supersedes not in self.claims:
            raise ValueError("supersedes must reference an existing claim")
        key = (claim.subject_id, claim.predicate)
        conflicts: list[Contradiction] = []
        for prior_id in self.by_key[key]:
            prior = self.claims[prior_id]
            if prior.claim_id == claim.supersedes or claim.claim_id == prior.supersedes:
                continue
            if prior.normalized_value() == claim.normalized_value():
                continue
            strength = min(self._evidence_strength(prior), self._evidence_strength(claim))
            if strength <= 0.15:
                continue
            cid = str(uuid.uuid4())
            contradiction = Contradiction(
                contradiction_id=cid,
                subject_id=claim.subject_id,
                predicate=claim.predicate,
                claim_ids=(prior.claim_id, claim.claim_id),
                values=(prior.normalized_value(), claim.normalized_value()),
                severity=min(1.0, 0.35 + strength * 0.65),
            )
            self.contradictions[cid] = contradiction
            conflicts.append(contradiction)
        self.claims[claim.claim_id] = claim
        self.by_key[key].append(claim.claim_id)
        return conflicts

    def current_claims(self, subject_id: str, predicate: str | None = None) -> list[Claim]:
        result = []
        superseded = {c.supersedes for c in self.claims.values() if c.supersedes}
        for claim in self.claims.values():
            if claim.claim_id in superseded or claim.subject_id != subject_id:
                continue
            if predicate is not None and claim.predicate != predicate:
                continue
            result.append(claim)
        return result

    def impact_of(self, subject_id: str, max_depth: int = 6) -> list[str]:
        seen = {subject_id}
        queue = deque([(subject_id, 0)])
        impacted: list[str] = []
        while queue:
            node, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for child in sorted(self.dependencies.get(node, ())):
                if child in seen:
                    continue
                seen.add(child)
                impacted.append(child)
                queue.append((child, depth + 1))
        return impacted

    def contradiction_rate(self, subject_id: str) -> float:
        subject_claims = [c for c in self.claims.values() if c.subject_id == subject_id]
        if not subject_claims:
            return 0.0
        involved = {claim_id for contradiction in self.contradictions.values() if contradiction.subject_id == subject_id for claim_id in contradiction.claim_ids}
        return min(1.0, len(involved) / len(subject_claims))

    @staticmethod
    def _evidence_strength(claim: Claim) -> float:
        base = {
            EvidenceStatus.VERIFIED: 1.0,
            EvidenceStatus.CORROBORATED: 0.9,
            EvidenceStatus.USER_SUPPLIED: 0.55,
            EvidenceStatus.INFERENCE: 0.45,
            EvidenceStatus.MODEL_ESTIMATE: 0.4,
            EvidenceStatus.UNVERIFIED: 0.1,
        }[claim.status]
        return min(base, max(0.0, claim.confidence))
