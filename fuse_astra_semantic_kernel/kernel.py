from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, Iterable, List, Mapping, MutableMapping, Set, Tuple


class Maturity(IntEnum):
    DESIGN_LOCKED = 0
    LOCAL_COMPONENT = 1
    LOCAL_INTEGRATED = 2
    REPRODUCIBLE = 3
    PROVIDER_INTEROP = 4
    MULTI_PROVIDER_SOVEREIGN = 5
    FUSE_CONTROLLED_RUNTIME = 6
    PRODUCTION_VERIFIED = 7


@dataclass(frozen=True)
class SemanticCapability:
    semantic_id: str
    plane: str
    contract: str
    maturity: Maturity = Maturity.DESIGN_LOCKED
    aliases: Tuple[str, ...] = ()
    evidence: Tuple[str, ...] = ()
    dependencies: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Implementation:
    impl_id: str
    capability_id: str
    provider: str
    quality: float
    latency_ms: float
    cost_units: float
    sovereignty: float
    maturity: Maturity
    authority_ok: bool = True
    residency_ok: bool = True
    safety_ok: bool = True
    proof_ok: bool = False
    local: bool = False

    def satisfies(self, *, min_quality: float, min_maturity: Maturity) -> bool:
        return (
            self.quality >= min_quality
            and self.maturity >= min_maturity
            and self.authority_ok
            and self.residency_ok
            and self.safety_ok
            and self.proof_ok
        )


@dataclass(frozen=True)
class CapabilityProfile:
    profile_id: str
    required_capabilities: Tuple[str, ...]
    min_quality: float = 0.0
    min_maturity: Maturity = Maturity.LOCAL_COMPONENT
    require_astra_independent: bool = False
    prefer_local: bool = False


@dataclass(frozen=True)
class CompiledRoute:
    profile_id: str
    selected: Mapping[str, Implementation]
    total_cost_units: float
    worst_latency_ms: float
    average_quality: float
    average_sovereignty: float

    @property
    def providers(self) -> Set[str]:
        return {impl.provider for impl in self.selected.values()}

    @property
    def astra_independent(self) -> bool:
        return "openai" not in self.providers


class AmbiguousAliasError(ValueError):
    pass


class CapabilityRegistry:
    """Canonical registry keyed by semantic identity.

    Historical numeric IDs are non-authoritative aliases and may map to more than
    one semantic capability. Alias collisions are surfaced and never allowed to
    overwrite canonical semantic identity.
    """

    def __init__(self) -> None:
        self._caps: Dict[str, SemanticCapability] = {}
        self._aliases: MutableMapping[str, Set[str]] = {}

    def register(self, capability: SemanticCapability) -> None:
        existing = self._caps.get(capability.semantic_id)
        if existing is not None and existing != capability:
            raise ValueError(
                f"semantic capability already exists with different definition: {capability.semantic_id}"
            )
        self._caps[capability.semantic_id] = capability
        for alias in capability.aliases:
            self._aliases.setdefault(alias, set()).add(capability.semantic_id)

    def get(self, semantic_id: str) -> SemanticCapability:
        return self._caps[semantic_id]

    def resolve_alias(self, alias: str) -> SemanticCapability:
        matches = sorted(self._aliases.get(alias, ()))
        if not matches:
            raise KeyError(alias)
        if len(matches) != 1:
            raise AmbiguousAliasError(f"{alias} maps to {matches}")
        return self._caps[matches[0]]

    def alias_matches(self, alias: str) -> Tuple[str, ...]:
        return tuple(sorted(self._aliases.get(alias, ())))

    def semantic_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._caps))


class CapabilityCompiler:
    """Compile a semantic profile into a route using hard gates first, economics second."""

    def __init__(self, registry: CapabilityRegistry, implementations: Iterable[Implementation]) -> None:
        self.registry = registry
        self._impls: Dict[str, List[Implementation]] = {}
        for impl in implementations:
            self._impls.setdefault(impl.capability_id, []).append(impl)

    @staticmethod
    def _score(impl: Implementation, *, prefer_local: bool) -> float:
        local_bonus = 0.15 if prefer_local and impl.local else 0.0
        return (
            impl.cost_units
            + (impl.latency_ms / 10000.0)
            - (impl.quality * 0.75)
            - (impl.sovereignty * 0.35)
            - local_bonus
        )

    def compile(self, profile: CapabilityProfile) -> CompiledRoute:
        selected: Dict[str, Implementation] = {}
        for cap_id in profile.required_capabilities:
            self.registry.get(cap_id)
            candidates = [
                impl
                for impl in self._impls.get(cap_id, ())
                if impl.satisfies(
                    min_quality=profile.min_quality,
                    min_maturity=profile.min_maturity,
                )
            ]
            if profile.require_astra_independent:
                candidates = [impl for impl in candidates if impl.provider != "openai"]
            if not candidates:
                raise RuntimeError(f"no qualified implementation for {cap_id}")
            selected[cap_id] = min(
                candidates,
                key=lambda i: (self._score(i, prefer_local=profile.prefer_local), i.impl_id),
            )

        vals = list(selected.values())
        return CompiledRoute(
            profile_id=profile.profile_id,
            selected=selected,
            total_cost_units=sum(v.cost_units for v in vals),
            worst_latency_ms=max((v.latency_ms for v in vals), default=0.0),
            average_quality=sum(v.quality for v in vals) / len(vals) if vals else 0.0,
            average_sovereignty=sum(v.sovereignty for v in vals) / len(vals) if vals else 0.0,
        )


