"""FUSE Mobile v1 provider-neutral gateway contract.

This module is intentionally effect-free. It compiles authenticated capability
manifests and request routes over already-admitted Federation components. It does
not mint provider authority, carry credentials, deploy services, or perform
external effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

CAPABILITY_ID = "FUSE-MOBILE-V1"
SCHEMA = "FUSE-MOBILE-GATEWAY-V1"
VERSION = "1.0.0"

CONTROL_MANIFEST_DOC_ID = "1IdYLpiNXBiYTtWVrCHpaqLu33I_envbk2dtAdp6FRKY"
WORKSTREAM_MANIFEST_DOC_ID = "12_tEikklvbgt_aIprsy_p-i1qXDsteuoepPxskqWwHA"
SYNC_BUS_SHEET_ID = "1N9plg1P3lY0_0w2kWc4WHIH-rqK62Xq1tU5WRYtCWfo"
KIM_DATAVERSE_SHEET_ID = "1dnbLsLf97_dfX12Bd_rNfIhHp01Sf5Rl_pnqKFgJuds"

OPENROUTER_ADAPTER = "sovara.creative.openrouter_adapter"
OPENROUTER_PROCESSOR_MESH = "sovara.creative.openrouter_processor_mesh"
PROVIDER_CELL_REGISTRY = "bubbles.provider_cell_registry"
SEB_PACKAGE = "sovereign_execution_boundary"


class EffectClass(str, Enum):
    READ_ONLY = "READ_ONLY"
    INTERNAL = "INTERNAL"
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"
    EXTERNAL_COMMUNICATION = "EXTERNAL_COMMUNICATION"
    PRIVILEGE_CHANGE = "PRIVILEGE_CHANGE"
    DESTRUCTIVE = "DESTRUCTIVE"
    HIGH_IMPACT = "HIGH_IMPACT"


class Mode(str, Enum):
    AUTO = "AUTO"
    FAST = "FAST"
    THINK = "THINK"
    CREATE = "CREATE"
    BUILD = "BUILD"
    RESEARCH = "RESEARCH"
    EXECUTE = "EXECUTE"
    PRIVATE = "PRIVATE"


@dataclass(frozen=True)
class Capability:
    capability_id: str
    kind: str
    route: str
    health: str = "UNKNOWN"
    authority: str = "NONE"
    freshness_ttl_seconds: int = 0


@dataclass(frozen=True)
class FederationCapabilityManifest:
    subject: str
    issued_at: str
    expires_at: str
    capabilities: tuple[Capability, ...] = field(default_factory=tuple)
    source_scopes: tuple[str, ...] = field(default_factory=tuple)
    model_scopes: tuple[str, ...] = field(default_factory=tuple)
    agent_scopes: tuple[str, ...] = field(default_factory=tuple)
    tool_scopes: tuple[str, ...] = field(default_factory=tuple)
    policies: Mapping[str, str] = field(default_factory=dict)

    def public_view(self) -> dict:
        """Return a mobile-safe view. Never emit credentials or secret values."""
        return {
            "schema": SCHEMA,
            "version": VERSION,
            "subject": self.subject,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "capabilities": [c.__dict__ for c in self.capabilities],
            "source_scopes": list(self.source_scopes),
            "model_scopes": list(self.model_scopes),
            "agent_scopes": list(self.agent_scopes),
            "tool_scopes": list(self.tool_scopes),
            "policies": dict(self.policies),
        }


@dataclass(frozen=True)
class MobileRequest:
    intent: str
    mode: Mode = Mode.AUTO
    requested_sources: tuple[str, ...] = field(default_factory=tuple)
    requested_models: tuple[str, ...] = field(default_factory=tuple)
    requested_agents: tuple[str, ...] = field(default_factory=tuple)
    effect_class: EffectClass = EffectClass.READ_ONLY
    verification: str = "HIGH"


@dataclass(frozen=True)
class RouteDecision:
    strategy: str
    components: tuple[str, ...]
    effect_allowed: bool
    owner_gate_required: bool
    reason: str


def _has_capability(manifest: FederationCapabilityManifest, prefix: str) -> bool:
    return any(c.capability_id.startswith(prefix) and c.health not in {"OFFLINE", "FAILED"} for c in manifest.capabilities)


def route_request(request: MobileRequest, manifest: FederationCapabilityManifest) -> RouteDecision:
    """Compile a minimal, proof-aware route without executing it."""
    if request.effect_class in {
        EffectClass.EXTERNAL_COMMUNICATION,
        EffectClass.PRIVILEGE_CHANGE,
        EffectClass.DESTRUCTIVE,
        EffectClass.HIGH_IMPACT,
    }:
        return RouteDecision(
            strategy="OWNER_GATED",
            components=("Human-First", "SOVARA", "ProofOS"),
            effect_allowed=False,
            owner_gate_required=True,
            reason="Consequential effect requires exact current authority and readback plan.",
        )

    components: list[str] = ["FUSE", "OF50", "FIO"]
    if request.mode in {Mode.RESEARCH, Mode.THINK}:
        components.extend(["KDV", "EvidenceOps", "CFBE"])
    if request.mode == Mode.CREATE:
        components.extend(["SOVARA-Creative", "Artifact-Registry"])
    if request.mode == Mode.BUILD:
        components.extend(["MODISA", "ProofOS"])

    if request.requested_models and any("openrouter" in m.lower() for m in request.requested_models):
        if _has_capability(manifest, "OPENROUTER"):
            components.append(OPENROUTER_PROCESSOR_MESH)
        else:
            components.append("PROVIDER_FALLBACK")

    return RouteDecision(
        strategy=request.mode.value,
        components=tuple(dict.fromkeys(components)),
        effect_allowed=True,
        owner_gate_required=False,
        reason="Safe/internal route compiled from authenticated capability manifest.",
    )


def default_capability_contracts() -> Sequence[Capability]:
    """Reference only source-admitted adapters; runtime health is assigned elsewhere."""
    return (
        Capability("OPENROUTER-CREATIVE-ADAPTER", "MODEL_PROVIDER", OPENROUTER_ADAPTER),
        Capability("OPENROUTER-PROCESSOR-MESH", "MODEL_ROUTER", OPENROUTER_PROCESSOR_MESH),
        Capability("BUBBLES-PROVIDER-CELL-REGISTRY", "PROVIDER_REGISTRY", PROVIDER_CELL_REGISTRY),
        Capability("SEB", "EXECUTION_BOUNDARY", SEB_PACKAGE),
        Capability("KDV", "DATA_PLANE", KIM_DATAVERSE_SHEET_ID),
    )


def validate_manifest(manifest: FederationCapabilityManifest) -> list[str]:
    errors: list[str] = []
    raw = repr(manifest.public_view()).lower()
    forbidden = ("api_key", "secret=", "authorization: bearer", "sk-")
    if any(marker in raw for marker in forbidden):
        errors.append("SECRET_MATERIAL_IN_PUBLIC_MANIFEST")
    if not manifest.subject:
        errors.append("MISSING_SUBJECT")
    if not manifest.expires_at:
        errors.append("MISSING_EXPIRY")
    return errors
