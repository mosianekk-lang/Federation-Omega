from __future__ import annotations

"""FUSE Cognitive Surface Fabric v1.

Pure planning/binding layer beneath the existing FUSE Sovereign Plane. It binds
Formation, Hypercube and Alpha-Omega to the user's qualified Apps Script,
Google AI Studio/Gemini, Canva and OpenRouter surfaces without calling a
provider, resolving credentials, minting authority or promoting completion.
"""

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from federation.formation_surface_load_balancer_v1 import (
    FormationSurfaceLoadBalancer,
    FormationWorkPackage,
    SurfaceFormationPlan,
    SurfaceRuntimeState,
    WorkKind,
)
from federation.omnisurface_fabric_v2 import EffectClass
from superior_logic.hypercube_bottleneck_resolver import (
    BottleneckSignal,
    HypercubeBottleneckResolver,
)

SCHEMA = "FUSE_COGNITIVE_SURFACE_FABRIC_V1"
VERSION = "1.0.0"
CONTRACT_ID = "FUSE-COGNITIVE-SURFACE-FABRIC-001"
EXTERNAL_EFFECTS = False
AUTHORITY_MINTING = False
PROVIDER_EXECUTION = False

ALPHA_OMEGA_LIFECYCLE = (
    "DISCOVERY",
    "DECOMPOSITION",
    "ARCHITECTURE",
    "BUILD",
    "TEST",
    "DEPLOY",
    "VERIFY",
    "OPERATE",
    "MAINTAIN",
)

SURFACE_ROLES: Mapping[str, tuple[str, ...]] = {
    "GOOGLE-APPS-SCRIPT": (
        "workspace_automation",
        "queue_heartbeat",
        "event_wakeup",
        "deterministic_transform",
    ),
    "GOOGLE-AI-STUDIO-GEMINI": (
        "reasoning",
        "multimodal",
        "structured_output",
        "candidate_research",
    ),
    "CANVA": (
        "design",
        "presentation",
        "visual_mission_genome",
        "customer_artifact",
    ),
    "OPENROUTER": (
        "challenger",
        "provider_marketplace",
        "benchmarking",
        "model_diversity",
    ),
    "HYPERCUBE": (
        "bottleneck_detection",
        "mechanism_harvest",
        "failure_learning",
        "residual_invention",
    ),
}


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: object) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


