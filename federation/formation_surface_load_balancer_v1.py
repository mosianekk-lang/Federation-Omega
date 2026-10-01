from __future__ import annotations

"""FUSE Formation Surface Load Balancer v1.

Pure planning only. This module discovers eligible surfaces from the existing
OmniSurface registry, ranks them with AO-HARMONIC FormationEngine, and compiles
a minimum-sufficient execution portfolio. It performs no provider call, reads no
credential, grants no authority, spends no money and executes no external effect.
"""

from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Iterable, Mapping, Sequence

from ao_harmonic_v3.science_and_routes import FormationEngine, Route
from federation.omnisurface_fabric_v2 import (
    EffectClass,
    OmniSurfaceRegistry,
    SurfaceDescriptor,
    build_default_registry,
)

SCHEMA = "FUSE_FORMATION_SURFACE_LOAD_BALANCER_V1"
VERSION = "1.0.0"
EXTERNAL_EFFECTS = False
AUTHORITY_MINTING = False
PROVIDER_EXECUTION = False

_EFFECT_ORDER = {
    EffectClass.OBSERVE: 0,
    EffectClass.INTERNAL: 1,
    EffectClass.DRAFT: 2,
    EffectClass.REVERSIBLE_WRITE: 3,
    EffectClass.CONSEQUENTIAL: 4,
    EffectClass.FINANCIAL: 5,
}


