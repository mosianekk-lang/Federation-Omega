"""Strategic Objective Ecology (SOE Omega) v1.

Estate-wide, authority-bounded portfolio intelligence built above AMCF/MCE.
It generates and selects mission candidates, allocates bounded resources, detects
duplicate mission intent, measures capability pressure, and preserves owner
authority for consequential objectives.

This module produces plans only. It does not create credentials, spend money,
send messages, deploy workloads, or mutate providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import math
import re
from typing import Iterable, Mapping

from .autonomic_fabric import AuthorityCeiling


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _stable_hash(payload: object) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _tokens(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", value.casefold()))


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a = set(left)
    b = set(right)
    if not a and not b:
        return 1.0
    union = a | b
    return 0.0 if not union else len(a & b) / len(union)


class MissionLifecycle(str, Enum):
    PROPOSED = "PROPOSED"
    SELECTED = "SELECTED"
    ACTIVE = "ACTIVE"
    HELD = "HELD"
    MERGE_CANDIDATE = "MERGE_CANDIDATE"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"
    VERIFIED_CLOSED = "VERIFIED_CLOSED"


class GenesisSignalType(str, Enum):
    GAP = "GAP"
    OPPORTUNITY = "OPPORTUNITY"
    RISK = "RISK"
    DEPENDENCY = "DEPENDENCY"
    CAPABILITY = "CAPABILITY"


@dataclass(frozen=True)
class StrategicObjective:
    objective_id: str
    title: str
    outcome_value: float
    urgency: float
    confidence: float
    authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL
    invariants: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @property
    def priority(self) -> float:
        return _clip(self.outcome_value) * (0.5 + 0.5 * _clip(self.urgency)) * (0.5 + 0.5 * _clip(self.confidence))


@dataclass(frozen=True)
class MissionCandidate:
    mission_id: str
    objective_id: str
    summary: str
    outcome_value: float
    unlock_leverage: float
    success_probability: float
    learning_value: float
    reusability: float
    cost: float
    risk: float
    latency: float
    required_capabilities: tuple[str, ...] = ()
    produces_capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    resource_demand: Mapping[str, float] = field(default_factory=dict)
    authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL
    external_effect: bool = False
    owner_reserved: bool = False
    lifecycle: MissionLifecycle = MissionLifecycle.PROPOSED
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.mission_id.strip():
            raise ValueError("mission_id is required")
        if not self.objective_id.strip():
            raise ValueError("objective_id is required")
        if not self.summary.strip():
            raise ValueError("summary is required")
        if self.cost < 0 or self.risk < 0 or self.latency < 0:
            raise ValueError("cost/risk/latency must be non-negative")
        for resource, amount in self.resource_demand.items():
            if amount < 0:
                raise ValueError(f"resource demand must be non-negative: {resource}")

    @property
    def strategic_utility(self) -> float:
        benefit = (
            0.34 * _clip(self.outcome_value)
            + 0.24 * _clip(self.unlock_leverage)
            + 0.16 * _clip(self.learning_value)
            + 0.16 * _clip(self.reusability)
            + 0.10 * _clip(self.success_probability)
        )
        success = max(0.05, _clip(self.success_probability))
        denominator = (1.0 + self.cost) * (1.0 + self.risk) * (1.0 + self.latency)
        return (benefit * success) / denominator

    @property
    def signature(self) -> str:
        return _stable_hash(
            {
                "objective": sorted(_tokens(self.summary)),
                "requires": sorted(self.required_capabilities),
                "produces": sorted(self.produces_capabilities),
            }
        )[:20]


@dataclass(frozen=True)
class ResourceEnvelope:
    capacity: Mapping[str, float]

    def can_fit(self, used: Mapping[str, float], demand: Mapping[str, float]) -> bool:
        for resource, amount in demand.items():
            if used.get(resource, 0.0) + amount > self.capacity.get(resource, 0.0) + 1e-12:
                return False
        return True

    def consume(self, used: Mapping[str, float], demand: Mapping[str, float]) -> dict[str, float]:
        if not self.can_fit(used, demand):
            raise ValueError("resource demand exceeds envelope")
        result = dict(used)
        for resource, amount in demand.items():
            result[resource] = result.get(resource, 0.0) + amount
        return result


@dataclass(frozen=True)
class CapabilityPressure:
    capability: str
    demanding_missions: tuple[str, ...]
    weighted_demand: float
    unlock_value: float
    build_priority: float


class CapabilityCentrality:
    def measure(self, missions: Iterable[MissionCandidate]) -> tuple[CapabilityPressure, ...]:
        by_capability: dict[str, list[MissionCandidate]] = {}
        for mission in missions:
            for capability in set(mission.required_capabilities):
                by_capability.setdefault(capability, []).append(mission)
        result = []
        for capability, items in by_capability.items():
            weighted = sum(item.strategic_utility for item in items)
            unlock = sum(_clip(item.unlock_leverage) for item in items)
            build_priority = weighted * (1.0 + math.log1p(len(items))) * (1.0 + unlock)
            result.append(
                CapabilityPressure(
                    capability=capability,
                    demanding_missions=tuple(sorted(item.mission_id for item in items)),
                    weighted_demand=weighted,
                    unlock_value=unlock,
                    build_priority=build_priority,
                )
            )
        return tuple(sorted(result, key=lambda item: (-item.build_priority, item.capability)))


@dataclass(frozen=True)
class PortfolioPlan:
    selected: tuple[MissionCandidate, ...]
    held: tuple[tuple[str, str], ...]
    resource_usage: Mapping[str, float]
    total_utility: float
    plan_sha256: str


class PortfolioAllocator:
    """Deterministic dependency-aware resource allocator."""

    def _scarcity_cost(self, mission: MissionCandidate, envelope: ResourceEnvelope) -> float:
        cost = 0.0
        for resource, amount in mission.resource_demand.items():
            capacity = envelope.capacity.get(resource, 0.0)
            if capacity <= 0 and amount > 0:
                return math.inf
            if capacity > 0:
                cost += amount / capacity
        return max(0.001, cost)

    def allocate(
        self,
        missions: Iterable[MissionCandidate],
        envelope: ResourceEnvelope,
        *,
        authority_ceiling: AuthorityCeiling = AuthorityCeiling.A1_INTERNAL,
        allow_external_effects: bool = False,
        max_missions: int = 12,
    ) -> PortfolioPlan:
        if max_missions < 1:
            raise ValueError("max_missions must be at least one")
        candidates = {item.mission_id: item for item in missions}
        selected: list[MissionCandidate] = []
        selected_ids: set[str] = set()
        used: dict[str, float] = {}
        held: dict[str, str] = {}
        authority_rank = {
            AuthorityCeiling.A0_OBSERVE: 0,
            AuthorityCeiling.A1_INTERNAL: 1,
            AuthorityCeiling.A2_BOUNDED_EFFECT: 2,
            AuthorityCeiling.A3_CONSEQUENTIAL: 3,
        }

        while len(selected) < max_missions:
            ready = []
            for item in candidates.values():
                if item.mission_id in selected_ids or item.mission_id in held:
                    continue
                if any(dep in candidates and dep not in selected_ids for dep in item.dependencies):
                    continue
                if authority_rank[item.authority_ceiling] > authority_rank[authority_ceiling]:
                    held[item.mission_id] = "AUTHORITY_CEILING_EXCEEDED"
                    continue
                if (item.external_effect or item.owner_reserved) and not allow_external_effects:
                    held[item.mission_id] = "OWNER_OR_EFFECT_GATE"
                    continue
                if not envelope.can_fit(used, item.resource_demand):
                    continue
                scarcity = self._scarcity_cost(item, envelope)
                frontier = item.strategic_utility / scarcity
                ready.append((frontier, item))
            if not ready:
                break
            ready.sort(key=lambda pair: (-pair[0], -pair[1].strategic_utility, pair[1].mission_id))
            chosen = ready[0][1]
            selected.append(replace(chosen, lifecycle=MissionLifecycle.SELECTED))
            selected_ids.add(chosen.mission_id)
            used = envelope.consume(used, chosen.resource_demand)

        for item in candidates.values():
            if item.mission_id in selected_ids or item.mission_id in held:
                continue
            unresolved = [dep for dep in item.dependencies if dep in candidates and dep not in selected_ids]
            if unresolved:
                held[item.mission_id] = "DEPENDENCY_NOT_SELECTED"
            elif not envelope.can_fit(used, item.resource_demand):
                held[item.mission_id] = "RESOURCE_ENVELOPE_EXHAUSTED"
            else:
                held[item.mission_id] = "PORTFOLIO_LIMIT_OR_LOWER_FRONTIER"

        body = {
            "selected": [item.mission_id for item in selected],
            "held": sorted(held.items()),
            "resource_usage": used,
        }
        return PortfolioPlan(
            selected=tuple(selected),
            held=tuple(sorted(held.items())),
            resource_usage=used,
            total_utility=sum(item.strategic_utility for item in selected),
            plan_sha256=_stable_hash(body),
        )


@dataclass(frozen=True)
class MissionGenesisSignal:
    signal_id: str
    signal_type: GenesisSignalType
    description: str
    value: float
    confidence: float
    capability: str | None = None
    evidence_refs: tuple[str, ...] = ()
    requires_external_effect: bool = False


class MissionGenesisEngine:
    """Converts bounded evidence signals into mission proposals, never auto-approval."""

    def generate(self, signals: Iterable[MissionGenesisSignal], *, objective_id: str) -> tuple[MissionCandidate, ...]:
        proposals = []
        for signal in sorted(signals, key=lambda item: item.signal_id):
            if _clip(signal.confidence) <= 0.0 or _clip(signal.value) <= 0.0:
                continue
            summary = f"Resolve {signal.signal_type.value.lower()} signal: {signal.description.strip()}"
            capability = signal.capability.strip() if signal.capability else ""
            mission_id = f"GEN-{_stable_hash({'objective': objective_id, 'signal': signal.signal_id})[:16]}"
            proposals.append(
                MissionCandidate(
                    mission_id=mission_id,
                    objective_id=objective_id,
                    summary=summary,
                    outcome_value=_clip(signal.value),
                    unlock_leverage=0.75 if signal.signal_type in {GenesisSignalType.CAPABILITY, GenesisSignalType.DEPENDENCY} else 0.45,
                    success_probability=_clip(signal.confidence),
                    learning_value=0.55,
                    reusability=0.75 if capability else 0.45,
                    cost=0.15,
                    risk=0.10 if not signal.requires_external_effect else 0.35,
                    latency=0.15,
                    required_capabilities=(capability,) if capability and signal.signal_type != GenesisSignalType.CAPABILITY else (),
                    produces_capabilities=(capability,) if capability and signal.signal_type == GenesisSignalType.CAPABILITY else (),
                    resource_demand={"attention": 0.1},
                    authority_ceiling=AuthorityCeiling.A2_BOUNDED_EFFECT if signal.requires_external_effect else AuthorityCeiling.A1_INTERNAL,
                    external_effect=signal.requires_external_effect,
                    owner_reserved=signal.requires_external_effect,
                    evidence_refs=signal.evidence_refs,
                )
            )
        return tuple(proposals)


@dataclass(frozen=True)
class MergeSuggestion:
    canonical_mission_id: str
    duplicate_mission_id: str
    similarity: float
    reason: str


class MissionDeduplicator:
    def compare(self, left: MissionCandidate, right: MissionCandidate) -> float:
        semantic = _jaccard(_tokens(left.summary), _tokens(right.summary))
        required = _jaccard(left.required_capabilities, right.required_capabilities)
        produced = _jaccard(left.produces_capabilities, right.produces_capabilities)
        objective = 1.0 if left.objective_id == right.objective_id else 0.0
        return 0.45 * semantic + 0.25 * required + 0.15 * produced + 0.15 * objective

    def suggestions(self, missions: Iterable[MissionCandidate], *, threshold: float = 0.72) -> tuple[MergeSuggestion, ...]:
        items = sorted(missions, key=lambda item: item.mission_id)
        suggestions = []
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                score = self.compare(left, right)
                if score >= threshold:
                    canonical = min(left.mission_id, right.mission_id)
                    duplicate = right.mission_id if canonical == left.mission_id else left.mission_id
                    suggestions.append(MergeSuggestion(canonical, duplicate, score, "HIGH_INTENT_OVERLAP"))
        return tuple(sorted(suggestions, key=lambda item: (-item.similarity, item.canonical_mission_id, item.duplicate_mission_id)))


@dataclass(frozen=True)
class StrategicGenomeRecord:
    pattern_id: str
    features: tuple[str, ...]
    mission_sequence: tuple[str, ...]
    realized_value: float
    reliability: float
    evidence_refs: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        features: Iterable[str],
        mission_sequence: Iterable[str],
        realized_value: float,
        reliability: float,
        evidence_refs: Iterable[str] = (),
    ) -> "StrategicGenomeRecord":
        body = {
            "features": sorted(set(features)),
            "mission_sequence": tuple(mission_sequence),
            "realized_value": _clip(realized_value),
            "reliability": _clip(reliability),
        }
        return cls(
            pattern_id=_stable_hash(body)[:20],
            features=tuple(body["features"]),
            mission_sequence=tuple(body["mission_sequence"]),
            realized_value=body["realized_value"],
            reliability=body["reliability"],
            evidence_refs=tuple(sorted(set(evidence_refs))),
        )


class StrategicGenomeLibrary:
    def __init__(self, records: Iterable[StrategicGenomeRecord] = ()) -> None:
        self._records = {item.pattern_id: item for item in records}

    def add(self, record: StrategicGenomeRecord) -> None:
        self._records[record.pattern_id] = record

    def recommend(self, features: Iterable[str], *, minimum_similarity: float = 0.3) -> tuple[tuple[StrategicGenomeRecord, float], ...]:
        target = set(features)
        ranked = []
        for item in self._records.values():
            similarity = _jaccard(target, item.features)
            score = similarity * (0.5 + 0.5 * item.reliability) * (0.5 + 0.5 * item.realized_value)
            if similarity >= minimum_similarity:
                ranked.append((item, score))
        return tuple(sorted(ranked, key=lambda pair: (-pair[1], pair[0].pattern_id)))


@dataclass(frozen=True)
class EcologyPlan:
    objective_id: str
    portfolio: PortfolioPlan
    capability_pressure: tuple[CapabilityPressure, ...]
    merge_suggestions: tuple[MergeSuggestion, ...]
    strategic_patterns: tuple[tuple[str, float], ...]
    ecology_sha256: str


class StrategicObjectiveEcology:
    def __init__(
        self,
        *,
        allocator: PortfolioAllocator | None = None,
        centrality: CapabilityCentrality | None = None,
        deduplicator: MissionDeduplicator | None = None,
        genome_library: StrategicGenomeLibrary | None = None,
    ) -> None:
        self.allocator = allocator or PortfolioAllocator()
        self.centrality = centrality or CapabilityCentrality()
        self.deduplicator = deduplicator or MissionDeduplicator()
        self.genomes = genome_library or StrategicGenomeLibrary()

    def plan(
        self,
        *,
        objective: StrategicObjective,
        missions: Iterable[MissionCandidate],
        envelope: ResourceEnvelope,
        strategic_features: Iterable[str] = (),
        max_missions: int = 12,
    ) -> EcologyPlan:
        mission_list = tuple(missions)
        portfolio = self.allocator.allocate(
            mission_list,
            envelope,
            authority_ceiling=objective.authority_ceiling,
            allow_external_effects=False,
            max_missions=max_missions,
        )
        pressure = self.centrality.measure(mission_list)
        merges = self.deduplicator.suggestions(mission_list)
        patterns = tuple((item.pattern_id, score) for item, score in self.genomes.recommend(strategic_features))
        body = {
            "objective_id": objective.objective_id,
            "portfolio": portfolio.plan_sha256,
            "pressure": [(item.capability, item.build_priority) for item in pressure],
            "merges": [(item.canonical_mission_id, item.duplicate_mission_id) for item in merges],
            "patterns": patterns,
        }
        return EcologyPlan(
            objective_id=objective.objective_id,
            portfolio=portfolio,
            capability_pressure=pressure,
            merge_suggestions=merges,
            strategic_patterns=patterns,
            ecology_sha256=_stable_hash(body),
        )
