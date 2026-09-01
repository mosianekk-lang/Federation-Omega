from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


class DigitalTwinError(ValueError):
    pass


@dataclass(frozen=True)
class CapabilityEdge:
    capability_id: str
    provider: str
    operation: str
    target_class: str
    authority: str
    proof_strength: float
    latency_ms: int
    cost: float
    risk: float
    reversible: bool
    available: bool = True
    tags: tuple[str, ...] = ()

    @property
    def fitness(self) -> float:
        return (
            (self.proof_strength * 2.0)
            + (1.0 if self.reversible else 0.0)
            - self.cost
            - self.risk
            - min(max(self.latency_ms, 0) / 100_000.0, 1.0)
        )


@dataclass(frozen=True)
class RouteCandidate:
    capability_id: str
    provider: str
    operation: str
    fitness: float
    authority: str
    reversible: bool


class FederationDigitalTwin:
    """Small deterministic operational twin for route synthesis.

    It is intentionally a state model, not an executor. Availability/proof observations
    can be refreshed independently of source code.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityEdge] = {}

    def upsert(self, capability: CapabilityEdge) -> None:
        if not capability.capability_id.strip():
            raise DigitalTwinError("capability_id is required")
        for score_name, score in (("proof_strength", capability.proof_strength), ("risk", capability.risk)):
            if not 0.0 <= score <= 1.0:
                raise DigitalTwinError(f"{score_name} outside [0,1]")
        self._capabilities[capability.capability_id] = capability

    def remove(self, capability_id: str) -> None:
        self._capabilities.pop(capability_id, None)

    def snapshot(self) -> tuple[CapabilityEdge, ...]:
        return tuple(sorted(self._capabilities.values(), key=lambda x: x.capability_id))

    def synthesize(
        self,
        *,
        operation: str,
        target_class: str,
        max_risk: float = 1.0,
        min_proof_strength: float = 0.0,
        require_reversible: bool = False,
        allowed_authorities: Iterable[str] | None = None,
        limit: int = 5,
    ) -> tuple[RouteCandidate, ...]:
        authorities = set(allowed_authorities) if allowed_authorities is not None else None
        matches: list[CapabilityEdge] = []
        for cap in self._capabilities.values():
            if not cap.available:
                continue
            if cap.operation != operation or cap.target_class != target_class:
                continue
            if cap.risk > max_risk or cap.proof_strength < min_proof_strength:
                continue
            if require_reversible and not cap.reversible:
                continue
            if authorities is not None and cap.authority not in authorities:
                continue
            matches.append(cap)
        matches.sort(key=lambda x: (-x.fitness, x.latency_ms, x.capability_id))
        return tuple(
            RouteCandidate(
                capability_id=cap.capability_id,
                provider=cap.provider,
                operation=cap.operation,
                fitness=cap.fitness,
                authority=cap.authority,
                reversible=cap.reversible,
            )
            for cap in matches[: max(limit, 0)]
        )

    def opportunity_gaps(self, required: Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
        existing = {(c.operation, c.target_class) for c in self._capabilities.values() if c.available}
        return tuple(sorted(set(required) - existing))


__all__ = ["CapabilityEdge", "DigitalTwinError", "FederationDigitalTwin", "RouteCandidate"]
