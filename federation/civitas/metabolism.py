from __future__ import annotations

"""Strategic portfolio brain and Federation metabolism.

The metabolism allocates bounded internal resources while protecting reserve,
proof, safety, owner control and owner attention. A mission can have high
utility and still be held when its proof or authority is insufficient.
"""

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .contracts import (
    AuthorityClass,
    CivitasError,
    ObjectiveVector,
    ProofLevel,
    ProofRef,
    ResourceBudget,
    ResourceDemand,
    authority_at_most,
    digest,
    proof_at_least,
    safe_id,
)


@dataclass(frozen=True)
class MissionCandidate:
    mission_id: str
    objective: str
    vector: ObjectiveVector
    demand: ResourceDemand
    proof: ProofRef
    required_authority: AuthorityClass = AuthorityClass.A1_INTERNAL
    dependencies: tuple[str, ...] = ()
    unlocks: tuple[str, ...] = ()
    hard_blockers: tuple[str, ...] = ()
    reversible: bool = True
    external_effect: bool = False

    def validate(self) -> "MissionCandidate":
        safe_id(self.mission_id, "mission_id")
        if not self.objective.strip():
            raise ValueError("mission objective required")
        self.vector.validate()
        self.demand.validate()
        self.proof.validate()
        if not authority_at_most(self.required_authority, AuthorityClass.A1_INTERNAL):
            raise CivitasError("portfolio cannot allocate external-effect authority")
        if self.external_effect:
            raise CivitasError("CIVITAS mission candidates must be effect-free")
        return self

    @property
    def strategic_utility(self) -> float:
        self.validate()
        unlock_bonus = min(0.20, 0.025 * len(set(self.unlocks)))
        dependency_penalty = min(0.16, 0.02 * len(set(self.dependencies)))
        blocker_penalty = min(0.35, 0.08 * len(set(self.hard_blockers)))
        reversibility_bonus = 0.04 if self.reversible else -0.04
        return round(max(0.0, self.vector.utility + unlock_bonus + reversibility_bonus - dependency_penalty - blocker_penalty), 8)


@dataclass(frozen=True)
class MissionAllocation:
    mission_id: str
    disposition: str
    priority: float
    allocated: ResourceDemand
    unmet_resources: tuple[str, ...]
    proof_refs: tuple[str, ...]
    explanation: str
    external_effects: int = 0


@dataclass(frozen=True)
class PortfolioDecision:
    selected: tuple[MissionAllocation, ...]
    held: tuple[MissionAllocation, ...]
    reserve: ResourceBudget
    pareto_frontier: tuple[str, ...]
    shared_unlocks: tuple[str, ...]
    external_effects: int = 0

    @property
    def receipt_sha256(self) -> str:
        return digest(asdict(self))


@dataclass(frozen=True)
class FeatureRent:
    feature_id: str
    capability_gain: float
    proof_gain: float
    resilience_gain: float
    owner_load_reduction: float
    complexity_cost: float
    duplication_cost: float
    coordination_cost: float
    maintenance_cost: float
    proof_refs: tuple[str, ...]

    def validate(self) -> "FeatureRent":
        safe_id(self.feature_id, "feature_id")
        for name in (
            "capability_gain", "proof_gain", "resilience_gain", "owner_load_reduction",
            "complexity_cost", "duplication_cost", "coordination_cost", "maintenance_cost",
        ):
            value = float(getattr(self, name))
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0,1]")
        if not self.proof_refs:
            raise ValueError("feature rent requires proof")
        return self

    @property
    def net_rent(self) -> float:
        self.validate()
        benefits = (
            0.30 * self.capability_gain
            + 0.23 * self.proof_gain
            + 0.22 * self.resilience_gain
            + 0.25 * self.owner_load_reduction
        )
        costs = (
            0.30 * self.complexity_cost
            + 0.25 * self.duplication_cost
            + 0.25 * self.coordination_cost
            + 0.20 * self.maintenance_cost
        )
        return round(benefits - costs, 8)


@dataclass(frozen=True)
class EntropyAssessment:
    feature_id: str
    net_rent: float
    disposition: str
    archive_first: bool
    deletion_permitted: bool
    explanation: str
    external_effects: int = 0


class FederationMetabolism:
    """Reserve-protected allocator for compute, tokens, money and attention."""

    RESOURCE_NAMES = (
        "compute", "tokens", "money", "latency", "owner_attention", "proof_effort", "storage",
    )

    def __init__(self, budget: ResourceBudget) -> None:
        self.total = budget.validate()
        self.available = budget.available()
        self._remaining = {name: float(getattr(self.available, name)) for name in self.RESOURCE_NAMES}
        self._allocations: dict[str, ResourceDemand] = {}

    @property
    def remaining(self) -> ResourceDemand:
        return ResourceDemand(**self._remaining)

    def can_allocate(self, demand: ResourceDemand) -> tuple[bool, tuple[str, ...]]:
        demand.validate()
        unmet = tuple(
            name for name in self.RESOURCE_NAMES
            if float(getattr(demand, name)) > self._remaining[name] + 1e-12
        )
        return not unmet, unmet

    def allocate(self, mission_id: str, demand: ResourceDemand) -> ResourceDemand:
        safe_id(mission_id, "mission_id")
        if mission_id in self._allocations:
            if self._allocations[mission_id] != demand:
                raise CivitasError("mission allocation id reused with different demand")
            return self._allocations[mission_id]
        ok, unmet = self.can_allocate(demand)
        if not ok:
            raise CivitasError("resource demand exceeds protected available budget: " + ",".join(unmet))
        for name in self.RESOURCE_NAMES:
            self._remaining[name] -= float(getattr(demand, name))
        self._allocations[mission_id] = demand
        return demand

    @property
    def reserve(self) -> ResourceBudget:
        return ResourceBudget(
            compute=self.total.compute * self.total.reserve_fraction,
            tokens=self.total.tokens * self.total.reserve_fraction,
            money=self.total.money * self.total.reserve_fraction,
            latency=self.total.latency * self.total.reserve_fraction,
            owner_attention=self.total.owner_attention * self.total.reserve_fraction,
            proof_effort=self.total.proof_effort * self.total.reserve_fraction,
            storage=self.total.storage * self.total.reserve_fraction,
            reserve_fraction=0.0,
        )

    @staticmethod
    def feature_rent(feature: FeatureRent, *, minimum_net_rent: float = 0.03) -> EntropyAssessment:
        feature.validate()
        if not -1 <= minimum_net_rent <= 1:
            raise ValueError("minimum_net_rent must be in [-1,1]")
        net = feature.net_rent
        if net >= minimum_net_rent:
            disposition = "KEEP_AND_MEASURE"
            explanation = "measured capability/proof/resilience/owner-load gains exceed entropy cost"
        elif net >= 0:
            disposition = "SHADOW_AND_REDESIGN"
            explanation = "feature is not harmful but has not yet earned permanent complexity"
        else:
            disposition = "ARCHIVE_THEN_SUCCESSION_REVIEW"
            explanation = "complexity, duplication and coordination cost exceed current measured benefit"
        return EntropyAssessment(feature.feature_id, net, disposition, True, False, explanation)


