from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from math import exp
from typing import Iterable, List


class ClaimStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    POSSIBLE = "POSSIBLE"
    LIKELY = "LIKELY"
    KNOWN = "KNOWN"
    CONTESTED = "CONTESTED"
    STALE = "STALE"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    supports: bool
    authority: float
    reliability: float
    freshness: float
    independence_group: str = ""

    @staticmethod
    def _bounded(value: float) -> float:
        return max(0.0, min(1.0, value))

    @property
    def weight(self) -> float:
        return (
            self._bounded(self.authority)
            * self._bounded(self.reliability)
            * self._bounded(self.freshness)
        )


@dataclass
class Claim:
    claim_id: str
    evidence: List[Evidence] = field(default_factory=list)
    expiry_freshness_floor: float = 0.25

    def add(self, item: Evidence) -> None:
        self.evidence.append(item)

    def _independent_best(self) -> Iterable[Evidence]:
        groups = defaultdict(list)
        for item in self.evidence:
            groups[item.independence_group or item.evidence_id].append(item)
        for items in groups.values():
            yield max(items, key=lambda e: e.weight)

    @property
    def probability(self) -> float:
        independent = list(self._independent_best())
        if not independent:
            return 0.5
        support = sum(item.weight for item in independent if item.supports)
        oppose = sum(item.weight for item in independent if not item.supports)
        return 1.0 / (1.0 + exp(-(support - oppose)))

    @property
    def status(self) -> ClaimStatus:
        if not self.evidence:
            return ClaimStatus.UNKNOWN
        if max(item.freshness for item in self.evidence) < self.expiry_freshness_floor:
            return ClaimStatus.STALE

        independent = list(self._independent_best())
        strong_support = [e for e in independent if e.supports and e.weight >= 0.35]
        strong_oppose = [e for e in independent if not e.supports and e.weight >= 0.35]
        if strong_support and strong_oppose:
            return ClaimStatus.CONTESTED

        p = self.probability
        support_groups = {
            e.independence_group or e.evidence_id
            for e in independent
            if e.supports and e.weight >= 0.35
        }
        if p >= 0.82 and len(support_groups) >= 2:
            return ClaimStatus.KNOWN
        if p >= 0.67:
            return ClaimStatus.LIKELY
        return ClaimStatus.POSSIBLE


class EpistemicLedger:
    """Evidence-first claim state.

    Independent evidence groups prevent duplicated/echoed sources from being
    treated as independent corroboration. Model agreement is never special:
    it enters only as ordinary evidence with explicit authority/reliability.
    """

    def __init__(self) -> None:
        self._claims: dict[str, Claim] = {}

    def claim(self, claim_id: str) -> Claim:
        return self._claims.setdefault(claim_id, Claim(claim_id))

    def add_evidence(self, claim_id: str, evidence: Evidence) -> Claim:
        claim = self.claim(claim_id)
        claim.add(evidence)
        return claim

    def invalidate_freshness(self, claim_id: str) -> None:
        claim = self.claim(claim_id)
        claim.evidence = [
            Evidence(
                item.evidence_id,
                item.supports,
                item.authority,
                item.reliability,
                0.0,
                item.independence_group,
            )
            for item in claim.evidence
        ]
