"""FUSE-GCP Ω v1 — provider-neutral Google Cloud service mesh core.

Composes Formation-style route tournaments with Alpha→Omega lifecycle packets.
Does not create credentials, IAM grants, deployments, provider workers, schedulers,
billing authority, production traffic, or external effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from typing import Iterable, Sequence

SCHEMA = "FUSE-GCP-CLOUD-SERVICE-MESH-V1"
VERSION = "1.0.0"


class EffectClass(str, Enum):
    A0_OBSERVE = "A0_OBSERVE"
    A1_INTERNAL = "A1_INTERNAL"
    A2_PROVIDER_MUTATION = "A2_PROVIDER_MUTATION"
    A3_CONSEQUENTIAL = "A3_CONSEQUENTIAL"


class Stage(str, Enum):
    INTAKE = "INTAKE"
    DISCOVERY = "DISCOVERY"
    DECOMPOSITION = "DECOMPOSITION"
    ARCHITECTURE = "ARCHITECTURE"
    BUILD = "BUILD"
    TEST = "TEST"
    DEPLOY = "DEPLOY"
    VERIFY = "VERIFY"
    OPERATE = "OPERATE"
    MAINTAIN = "MAINTAIN"


@dataclass(frozen=True, slots=True)
class CloudServiceRequest:
    request_id: str
    mission_id: str
    requesting_organ: str
    capability: str
    effect_class: EffectClass
    project: str = ""
    region: str = ""
    target: str = ""
    action: str = ""
    authority_ref: str = ""
    semantic_postcondition: str = ""
    idempotency_key: str = ""

    def validate(self) -> None:
        if not all(x.strip() for x in (self.request_id, self.mission_id, self.requesting_organ, self.capability)):
            raise ValueError("REQUEST_IDENTITY_REQUIRED")
        if self.effect_class in {EffectClass.A2_PROVIDER_MUTATION, EffectClass.A3_CONSEQUENTIAL}:
            required = (self.project, self.target, self.action, self.authority_ref, self.semantic_postcondition, self.idempotency_key)
            if not all(x.strip() for x in required):
                raise ValueError("EFFECT_REQUEST_EXACT_TARGET_AUTHORITY_READBACK_REQUIRED")


@dataclass(frozen=True, slots=True)
class CloudRoute:
    route_id: str
    service: str
    executor: str
    directness: int
    maturity: int
    health: float
    reliability: float
    latency_ms: float
    cost: float
    risk: float
    effect_ceiling: EffectClass
    provider_native: bool = False
    build_required: bool = False
    evidence_refs: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.route_id.strip() or not self.service.strip() or not self.executor.strip():
            raise ValueError("ROUTE_IDENTITY_REQUIRED")
        if not (0 <= self.health <= 1 and 0 <= self.reliability <= 1):
            raise ValueError("HEALTH_RELIABILITY_RANGE")
        if min(self.directness, self.maturity, self.latency_ms, self.cost, self.risk) < 0:
            raise ValueError("ROUTE_METRICS_NONNEGATIVE")


@dataclass(frozen=True, slots=True)
class RankedRoute:
    route: CloudRoute
    score: float
    hold_reason: str = ""


@dataclass(frozen=True, slots=True)
class LogicalBot:
    bot_id: str
    role: str
    mission_id: str
    logical_only: bool = True
    provider_native_worker: bool = False
    may_self_certify: bool = False


@dataclass(frozen=True, slots=True)
class AlphaOmegaPacket:
    stage: Stage
    packet_id: str
    objective: str
    authority: str
    proof_gate: str
    dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CloudPlan:
    schema: str
    version: str
    mission_id: str
    request_id: str
    ranked_routes: tuple[RankedRoute, ...]
    selected_route_id: str
    logical_bots: tuple[LogicalBot, ...]
    provider_native_worker_count: int
    packets: tuple[AlphaOmegaPacket, ...]
    plan_sha256: str


@dataclass(frozen=True, slots=True)
class CloudServiceReceipt:
    request_id: str
    mission_id: str
    project: str
    region: str
    target: str
    action: str
    executor: str
    provider_identity: str
    transport_ok: bool
    semantic_readback_verified: bool
    semantic_postcondition: str
    observed_postcondition: str
    effect_performed: bool
    evidence_refs: tuple[str, ...] = ()

    def verify(self, request: CloudServiceRequest) -> bool:
        request.validate()
        if self.request_id != request.request_id or self.mission_id != request.mission_id:
            return False
        if request.effect_class in {EffectClass.A2_PROVIDER_MUTATION, EffectClass.A3_CONSEQUENTIAL}:
            if (self.project, self.target, self.action) != (request.project, request.target, request.action):
                return False
            if not self.provider_identity.strip() or not self.semantic_readback_verified:
                return False
            if self.observed_postcondition != request.semantic_postcondition:
                return False
        if self.effect_performed and not self.semantic_readback_verified:
            return False
        return self.transport_ok and (not self.effect_performed or self.semantic_readback_verified)


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + sha256(raw.encode("utf-8")).hexdigest()


def _effect_rank(value: EffectClass) -> int:
    return {EffectClass.A0_OBSERVE: 0, EffectClass.A1_INTERNAL: 1, EffectClass.A2_PROVIDER_MUTATION: 2, EffectClass.A3_CONSEQUENTIAL: 3}[value]


class FUSEGCPCloudServiceMesh:
    """Formation route tournament + Alpha→Omega lifecycle compiler."""

    DEFAULT_ROLES = (
        "CLOUD_ARCHITECT_BOT", "PLATFORM_ENGINEER_BOT", "IAM_WIF_IDENTITY_BOT",
        "SECURITY_ZERO_TRUST_BOT", "OBSERVABILITY_SRE_BOT", "PERFORMANCE_BOT",
        "FAILURE_SCIENTIST_BOT", "REDTEAM_PROOF_WITNESS_BOT",
    )

    def rank_routes(self, request: CloudServiceRequest, routes: Sequence[CloudRoute]) -> tuple[RankedRoute, ...]:
        request.validate()
        if not routes:
            raise ValueError("ROUTES_REQUIRED")
        ranked: list[RankedRoute] = []
        for route in routes:
            route.validate()
            hold = ""
            if route.health < 0.5:
                hold = "UNHEALTHY_ROUTE"
            elif _effect_rank(request.effect_class) > _effect_rank(route.effect_ceiling):
                hold = "EFFECT_CEILING_INSUFFICIENT"
            elif request.effect_class in {EffectClass.A2_PROVIDER_MUTATION, EffectClass.A3_CONSEQUENTIAL} and not request.authority_ref:
                hold = "AUTHORITY_REQUIRED"
            score = (5.0 * route.directness + 4.0 * route.maturity + 12.0 * route.health + 12.0 * route.reliability
                     - 0.002 * route.latency_ms - 2.0 * route.cost - 4.0 * route.risk
                     - (100.0 if route.build_required else 0.0))
            if hold:
                score -= 1000.0
            ranked.append(RankedRoute(route=route, score=round(score, 6), hold_reason=hold))
        ranked.sort(key=lambda item: (-item.score, item.route.route_id))
        return tuple(ranked)

    def formation_bots(self, mission_id: str, *, roles: Iterable[str] = ()) -> tuple[LogicalBot, ...]:
        role_set = tuple(dict.fromkeys([*(r.strip() for r in roles if r.strip()), *self.DEFAULT_ROLES]))
        return tuple(LogicalBot(bot_id=f"{mission_id}:{role}", role=role, mission_id=mission_id) for role in role_set)

    def alpha_omega_packets(self, mission_id: str) -> tuple[AlphaOmegaPacket, ...]:
        objectives = {
            Stage.INTAKE: "Seal owner/FUSE objective and terminal criteria",
            Stage.DISCOVERY: "Discover incumbent Cloud capabilities, currentness and reusable routes",
            Stage.DECOMPOSITION: "Split mission into independently verifiable streams",
            Stage.ARCHITECTURE: "Select minimum non-duplicate target architecture",
            Stage.BUILD: "Build only missing minimum differentiator",
            Stage.TEST: "Run healthy/failure/security/idempotency/rollback regression courts",
            Stage.DEPLOY: "Deploy only through exact authorised provider route",
            Stage.VERIFY: "Read back exact provider target and semantic postcondition",
            Stage.OPERATE: "Observe real runtime health, SLO and recovery",
            Stage.MAINTAIN: "Continuously learn, challenge, repair and retire stale capability",
        }
        packets: list[AlphaOmegaPacket] = []
        previous: str | None = None
        for index, stage in enumerate(Stage, 1):
            packet_id = f"{mission_id}:GCP-AO-{index:02d}"
            authority = "A0_A1" if stage in {Stage.INTAKE, Stage.DISCOVERY, Stage.DECOMPOSITION, Stage.ARCHITECTURE, Stage.TEST} else "ACTION_SPECIFIC_PROVIDER_GATED"
            packets.append(AlphaOmegaPacket(stage, packet_id, objectives[stage], authority, f"{stage.value}_READBACK", () if previous is None else (previous,)))
            previous = packet_id
        return tuple(packets)

    def plan(self, request: CloudServiceRequest, routes: Sequence[CloudRoute], *, roles: Iterable[str] = ()) -> CloudPlan:
        ranked = self.rank_routes(request, routes)
        eligible = [item for item in ranked if not item.hold_reason]
        if not eligible:
            raise ValueError("NO_ELIGIBLE_CLOUD_ROUTE")
        selected = eligible[0].route.route_id
        bots = self.formation_bots(request.mission_id, roles=roles)
        packets = self.alpha_omega_packets(request.mission_id)
        payload = {
            "schema": SCHEMA, "version": VERSION,
            "request": (request.request_id, request.mission_id, request.requesting_organ, request.capability, request.effect_class.value),
            "ranked": [(x.route.route_id, x.score, x.hold_reason) for x in ranked],
            "selected": selected,
            "bots": [(b.bot_id, b.role, b.logical_only, b.provider_native_worker) for b in bots],
            "packets": [(p.stage.value, p.packet_id, p.authority, p.proof_gate, p.dependencies) for p in packets],
            "provider_native_worker_count": 0,
        }
        return CloudPlan(SCHEMA, VERSION, request.mission_id, request.request_id, ranked, selected, bots, 0, packets, _digest(payload))