class StrategicPortfolioBrain:
    """Pareto-aware mission compiler above individual task routing."""

    def __init__(self, metabolism: FederationMetabolism) -> None:
        self.metabolism = metabolism

    @staticmethod
    def _dominates(left: MissionCandidate, right: MissionCandidate) -> bool:
        lb, rb = left.vector.benefit_tuple, right.vector.benefit_tuple
        lc, rc = left.vector.cost_tuple, right.vector.cost_tuple
        return (
            all(a >= b for a, b in zip(lb, rb))
            and all(a <= b for a, b in zip(lc, rc))
            and (any(a > b for a, b in zip(lb, rb)) or any(a < b for a, b in zip(lc, rc)))
        )

    @classmethod
    def pareto_frontier(cls, missions: Sequence[MissionCandidate]) -> tuple[MissionCandidate, ...]:
        validated = [mission.validate() for mission in missions]
        return tuple(sorted(
            (
                mission for mission in validated
                if not any(other.mission_id != mission.mission_id and cls._dominates(other, mission) for other in validated)
            ),
            key=lambda item: (item.strategic_utility, item.mission_id),
            reverse=True,
        ))

    @staticmethod
    def shared_unlocks(missions: Sequence[MissionCandidate]) -> tuple[str, ...]:
        counts: dict[str, int] = {}
        for mission in missions:
            for unlock in set(mission.unlocks):
                counts[unlock] = counts.get(unlock, 0) + 1
        return tuple(sorted((unlock for unlock, count in counts.items() if count >= 2), key=lambda item: (-counts[item], item)))

    def compile(self, missions: Sequence[MissionCandidate]) -> PortfolioDecision:
        if not missions:
            raise ValueError("mission candidates required")
        seen: set[str] = set()
        validated: list[MissionCandidate] = []
        for mission in missions:
            mission.validate()
            if mission.mission_id in seen:
                raise CivitasError("duplicate mission id")
            seen.add(mission.mission_id)
            validated.append(mission)
        frontier = self.pareto_frontier(validated)
        frontier_ids = {mission.mission_id for mission in frontier}
        unlocks = self.shared_unlocks(validated)
        ranked = sorted(
            validated,
            key=lambda item: (
                item.strategic_utility,
                len(set(item.unlocks).intersection(unlocks)),
                item.mission_id,
            ),
            reverse=True,
        )
        selected: list[MissionAllocation] = []
        held: list[MissionAllocation] = []
        for mission in ranked:
            reasons: list[str] = []
            if not proof_at_least(mission.proof.level, ProofLevel.SOURCE_READBACK):
                reasons.append("PROOF_BELOW_SOURCE_READBACK")
            if mission.hard_blockers:
                reasons.append("HARD_BLOCKERS:" + ",".join(sorted(set(mission.hard_blockers))))
            ok, unmet = self.metabolism.can_allocate(mission.demand)
            if not ok:
                reasons.append("RESOURCE_LIMIT:" + ",".join(unmet))
            if mission.mission_id not in frontier_ids and mission.strategic_utility < 0.35:
                reasons.append("DOMINATED_LOW_UTILITY")
            if reasons:
                held.append(MissionAllocation(
                    mission.mission_id,
                    "HOLD_EXACT_GATES",
                    mission.strategic_utility,
                    ResourceDemand(),
                    unmet if not ok else (),
                    (mission.proof.proof_ref,),
                    "; ".join(reasons),
                ))
                continue
            allocation = self.metabolism.allocate(mission.mission_id, mission.demand)
            selected.append(MissionAllocation(
                mission.mission_id,
                "ALLOCATE_INTERNAL_PORTFOLIO",
                mission.strategic_utility,
                allocation,
                (),
                (mission.proof.proof_ref,),
                "admissible mission selected by strategic utility, Pareto position and protected budget",
            ))
        return PortfolioDecision(
            tuple(selected),
            tuple(held),
            self.metabolism.reserve,
            tuple(mission.mission_id for mission in frontier),
            unlocks,
        )


__all__ = [
    "MissionCandidate", "MissionAllocation", "PortfolioDecision", "FeatureRent",
    "EntropyAssessment", "FederationMetabolism", "StrategicPortfolioBrain",
]
