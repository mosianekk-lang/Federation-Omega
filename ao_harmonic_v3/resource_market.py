from __future__ import annotations

from dataclasses import dataclass

from .models import Maturity, ResourceOffer


MATURITY_ORDER = {
    Maturity.DESIGN_ONLY: 0,
    Maturity.SOURCE_IMPLEMENTED: 1,
    Maturity.DETERMINISTIC_TESTED: 2,
    Maturity.ADVERSARIALLY_TESTED: 3,
    Maturity.SHADOW_VALIDATED: 4,
    Maturity.CANARY_VALIDATED: 5,
    Maturity.WORKFLOW_VERIFIED: 6,
    Maturity.OPERATIONAL_VERIFIED: 7,
    Maturity.CANONICAL: 8,
}


@dataclass(frozen=True)
class ResourceRequest:
    capability: str
    semantic_scope: str = ""
    minimum_maturity: Maturity = Maturity.SOURCE_IMPLEMENTED
    authority_ceiling: str = "A1_INTERNAL"
    maximum_owner_burden: float = 10.0
    rollback_required: bool = False


class ResourceMarket:
    EPSILON = 1e-9

    @staticmethod
    def score(resource: ResourceOffer) -> float:
        positive = (
            resource.relevance
            * resource.semantic_fit
            * resource.freshness
            * resource.reliability
            * resource.proof_strength
            * resource.executability
            * resource.information_gain
        )
        negative = (
            resource.latency
            + resource.owner_burden
            + resource.privacy_cost
            + resource.duplication_cost
            + resource.failure_risk
            + ResourceMarket.EPSILON
        )
        return positive / negative

    @staticmethod
    def eligible(resource: ResourceOffer, request: ResourceRequest) -> bool:
        if resource.capability != request.capability:
            return False
        if MATURITY_ORDER[resource.maturity] < MATURITY_ORDER[request.minimum_maturity]:
            return False
        if resource.owner_burden > request.maximum_owner_burden:
            return False
        if request.rollback_required and not resource.rollback_available:
            return False
        if request.semantic_scope and request.semantic_scope not in resource.semantic_scope:
            return False
        return True

    def rank(self, resources: list[ResourceOffer], request: ResourceRequest) -> list[ResourceOffer]:
        eligible = [r for r in resources if self.eligible(r, request)]
        return sorted(eligible, key=self.score, reverse=True)

    def best(self, resources: list[ResourceOffer], request: ResourceRequest) -> ResourceOffer | None:
        ranked = self.rank(resources, request)
        return ranked[0] if ranked else None
