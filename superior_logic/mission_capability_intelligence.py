from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import IntEnum
from typing import Iterable, Mapping


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class SurfaceReadiness(IntEnum):
    DISCOVERED = 10
    CONFIGURED = 20
    REACHABLE = 30
    AUTHENTICATED = 40
    EXECUTION_PROVEN = 50
    ARTIFACT_RETURN_PROVEN = 60
    CLEANUP_PROVEN = 70
    LOAD_TESTED = 80
    FAILOVER_PROVEN = 90
    TRUSTED_FOR_HEAVY_COMPUTE = 100


@dataclass(frozen=True, slots=True)
class MachineGenome:
    os_family: str
    cpu_class: str = "UNKNOWN"
    logical_cores: int = 0
    ram_mib: int = 0
    gpu_class: str = "NONE"
    gpu_vram_mib: int = 0
    container_runtime: str = "UNKNOWN"
    toolchain_digest: str = ""

    @property
    def genome_sha256(self) -> str:
        return _sha(asdict(self))


@dataclass(frozen=True, slots=True)
class ExecutionSurface:
    surface_id: str
    surface_type: str
    provider: str
    readiness: SurfaceReadiness
    capabilities: tuple[str, ...]
    authority_actions: tuple[str, ...] = ()
    owner_controlled: bool = False
    current: bool = True
    trust_domain: str = ""
    proof_ref: str = ""
    cost_rank: int = 100
    latency_rank: int = 100
    throughput_rank: int = 0
    genome: MachineGenome | None = None

    def supports(self, required: Iterable[str]) -> bool:
        available = set(self.capabilities)
        return set(required) <= available

    @property
    def machine_native_execution_proven(self) -> bool:
        return self.readiness >= SurfaceReadiness.EXECUTION_PROVEN and bool(self.proof_ref.strip())


@dataclass(frozen=True, slots=True)
class MissionResourceRequest:
    mission_id: str
    required_capabilities: tuple[str, ...]
    preferred_capabilities: tuple[str, ...] = ()
    heavy_compute: bool = False
    prefer_owner_controlled: bool = True
    privacy_sensitive: bool = False
    external_effects: bool = False
    required_authority_actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResourcePlan:
    mission_id: str
    selected_surface_ids: tuple[str, ...]
    qualified_surface_ids: tuple[str, ...]
    rejected_surface_ids: tuple[str, ...]
    capability_gaps: tuple[str, ...]
    degraded_compute_mode: bool
    owner_controlled_heavy_compute_available: bool
    windows_execution_proven: bool
    effect_authority_granted: bool
    decision_reasons: tuple[str, ...]
    plan_sha256: str


class MissionCapabilityIntelligence:
    """Deterministic no-effect resource/capability preflight.

    This component only ranks declared execution surfaces. It does not discover
    credentials, install software, dispatch jobs, mutate infrastructure, or grant
    effect authority. A Windows surface counts as executed only when the caller
    supplies a current machine-native proof reference at EXECUTION_PROVEN or above.
    """

    @staticmethod
    def _rank(surface: ExecutionSurface, request: MissionResourceRequest) -> tuple[int, ...]:
        preferred = len(set(surface.capabilities) & set(request.preferred_capabilities))
        owner_bonus = 1 if (request.prefer_owner_controlled and surface.owner_controlled) else 0
        privacy_bonus = 1 if (request.privacy_sensitive and surface.owner_controlled) else 0
        return (
            owner_bonus,
            privacy_bonus,
            int(surface.readiness),
            preferred,
            surface.throughput_rank,
            -surface.latency_rank,
            -surface.cost_rank,
        )

    def compile(
        self,
        request: MissionResourceRequest,
        surfaces: Iterable[ExecutionSurface],
    ) -> ResourcePlan:
        if not request.mission_id.strip():
            raise ValueError("mission_id required")
        required = tuple(sorted(set(request.required_capabilities)))
        required_auth = set(request.required_authority_actions)
        rows = tuple(surfaces)
        if len({row.surface_id for row in rows}) != len(rows):
            raise ValueError("duplicate surface_id")

        rejected: list[str] = []
        qualified: list[ExecutionSurface] = []
        reasons: list[str] = []
        for row in rows:
            if not row.current:
                rejected.append(row.surface_id)
                continue
            if not row.supports(required):
                rejected.append(row.surface_id)
                continue
            if not required_auth <= set(row.authority_actions):
                rejected.append(row.surface_id)
                continue
            if row.readiness < SurfaceReadiness.EXECUTION_PROVEN or not row.proof_ref.strip():
                rejected.append(row.surface_id)
                continue
            qualified.append(row)

        qualified.sort(key=lambda row: (self._rank(row, request), row.surface_id), reverse=True)
        selected: tuple[ExecutionSurface, ...] = tuple(qualified[:1])

        owner_heavy = any(
            row.owner_controlled
            and row.machine_native_execution_proven
            and row.supports(required)
            for row in rows
            if row.current
        )
        windows_proven = any(
            row.surface_type.upper().startswith("WINDOWS")
            and row.machine_native_execution_proven
            for row in selected
        )

        gaps: list[str] = []
        if not selected:
            gaps.extend(f"CAPABILITY:{cap}" for cap in required)
            gaps.append("LIVE_EXECUTION_BINDING")
            reasons.append("NO_EXECUTION_PROVEN_SURFACE_MATCHES_REQUIREMENTS")
        if request.heavy_compute and request.prefer_owner_controlled and not owner_heavy:
            gaps.append("OWNER_CONTROLLED_HEAVY_COMPUTE")
            reasons.append("PREFERRED_OWNER_HEAVY_COMPUTE_UNAVAILABLE")

        degraded = bool(request.heavy_compute and request.prefer_owner_controlled and not owner_heavy)
        if selected:
            reasons.append(f"SELECTED:{selected[0].surface_id}")
            if degraded:
                reasons.append("DEGRADED_COMPUTE_MODE")

        body: Mapping[str, object] = {
            "mission_id": request.mission_id,
            "selected": tuple(row.surface_id for row in selected),
            "qualified": tuple(row.surface_id for row in qualified),
            "rejected": tuple(sorted(rejected)),
            "gaps": tuple(sorted(set(gaps))),
            "degraded": degraded,
            "owner_heavy": owner_heavy,
            "windows_execution_proven": windows_proven,
            "effect_authority_granted": False,
            "reasons": tuple(reasons),
        }
        return ResourcePlan(
            mission_id=request.mission_id,
            selected_surface_ids=tuple(row.surface_id for row in selected),
            qualified_surface_ids=tuple(row.surface_id for row in qualified),
            rejected_surface_ids=tuple(sorted(rejected)),
            capability_gaps=tuple(sorted(set(gaps))),
            degraded_compute_mode=degraded,
            owner_controlled_heavy_compute_available=owner_heavy,
            windows_execution_proven=windows_proven,
            effect_authority_granted=False,
            decision_reasons=tuple(reasons),
            plan_sha256=_sha(body),
        )
