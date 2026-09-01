from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from sol_61_runtime.sol_62_frontier_primitives import ChampionChallenger

from .provider_attestations import ProviderAttestationStore


class CapabilityGraphError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapabilityNode:
    capability_id: str
    capability: str
    operation: str
    provider: str
    surface: str
    subject: str = "runtime"
    mutating: bool = False
    reversible: bool = True
    authority_level: str = "MISSION_SCOPED"
    proof_quality: float = 1.0
    success_rate: float = 1.0
    latency_ms: float = 1000.0
    cost: float = 0.0
    owner_interventions: float = 0.0
    risk: float = 0.0
    concurrency_limit: int = 1
    conflict_domains: tuple[str, ...] = ()
    attestation_required: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not all(value.strip() for value in (self.capability_id, self.capability, self.operation, self.provider, self.surface)):
            raise CapabilityGraphError("CAPABILITY_IDENTITY_FIELDS_REQUIRED")
        if not 0.0 <= self.proof_quality <= 1.0 or not 0.0 <= self.success_rate <= 1.0:
            raise CapabilityGraphError(f"INVALID_RELIABILITY_METRIC:{self.capability_id}")
        if not 0.0 <= self.risk <= 1.0:
            raise CapabilityGraphError(f"INVALID_RISK:{self.capability_id}")
        if self.latency_ms <= 0 or self.cost < 0 or self.owner_interventions < 0:
            raise CapabilityGraphError(f"INVALID_ROUTE_ECONOMICS:{self.capability_id}")
        if self.concurrency_limit < 1:
            raise CapabilityGraphError(f"INVALID_CONCURRENCY_LIMIT:{self.capability_id}")
        if self.mutating and not self.reversible and self.metadata.get("speculative", False):
            raise CapabilityGraphError(f"SPECULATIVE_IRREVERSIBLE_CAPABILITY_FORBIDDEN:{self.capability_id}")

    def empirical_score(self) -> float:
        base = ChampionChallenger.score(
            {
                "success_rate": self.success_rate,
                "proof_quality": self.proof_quality,
                "latency_ms": self.latency_ms,
                "cost": self.cost,
                "owner_interventions": self.owner_interventions,
            }
        )
        return base - 0.15 * self.risk


@dataclass(frozen=True)
class CapabilityRoute:
    capability_id: str
    capability: str
    operation: str
    provider: str
    surface: str
    subject: str
    score: float
    mutating: bool
    reversible: bool
    authority_level: str
    concurrency_limit: int
    conflict_domains: tuple[str, ...]
    attestation_id: str | None
    evidence_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


class CapabilityGraph:
    """Semantic capability graph above provider-specific route implementations.

    The graph answers "what verified capability can satisfy this transition?"
    rather than hard-coding a provider. Provider-backed nodes may require a
    fresh ProviderAttestation; local/deterministic nodes can remain unattested.
    """

    def __init__(self, nodes: Sequence[CapabilityNode] = ()):
        self._nodes: dict[str, CapabilityNode] = {}
        for node in nodes:
            self.add(node)

    def add(self, node: CapabilityNode) -> None:
        node.validate()
        prior = self._nodes.get(node.capability_id)
        if prior is not None and prior != node:
            raise CapabilityGraphError(f"CAPABILITY_ID_COLLISION:{node.capability_id}")
        self._nodes[node.capability_id] = node

    def nodes(self) -> tuple[CapabilityNode, ...]:
        return tuple(self._nodes[key] for key in sorted(self._nodes))

    def candidates(
        self,
        capability: str,
        *,
        now_epoch: int,
        attestation_store: ProviderAttestationStore | None = None,
        required_operation: str | None = None,
        authority_ceiling: str | None = None,
        allow_mutation: bool = True,
    ) -> tuple[CapabilityRoute, ...]:
        requested = capability.strip().upper()
        routes: list[CapabilityRoute] = []
        for node in self.nodes():
            if node.capability.upper() != requested:
                continue
            if required_operation is not None and node.operation != required_operation:
                continue
            if not allow_mutation and node.mutating:
                continue
            if authority_ceiling is not None and node.authority_level != authority_ceiling:
                continue

            attestation_id: str | None = None
            evidence_refs: tuple[str, ...] = ()
            if node.attestation_required:
                if attestation_store is None:
                    continue
                attestation = attestation_store.resolve(
                    provider=node.provider,
                    surface=node.surface,
                    subject=node.subject,
                    capability=node.capability,
                    now_epoch=now_epoch,
                )
                if attestation is None:
                    continue
                attestation_id = attestation.attestation_id
                evidence_refs = attestation.evidence_refs

            routes.append(
                CapabilityRoute(
                    capability_id=node.capability_id,
                    capability=node.capability.upper(),
                    operation=node.operation,
                    provider=node.provider.upper(),
                    surface=node.surface.upper(),
                    subject=node.subject,
                    score=node.empirical_score(),
                    mutating=node.mutating,
                    reversible=node.reversible,
                    authority_level=node.authority_level,
                    concurrency_limit=node.concurrency_limit,
                    conflict_domains=tuple(sorted(set(node.conflict_domains))),
                    attestation_id=attestation_id,
                    evidence_refs=evidence_refs,
                    metadata=dict(node.metadata),
                )
            )
        routes.sort(key=lambda item: (-item.score, item.cost if hasattr(item, "cost") else 0, item.capability_id))
        return tuple(routes)

    def best_route(self, capability: str, **kwargs: Any) -> CapabilityRoute:
        routes = self.candidates(capability, **kwargs)
        if not routes:
            raise CapabilityGraphError(f"NO_VERIFIED_CAPABILITY_ROUTE:{capability}")
        return routes[0]

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": "SLOS_CAPABILITY_GRAPH_V1",
            "node_count": len(self._nodes),
            "nodes": [
                {
                    "capability_id": node.capability_id,
                    "capability": node.capability,
                    "operation": node.operation,
                    "provider": node.provider,
                    "surface": node.surface,
                    "mutating": node.mutating,
                    "reversible": node.reversible,
                    "authority_level": node.authority_level,
                    "proof_quality": node.proof_quality,
                    "success_rate": node.success_rate,
                    "latency_ms": node.latency_ms,
                    "cost": node.cost,
                    "risk": node.risk,
                    "concurrency_limit": node.concurrency_limit,
                    "conflict_domains": list(node.conflict_domains),
                    "attestation_required": node.attestation_required,
                }
                for node in self.nodes()
            ],
        }


__all__ = [
    "CapabilityGraph",
    "CapabilityGraphError",
    "CapabilityNode",
    "CapabilityRoute",
]