def build_default_registry() -> CapabilityRegistry:
    r = CapabilityRegistry()
    for semantic_id, plane, contract, aliases, maturity in [
        ("CK.STATE", "STATE", "Durable mission state independent of processor/session.", ("IH-02", "IH-06", "IH-86"), Maturity.LOCAL_COMPONENT),
        ("CK.CONTEXT", "CONTEXT", "Provenance-aware retrieval, compaction and invalidation.", ("IH-09", "IH-83"), Maturity.LOCAL_COMPONENT),
        ("CK.MODEL", "MODEL", "Provider/local model abstraction and measured routing.", ("IH-69", "IH-73"), Maturity.DESIGN_LOCKED),
        ("CK.TOOL", "TOOL", "Typed tool/MCP/A2A execution with semantic readback.", ("IH-19", "IH-89"), Maturity.LOCAL_COMPONENT),
        ("CK.EXEC", "EXEC", "Reproducible sandbox/shell/computer execution.", ("IH-27", "IH-90"), Maturity.LOCAL_COMPONENT),
        ("CK.IDENTITY", "IDENTITY", "Short-lived workload identity and attestation.", ("IH-36",), Maturity.DESIGN_LOCKED),
        ("CK.POLICY", "POLICY", "Deterministic authority, data, spend and safety gates.", ("IH-03", "IH-123"), Maturity.LOCAL_COMPONENT),
        ("CK.AGENT", "AGENT", "Ephemeral specialist composition and lifecycle.", ("IH-08", "IH-37"), Maturity.DESIGN_LOCKED),
        ("CK.OBSERVE", "OBSERVE", "Unified traces, metrics, cost and failure telemetry.", ("IH-43", "IH-101"), Maturity.LOCAL_COMPONENT),
        ("CK.EVAL", "EVAL", "Frozen matched visible/adversarial/hidden evaluation.", ("IH-44", "IH-103"), Maturity.DESIGN_LOCKED),
        ("CK.PROOF", "PROOF", "Causal claims, readback, provenance and maturity.", ("IH-46", "IH-47"), Maturity.LOCAL_COMPONENT),
        ("CK.ARTIFACT", "ARTIFACT", "Cross-artifact generation from canonical state.", ("IH-62", "IH-94"), Maturity.DESIGN_LOCKED),
    ]:
        r.register(
            SemanticCapability(
                semantic_id,
                plane,
                contract,
                maturity=maturity,
                aliases=aliases,
            )
        )

    # The historical IH-109 collision is intentionally preserved so that old
    # evidence remains addressable without letting the numeric alias choose truth.
    r.register(
        SemanticCapability(
            "SERVE.DISAGGREGATED_PREFILL_DECODE",
            "MODEL/SERVE",
            "Conditionally split prefill/decode only when measured topology and load justify it.",
            aliases=("IH-109",),
        )
    )
    r.register(
        SemanticCapability(
            "LANG.EQUIVALENCE_COURT",
            "TOOL/PROTOCOL",
            "Prove translated outcomes preserve semantic state/effects.",
            aliases=("IH-109",),
            maturity=Maturity.LOCAL_COMPONENT,
        )
    )
    return r


PROFILES: Dict[str, CapabilityProfile] = {
    "PROFILE.ASTRA_CLASS.CODING": CapabilityProfile(
        "PROFILE.ASTRA_CLASS.CODING",
        (
            "CK.STATE",
            "CK.CONTEXT",
            "CK.MODEL",
            "CK.TOOL",
            "CK.EXEC",
            "CK.AGENT",
            "CK.EVAL",
            "CK.PROOF",
        ),
        min_quality=0.80,
    ),
    "PROFILE.LONG_HORIZON": CapabilityProfile(
        "PROFILE.LONG_HORIZON",
        ("CK.STATE", "CK.CONTEXT", "CK.AGENT", "CK.OBSERVE", "CK.EVAL", "CK.PROOF"),
        min_quality=0.75,
    ),
    "PROFILE.LOCAL_OFFLINE": CapabilityProfile(
        "PROFILE.LOCAL_OFFLINE",
        ("CK.STATE", "CK.CONTEXT", "CK.MODEL", "CK.TOOL", "CK.EXEC", "CK.PROOF"),
        min_quality=0.70,
        require_astra_independent=True,
        prefer_local=True,
    ),
}