def _clean(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _stable(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _digest(value: object) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


class WorkKind(StrEnum):
    COGNITION = "COGNITION"
    AUTOMATION = "AUTOMATION"
    RUNTIME = "RUNTIME"
    CREATIVE = "CREATIVE"
    SOURCE_CONTROL = "SOURCE_CONTROL"
    KNOWLEDGE = "KNOWLEDGE"
    COMMUNICATIONS = "COMMUNICATIONS"
    DEVICE = "DEVICE"
    GENERAL = "GENERAL"


@dataclass(frozen=True, slots=True)
class SurfaceRuntimeState:
    surface_id: str
    authority_pass: bool
    privacy_pass: bool
    currentness_pass: bool
    proof_pass: bool
    health_pass: bool
    quota_pass: bool
    circuit_open: bool = False
    quality: float = 0.0
    reliability: float = 0.0
    proof_strength: float = 0.0
    latency_ms: float = 0.0
    estimated_cost: float = 0.0
    owner_burden: float = 0.0
    privacy_cost: float = 0.0
    maintenance_cost: float = 0.0
    strategic_value: float = 0.0
    parallel_slots: int = 1
    correlation_domains: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()

    def validate(self) -> "SurfaceRuntimeState":
        if not self.surface_id.strip():
            raise ValueError("FORMATION_SURFACE_ID_REQUIRED")
        if self.parallel_slots < 1:
            raise ValueError("FORMATION_SURFACE_PARALLEL_SLOTS_INVALID")
        for value in (
            self.quality,
            self.reliability,
            self.proof_strength,
            self.latency_ms,
            self.estimated_cost,
            self.owner_burden,
            self.privacy_cost,
            self.maintenance_cost,
            self.strategic_value,
        ):
            if value < 0:
                raise ValueError("FORMATION_SURFACE_NEGATIVE_METRIC")
        return self

    @property
    def hard_gates_pass(self) -> bool:
        return all(
            (
                self.authority_pass,
                self.privacy_pass,
                self.currentness_pass,
                self.proof_pass,
                self.health_pass,
                self.quota_pass,
                not self.circuit_open,
            )
        )


@dataclass(frozen=True, slots=True)
class FormationWorkPackage:
    package_id: str
    kind: WorkKind
    capabilities: tuple[str, ...]
    maximum_effect: EffectClass = EffectClass.INTERNAL
    parallelizable: bool = True
    require_independent_candidates: bool = False
    candidate_count: int = 1
    preferred_surface_ids: tuple[str, ...] = ()
    allow_composition: bool = True

    def validate(self) -> "FormationWorkPackage":
        if not self.package_id.strip() or not self.capabilities:
            raise ValueError("FORMATION_WORK_PACKAGE_ID_AND_CAPABILITIES_REQUIRED")
        if self.candidate_count < 1:
            raise ValueError("FORMATION_CANDIDATE_COUNT_INVALID")
        if self.require_independent_candidates and self.candidate_count < 2:
            raise ValueError("FORMATION_INDEPENDENCE_REQUIRES_MULTIPLE_CANDIDATES")
        return self


@dataclass(frozen=True, slots=True)
class PackageAssignment:
    package_id: str
    kind: str
    selected_surface_ids: tuple[str, ...]
    covered_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    independent: bool
    estimated_cost: float
    route_score: float
    proof_refs: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing_capabilities


@dataclass(frozen=True, slots=True)
class HeldSurface:
    package_id: str
    surface_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SurfaceFormationPlan:
    schema: str
    version: str
    plan_id: str
    mission_id: str
    assignments: tuple[PackageAssignment, ...]
    execution_waves: tuple[tuple[str, ...], ...]
    selected_surface_ids: tuple[str, ...]
    held_surfaces: tuple[HeldSurface, ...]
    missing_packages: tuple[str, ...]
    total_estimated_cost: float
    external_effect_authorized: bool
    provider_execution_proven: bool
    authority_minted: bool
    truth_boundary: str

    @property
    def complete(self) -> bool:
        return not self.missing_packages and all(row.complete for row in self.assignments)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


PROVIDER_CELL_TO_SURFACE_ID: Mapping[str, str] = {
    "google-cloud-cloud-run": "GOOGLE-CLOUD",
    "google-apps-script": "GOOGLE-APPS-SCRIPT",
    "openai-private-runtime": "OPENAI-GPT6-ASTRA",
    "openrouter-private-runtime": "OPENROUTER",
    "gemini-private-runtime": "GOOGLE-AI-STUDIO-GEMINI",
}


def runtime_states_from_provider_projection(
    projection: object,
    *,
    authority_by_cell: Mapping[str, bool],
    privacy_by_cell: Mapping[str, bool],
    currentness_by_cell: Mapping[str, bool],
    quota_by_cell: Mapping[str, bool],
    correlation_domains_by_cell: Mapping[str, Iterable[str]] | None = None,
) -> tuple[SurfaceRuntimeState, ...]:
    """Translate existing Bubbles/SOVARA provider health into Formation state.

    Provider health never mints authority, privacy approval, freshness or quota.
    Those four gates must be supplied independently by the caller.  Quality and
    reliability remain neutral rather than being fabricated from liveness.
    """
    specs = {getattr(row, "cell_id"): row for row in getattr(projection, "specs", ())}
    health = {getattr(row, "cell_id"): row for row in getattr(projection, "health", ())}
    domains = dict(correlation_domains_by_cell or {})
    rows: list[SurfaceRuntimeState] = []

    for cell_id, surface_id in PROVIDER_CELL_TO_SURFACE_ID.items():
        spec = specs.get(cell_id)
        status = health.get(cell_id)
        if spec is None or status is None:
            continue
        semantic_ready = bool(getattr(status, "semantic_readback_ready", False))
        provider_native = bool(getattr(status, "provider_native", False))
        provider_live = bool(getattr(status, "provider_live", False))
        credential_bound = bool(getattr(status, "credential_bound", False))
        latency = getattr(status, "latency_ms", None)
        cost_microunits = getattr(status, "estimated_cost_microunits", None)
        proof_refs = tuple(getattr(status, "proof_refs", ()) or ())
        priority = float(getattr(spec, "priority", 50.0))

        rows.append(
            SurfaceRuntimeState(
                surface_id=surface_id,
                authority_pass=bool(authority_by_cell.get(cell_id, False)) and credential_bound,
                privacy_pass=bool(privacy_by_cell.get(cell_id, False)),
                currentness_pass=bool(currentness_by_cell.get(cell_id, False)),
                proof_pass=provider_native and semantic_ready,
                health_pass=provider_live,
                quota_pass=bool(quota_by_cell.get(cell_id, False)),
                circuit_open=not provider_live,
                quality=0.5,
                reliability=0.5,
                proof_strength=1.0 if (provider_native and semantic_ready) else 0.0,
                latency_ms=float(latency or 0.0),
                estimated_cost=float(cost_microunits or 0) / 1_000_000.0,
                owner_burden=0.0,
                privacy_cost=0.0,
                maintenance_cost=0.0,
                strategic_value=max(0.0, min(1.0, priority / 100.0)),
                correlation_domains=_clean(domains.get(cell_id, (getattr(spec, "provider", cell_id),))),
                proof_refs=_clean(proof_refs),
            ).validate()
        )
    return tuple(rows)


class FormationSurfaceLoadBalancer:
    """Compile minimum-sufficient cross-surface portfolios for FUSE work."""

    TRUTH_BOUNDARY = (
        "SURFACE_FORMATION_COMPILED!=SURFACE_AUTHORITY_GRANTED!=PROVIDER_EXECUTED"
        "!=SEMANTIC_READBACK!=EFFECT_VERIFIED!=OWNER_VALUE!=COMPLETE"
    )

    def __init__(
        self,
        registry: OmniSurfaceRegistry | None = None,
        formation_engine: FormationEngine | None = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.formation_engine = formation_engine or FormationEngine()

    @staticmethod
    def _gate_reasons(
        descriptor: SurfaceDescriptor,
        runtime: SurfaceRuntimeState | None,
        package: FormationWorkPackage,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if runtime is None:
            reasons.append("RUNTIME_STATE_UNAVAILABLE")
            return tuple(reasons)
        if not runtime.authority_pass:
            reasons.append("AUTHORITY_HOLD")
        if not runtime.privacy_pass:
            reasons.append("PRIVACY_HOLD")
        if not runtime.currentness_pass:
            reasons.append("CURRENTNESS_HOLD")
        if not runtime.proof_pass:
            reasons.append("PROOF_HOLD")
        if not runtime.health_pass:
            reasons.append("HEALTH_HOLD")
        if not runtime.quota_pass:
            reasons.append("QUOTA_HOLD")
        if runtime.circuit_open:
            reasons.append("CIRCUIT_OPEN")
        if _EFFECT_ORDER[descriptor.maximum_effect] < _EFFECT_ORDER[package.maximum_effect]:
            reasons.append("EFFECT_CEILING_TOO_LOW")
        if not (set(descriptor.capabilities) & set(package.capabilities)):
            reasons.append("NO_CAPABILITY_OVERLAP")
        return tuple(reasons)

    @staticmethod
    def _reversibility(descriptor: SurfaceDescriptor) -> float:
        effect = descriptor.maximum_effect
        if effect in {EffectClass.OBSERVE, EffectClass.INTERNAL}:
            return 1.0
        if effect == EffectClass.DRAFT:
            return 0.95
        if effect == EffectClass.REVERSIBLE_WRITE:
            return 0.8
        if effect == EffectClass.CONSEQUENTIAL:
            return 0.45
        return 0.0

    def _route(
        self,
        descriptor: SurfaceDescriptor,
        runtime: SurfaceRuntimeState,
        package: FormationWorkPackage,
    ) -> Route:
        speed = 1.0 / (1.0 + (runtime.latency_ms / 1000.0))
        preferred_bonus = 0.25 if descriptor.surface_id in package.preferred_surface_ids else 0.0
        return Route(
            route_id=descriptor.surface_id,
            route_type="FORMATION_SURFACE",
            feasibility=min(1.0, (runtime.quality + runtime.reliability) / 2.0),
            proof_strength=min(1.0, runtime.proof_strength),
            reversibility=self._reversibility(descriptor),
            speed=speed,
            strategic_value=runtime.strategic_value + preferred_bonus,
            owner_burden=runtime.owner_burden,
            privacy_cost=runtime.privacy_cost,
            maintenance_cost=runtime.maintenance_cost + runtime.estimated_cost,
        )

    def _eligible(
        self,
        package: FormationWorkPackage,
        runtime_by_id: Mapping[str, SurfaceRuntimeState],
    ) -> tuple[list[tuple[SurfaceDescriptor, SurfaceRuntimeState, float]], list[HeldSurface]]:
        eligible: list[tuple[SurfaceDescriptor, SurfaceRuntimeState, float]] = []
        held: list[HeldSurface] = []
        required = set(package.capabilities)
        for descriptor in self.registry.surfaces.values():
            if not (required & set(descriptor.capabilities)):
                continue
            runtime = runtime_by_id.get(descriptor.surface_id)
            reasons = self._gate_reasons(descriptor, runtime, package)
            if reasons:
                held.append(HeldSurface(package.package_id, descriptor.surface_id, reasons))
                continue
            assert runtime is not None
            route = self._route(descriptor, runtime, package)
            eligible.append((descriptor, runtime, self.formation_engine.score(route)))
        eligible.sort(key=lambda row: (row[2], row[0].surface_id), reverse=True)
        return eligible, held

    @staticmethod
    def _independent(
        selected: Sequence[tuple[SurfaceDescriptor, SurfaceRuntimeState, float]],
        candidate: tuple[SurfaceDescriptor, SurfaceRuntimeState, float],
    ) -> bool:
        descriptor, runtime, _ = candidate
        if any(existing[0].provider == descriptor.provider for existing in selected):
            return False
        candidate_domains = set(runtime.correlation_domains)
        for _, existing_runtime, _ in selected:
            if candidate_domains and candidate_domains & set(existing_runtime.correlation_domains):
                return False
        return True

    def _assign_package(
        self,
        package: FormationWorkPackage,
        runtime_by_id: Mapping[str, SurfaceRuntimeState],
        remaining_budget: float,
    ) -> tuple[PackageAssignment, tuple[HeldSurface, ...]]:
        package.validate()
        eligible, held = self._eligible(package, runtime_by_id)
        required = set(package.capabilities)

        if package.require_independent_candidates:
            full = [
                row for row in eligible
                if required.issubset(set(row[0].capabilities))
            ]
            selected: list[tuple[SurfaceDescriptor, SurfaceRuntimeState, float]] = []
            for row in full:
                if not selected or self._independent(selected, row):
                    projected = sum(item[1].estimated_cost for item in (*selected, row))
                    if projected <= remaining_budget:
                        selected.append(row)
                if len(selected) >= package.candidate_count:
                    break
            if len(selected) < package.candidate_count:
                reasons = ["INDEPENDENCE_OR_BUDGET_FLOOR_NOT_MET"]
                for row in full:
                    held.append(HeldSurface(package.package_id, row[0].surface_id, tuple(reasons)))
                return (
                    PackageAssignment(
                        package_id=package.package_id,
                        kind=package.kind.value,
                        selected_surface_ids=(),
                        covered_capabilities=(),
                        missing_capabilities=tuple(sorted(required)),
                        independent=False,
                        estimated_cost=0.0,
                        route_score=0.0,
                        proof_refs=(),
                    ),
                    tuple(held),
                )
            refs = _clean(ref for _, rt, _ in selected for ref in rt.proof_refs)
            return (
                PackageAssignment(
                    package_id=package.package_id,
                    kind=package.kind.value,
                    selected_surface_ids=tuple(row[0].surface_id for row in selected),
                    covered_capabilities=tuple(sorted(required)),
                    missing_capabilities=(),
                    independent=True,
                    estimated_cost=sum(row[1].estimated_cost for row in selected),
                    route_score=sum(row[2] for row in selected),
                    proof_refs=refs,
                ),
                tuple(held),
            )

        full = [row for row in eligible if required.issubset(set(row[0].capabilities))]
        if full:
            for row in full:
                if row[1].estimated_cost <= remaining_budget:
                    refs = _clean(row[1].proof_refs)
                    return (
                        PackageAssignment(
                            package_id=package.package_id,
                            kind=package.kind.value,
                            selected_surface_ids=(row[0].surface_id,),
                            covered_capabilities=tuple(sorted(required)),
                            missing_capabilities=(),
                            independent=True,
                            estimated_cost=row[1].estimated_cost,
                            route_score=row[2],
                            proof_refs=refs,
                        ),
                        tuple(held),
                    )

        if not package.allow_composition:
            return (
                PackageAssignment(
                    package_id=package.package_id,
                    kind=package.kind.value,
                    selected_surface_ids=(),
                    covered_capabilities=(),
                    missing_capabilities=tuple(sorted(required)),
                    independent=True,
                    estimated_cost=0.0,
                    route_score=0.0,
                    proof_refs=(),
                ),
                tuple(held),
            )

        uncovered = set(required)
        selected: list[tuple[SurfaceDescriptor, SurfaceRuntimeState, float]] = []
        cost = 0.0
        pool = list(eligible)
        while uncovered:
            candidates = [
                row for row in pool
                if set(row[0].capabilities) & uncovered
                and cost + row[1].estimated_cost <= remaining_budget
            ]
            if not candidates:
                break
            candidates.sort(
                key=lambda row: (
                    len(set(row[0].capabilities) & uncovered),
                    row[2],
                    -row[1].estimated_cost,
                    row[0].surface_id,
                ),
                reverse=True,
            )
            chosen = candidates[0]
            selected.append(chosen)
            cost += chosen[1].estimated_cost
            uncovered -= set(chosen[0].capabilities)
            pool = [row for row in pool if row[0].surface_id != chosen[0].surface_id]

        covered = required - uncovered
        refs = _clean(ref for _, rt, _ in selected for ref in rt.proof_refs)
        return (
            PackageAssignment(
                package_id=package.package_id,
                kind=package.kind.value,
                selected_surface_ids=tuple(row[0].surface_id for row in selected),
                covered_capabilities=tuple(sorted(covered)),
                missing_capabilities=tuple(sorted(uncovered)),
                independent=True,
                estimated_cost=cost,
                route_score=sum(row[2] for row in selected),
                proof_refs=refs,
            ),
            tuple(held),
        )

    @staticmethod
    def _waves(
        packages: Sequence[FormationWorkPackage],
        assignments: Sequence[PackageAssignment],
        max_parallel_surfaces: int,
    ) -> tuple[tuple[str, ...], ...]:
        if max_parallel_surfaces < 1:
            raise ValueError("FORMATION_MAX_PARALLEL_SURFACES_INVALID")
        package_by_id = {row.package_id: row for row in packages}
        waves: list[tuple[str, ...]] = []
        buffer: list[str] = []

        def flush() -> None:
            nonlocal buffer
            if buffer:
                waves.append(tuple(dict.fromkeys(buffer)))
                buffer = []

        for assignment in assignments:
            package = package_by_id[assignment.package_id]
            if not assignment.selected_surface_ids:
                continue
            if not package.parallelizable:
                flush()
                waves.append(tuple(dict.fromkeys(assignment.selected_surface_ids)))
                continue
            for surface_id in assignment.selected_surface_ids:
                if surface_id not in buffer:
                    buffer.append(surface_id)
                if len(buffer) >= max_parallel_surfaces:
                    flush()
        flush()
        return tuple(waves)

    def compile(
        self,
        *,
        mission_id: str,
        packages: Sequence[FormationWorkPackage],
        runtime_states: Sequence[SurfaceRuntimeState],
        max_parallel_surfaces: int = 4,
        total_cost_ceiling: float = float("inf"),
    ) -> SurfaceFormationPlan:
        if not mission_id.strip() or not packages:
            raise ValueError("FORMATION_MISSION_AND_PACKAGES_REQUIRED")
        if total_cost_ceiling < 0:
            raise ValueError("FORMATION_COST_CEILING_INVALID")

        runtime_rows = [row.validate() for row in runtime_states]
        runtime_ids = [row.surface_id for row in runtime_rows]
        if len(runtime_ids) != len(set(runtime_ids)):
            raise ValueError("FORMATION_DUPLICATE_RUNTIME_STATE")
        runtime_by_id = {row.surface_id: row for row in runtime_rows}

        assignments: list[PackageAssignment] = []
        held: list[HeldSurface] = []
        spent = 0.0
        for package in packages:
            remaining = max(0.0, total_cost_ceiling - spent)
            assignment, held_rows = self._assign_package(package, runtime_by_id, remaining)
            assignments.append(assignment)
            held.extend(held_rows)
            spent += assignment.estimated_cost

        waves = self._waves(packages, assignments, max_parallel_surfaces)
        selected = _clean(
            surface_id
            for assignment in assignments
            for surface_id in assignment.selected_surface_ids
        )
        missing_packages = tuple(
            assignment.package_id for assignment in assignments if not assignment.complete
        )
        core = {
            "schema": SCHEMA,
            "version": VERSION,
            "mission_id": mission_id.strip(),
            "assignments": [asdict(row) for row in assignments],
            "execution_waves": waves,
            "selected_surface_ids": selected,
            "missing_packages": missing_packages,
            "total_estimated_cost": round(spent, 9),
        }
        return SurfaceFormationPlan(
            schema=SCHEMA,
            version=VERSION,
            plan_id=f"FUSE-SURFACE-FORMATION-{_digest(core)[:24].upper()}",
            mission_id=mission_id.strip(),
            assignments=tuple(assignments),
            execution_waves=waves,
            selected_surface_ids=selected,
            held_surfaces=tuple(held),
            missing_packages=missing_packages,
            total_estimated_cost=round(spent, 9),
            external_effect_authorized=False,
            provider_execution_proven=False,
            authority_minted=False,
            truth_boundary=self.TRUTH_BOUNDARY,
        )


__all__ = [
    "SCHEMA",
    "VERSION",
    "EXTERNAL_EFFECTS",
    "AUTHORITY_MINTING",
    "PROVIDER_EXECUTION",
    "WorkKind",
    "SurfaceRuntimeState",
    "FormationWorkPackage",
    "PackageAssignment",
    "HeldSurface",
    "SurfaceFormationPlan",
    "FormationSurfaceLoadBalancer",
    "PROVIDER_CELL_TO_SURFACE_ID",
    "runtime_states_from_provider_projection",
]