def _clean(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


@dataclass(frozen=True, slots=True)
class CognitivePacket:
    mission_id: str
    objective: str
    acceptance_predicates: tuple[str, ...]
    authority_ceiling: str = "A1_INTERNAL"
    privacy_class: str = "P1_INTERNAL"
    cost_ceiling: float = 0.0
    required_capabilities: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    uncertainty: tuple[str, ...] = ()
    falsifiers: tuple[str, ...] = ()
    deadline_seconds: int = 300
    proof_floor: str = "SEMANTIC_READBACK"
    idempotency_key: str = ""
    automation_required: bool = False
    research_required: bool = False
    creative_required: bool = False
    challenger_required: bool = False
    maximum_effect: EffectClass = EffectClass.INTERNAL

    def validate(self) -> "CognitivePacket":
        if not self.mission_id.strip() or not self.objective.strip():
            raise ValueError("COGNITIVE_PACKET_MISSION_AND_OBJECTIVE_REQUIRED")
        if not self.acceptance_predicates:
            raise ValueError("COGNITIVE_PACKET_ACCEPTANCE_PREDICATES_REQUIRED")
        if self.cost_ceiling < 0:
            raise ValueError("COGNITIVE_PACKET_COST_CEILING_INVALID")
        if self.deadline_seconds < 1:
            raise ValueError("COGNITIVE_PACKET_DEADLINE_INVALID")
        if self.authority_ceiling not in {"A0_INTERNAL", "A1_INTERNAL"}:
            raise ValueError("COGNITIVE_PACKET_AUTHORITY_CEILING_EXCEEDS_INTERNAL_BINDING")
        if self.maximum_effect not in {EffectClass.OBSERVE, EffectClass.INTERNAL}:
            raise ValueError("COGNITIVE_PACKET_EFFECT_CEILING_EXCEEDS_INTERNAL_BINDING")
        return self


@dataclass(frozen=True, slots=True)
class AlphaOmegaResidualPacket:
    mission_id: str
    residual_capabilities: tuple[str, ...]
    lifecycle: tuple[str, ...]
    proof_gates: tuple[str, ...]
    authority_ceiling: str
    provider_effect_authorized: bool
    truth_boundary: str

    @property
    def required(self) -> bool:
        return bool(self.residual_capabilities)


@dataclass(frozen=True, slots=True)
class CognitiveSurfacePlan:
    schema: str
    version: str
    contract_id: str
    plan_id: str
    mission_id: str
    formation: SurfaceFormationPlan
    hypercube_required: bool
    hypercube_resolution: Mapping[str, Any] | None
    alpha_omega: AlphaOmegaResidualPacket
    cognitive_graph_edges: tuple[tuple[str, str, str], ...]
    external_effect_authorized: bool
    provider_execution_proven: bool
    authority_minted: bool
    truth_boundary: str

    @property
    def complete(self) -> bool:
        return self.formation.complete and not self.alpha_omega.required

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class CognitiveSurfaceFabric:
    """Compile minimum-sufficient cognitive surface plans plus bounded residuals."""

    TRUTH_BOUNDARY = (
        "COGNITIVE_SURFACE_PLAN_COMPILED!=SURFACE_CALLABLE!=PROVIDER_EXECUTED"
        "!=SEMANTIC_READBACK!=ALPHA_OMEGA_BUILD_EXECUTED!=OWNER_VALUE!=COMPLETE"
    )

    def __init__(
        self,
        *,
        balancer: FormationSurfaceLoadBalancer | None = None,
        hypercube: HypercubeBottleneckResolver | None = None,
    ) -> None:
        self.balancer = balancer or FormationSurfaceLoadBalancer()
        self.hypercube = hypercube or HypercubeBottleneckResolver()

    @staticmethod
    def _packages(packet: CognitivePacket) -> tuple[FormationWorkPackage, ...]:
        packages: list[FormationWorkPackage] = []
        covered: set[str] = set()

        if packet.automation_required:
            packages.append(
                FormationWorkPackage(
                    "apps-script-automation",
                    WorkKind.AUTOMATION,
                    ("workspace_automation",),
                    preferred_surface_ids=("GOOGLE-APPS-SCRIPT",),
                )
            )
            covered.add("workspace_automation")

        if packet.research_required:
            packages.append(
                FormationWorkPackage(
                    "gemini-cognition",
                    WorkKind.COGNITION,
                    ("reasoning", "structured_output"),
                    preferred_surface_ids=("GOOGLE-AI-STUDIO-GEMINI",),
                )
            )
            covered.update(("reasoning", "structured_output"))

        if packet.creative_required:
            packages.append(
                FormationWorkPackage(
                    "canva-creative",
                    WorkKind.CREATIVE,
                    ("design",),
                    preferred_surface_ids=("CANVA",),
                )
            )
            covered.add("design")

        if packet.challenger_required:
            packages.append(
                FormationWorkPackage(
                    "openrouter-challenger",
                    WorkKind.COGNITION,
                    ("challenger", "provider_marketplace"),
                    preferred_surface_ids=("OPENROUTER",),
                )
            )
            covered.update(("challenger", "provider_marketplace"))

        remaining = tuple(
            capability
            for capability in _clean(packet.required_capabilities)
            if capability not in covered
        )
        if remaining:
            packages.append(
                FormationWorkPackage(
                    "mission-capability",
                    WorkKind.GENERAL,
                    remaining,
                    allow_composition=True,
                )
            )

        if not packages:
            packages.append(
                FormationWorkPackage(
                    "default-cognition",
                    WorkKind.COGNITION,
                    ("reasoning",),
                    preferred_surface_ids=("GOOGLE-AI-STUDIO-GEMINI",),
                )
            )
        return tuple(packages)

    @staticmethod
    def _edges(
        packet: CognitivePacket,
        formation: SurfaceFormationPlan,
        residuals: tuple[str, ...],
    ) -> tuple[tuple[str, str, str], ...]:
        edges: list[tuple[str, str, str]] = []
        for surface_id in formation.selected_surface_ids:
            edges.append((packet.mission_id, "ROUTES_THROUGH", surface_id))
        for proof_ref in _clean(packet.evidence_refs):
            edges.append((packet.mission_id, "REQUIRES_EVIDENCE", proof_ref))
        for capability in residuals:
            edges.append((packet.mission_id, "REQUIRES_CAPABILITY", capability))
        return tuple(edges)

    def compile(
        self,
        *,
        packet: CognitivePacket,
        runtime_states: Sequence[SurfaceRuntimeState],
        bottleneck_signal: BottleneckSignal | None = None,
        max_parallel_surfaces: int = 4,
    ) -> CognitiveSurfacePlan:
        packet.validate()
        packages = self._packages(packet)
        formation = self.balancer.compile(
            mission_id=packet.mission_id,
            packages=packages,
            runtime_states=runtime_states,
            max_parallel_surfaces=max_parallel_surfaces,
            total_cost_ceiling=packet.cost_ceiling if packet.cost_ceiling > 0 else float("inf"),
        )
        residuals = _clean(
            capability
            for assignment in formation.assignments
            for capability in assignment.missing_capabilities
        )

        hypercube_resolution: Mapping[str, Any] | None = None
        if residuals and bottleneck_signal is not None:
            resolved = self.hypercube.resolve(bottleneck_signal)
            hypercube_resolution = {
                "bottleneck_id": resolved.bottleneck_id,
                "action_state": resolved.action_state,
                "selected_candidate_id": resolved.selected.candidate_id,
                "selected_family": resolved.selected.family.value,
                "market_harvest": resolved.market_harvest,
                "internal_harvest": resolved.internal_harvest,
                "invention_required": resolved.invention_required,
                "external_effect_authorized": resolved.external_effect_authorized,
                "stable_self_promotion_allowed": resolved.stable_self_promotion_allowed,
                "receipt_sha256": resolved.receipt_sha256,
            }

        alpha_omega = AlphaOmegaResidualPacket(
            mission_id=packet.mission_id,
            residual_capabilities=residuals,
            lifecycle=ALPHA_OMEGA_LIFECYCLE,
            proof_gates=("TEST", "ROLLBACK", "SEMANTIC_READBACK", "INDEPENDENT_JUDGE"),
            authority_ceiling=packet.authority_ceiling,
            provider_effect_authorized=False,
            truth_boundary=(
                "ALPHA_OMEGA_RESIDUAL_PACKET!=BUILD_EXECUTED!=SOURCE_ADMITTED"
                "!=PROVIDER_DEPLOYED!=OPERATIONAL_VERIFIED"
            ),
        )

        core = {
            "schema": SCHEMA,
            "version": VERSION,
            "contract_id": CONTRACT_ID,
            "mission_id": packet.mission_id,
            "formation_plan_id": formation.plan_id,
            "selected_surfaces": formation.selected_surface_ids,
            "residual_capabilities": residuals,
            "hypercube_receipt": (
                hypercube_resolution.get("receipt_sha256")
                if hypercube_resolution is not None
                else None
            ),
            "alpha_omega_required": alpha_omega.required,
        }
        return CognitiveSurfacePlan(
            schema=SCHEMA,
            version=VERSION,
            contract_id=CONTRACT_ID,
            plan_id="FUSE-COGNITIVE-SURFACE-" + _digest(core)[:24].upper(),
            mission_id=packet.mission_id,
            formation=formation,
            hypercube_required=bool(residuals),
            hypercube_resolution=hypercube_resolution,
            alpha_omega=alpha_omega,
            cognitive_graph_edges=self._edges(packet, formation, residuals),
            external_effect_authorized=False,
            provider_execution_proven=False,
            authority_minted=False,
            truth_boundary=self.TRUTH_BOUNDARY,
        )


__all__ = [
    "SCHEMA",
    "VERSION",
    "CONTRACT_ID",
    "SURFACE_ROLES",
    "CognitivePacket",
    "AlphaOmegaResidualPacket",
    "CognitiveSurfacePlan",
    "CognitiveSurfaceFabric",
]
