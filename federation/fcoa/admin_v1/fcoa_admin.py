from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping

from federation.capability_truth_v1 import (
    AdapterRouteDecision,
    CapabilityCurrentnessFabric,
    CapabilityRouteRequirement,
    CapabilitySurfaceState,
)


class Scope(str, Enum):
    FUSE_OWNED = "FUSE_OWNED"
    PROVIDER = "PROVIDER"
    EXTERNAL = "EXTERNAL"


class AdminAction(str, Enum):
    CENSUS = "CENSUS"
    READ = "READ"
    ROUTE = "ROUTE"
    COMPOSE = "COMPOSE"
    TEST = "TEST"
    REPAIR = "REPAIR"
    UPGRADE = "UPGRADE"
    CONFIGURE = "CONFIGURE"
    DEPLOY = "DEPLOY"
    ROLLBACK = "ROLLBACK"
    RECOVER = "RECOVER"
    RETIRE = "RETIRE"
    MODEL_ADMIN = "MODEL_ADMIN"
    RUNTIME_ADMIN = "RUNTIME_ADMIN"
    UPDATE_ADMIN = "UPDATE_ADMIN"
    WORKPLANE_ADMIN = "WORKPLANE_ADMIN"
    MISSION_ADMIN = "MISSION_ADMIN"
    JUDGE_ADMIN = "JUDGE_ADMIN"


CONSEQUENTIAL_EXTERNAL = {
    "EXTERNAL_MESSAGE", "EXTERNAL_PUBLISH", "SPEND",
    "IAM_CHANGE", "DESTRUCTIVE_PROVIDER", "ACCOUNT_CHANGE",
}


@dataclass(frozen=True)
class CapabilityRecord:
    capability_id: str
    executor_id: str
    scope: Scope
    effects: frozenset[str] = frozenset({"READ_ONLY"})
    healthy: bool = True
    current: bool = True
    requires_credentials: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MissionAuthority:
    mission_id: str
    allowed_effects: frozenset[str] = frozenset({"READ_ONLY"})
    provider_credentials_bound: frozenset[str] = frozenset()
    provider_authorities: frozenset[str] = frozenset()
    owner_directives: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LeaseState:
    resource: str
    active: bool
    owner: str = ""
    foreign: bool = False


@dataclass(frozen=True)
class AdminDecision:
    state: str
    reason: str
    capability_id: str = ""
    executor_id: str = ""
    action: str = ""


class FCOAAdminRegistry:
    """Dynamic registry: newly registered FUSE-owned capabilities are inherited automatically."""
    def __init__(self, records: Iterable[CapabilityRecord] = ()):
        self._records: dict[str, CapabilityRecord] = {r.capability_id: r for r in records}

    def register(self, record: CapabilityRecord) -> None:
        self._records[record.capability_id] = record

    def all(self) -> tuple[CapabilityRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda r: r.capability_id))

    def get(self, capability_id: str) -> CapabilityRecord | None:
        return self._records.get(capability_id)

    def fuse_owned(self) -> tuple[CapabilityRecord, ...]:
        return tuple(r for r in self.all() if r.scope == Scope.FUSE_OWNED)


@dataclass(frozen=True)
class FCOACurrentnessGateDecision:
    state: str
    capability_id: str
    surface_state: str
    selected_adapter: str = ""
    provider: str = ""
    reasons: tuple[str, ...] = ()

    @property
    def qualified(self) -> bool:
        return self.state == "QUALIFIED"




class FCOASuperAdmin:
    AGENT_ID = "FCOA-OMEGA"
    PROFILE_ID = "FCOA_INTERNAL_SUPER_ADMIN_V1"
    ROUTING_DOCTRINE = ("REUSE", "REBIND", "REPAIR", "EXTEND", "COMPOSE", "HARVEST", "BUILD_MINIMUM")

    def __init__(self, registry: FCOAAdminRegistry):
        self.registry = registry

    def census(self) -> dict:
        rows = self.registry.all()
        return {
            "agent_id": self.AGENT_ID,
            "profile_id": self.PROFILE_ID,
            "capabilities": len(rows),
            "fuse_owned": len([r for r in rows if r.scope == Scope.FUSE_OWNED]),
            "provider": len([r for r in rows if r.scope == Scope.PROVIDER]),
            "external": len([r for r in rows if r.scope == Scope.EXTERNAL]),
            "healthy_current": len([r for r in rows if r.healthy and r.current]),
        }

    def authorize(self, capability_id: str, action: AdminAction, mission: MissionAuthority, *,
                  requested_effect: str = "READ_ONLY", lease: LeaseState | None = None) -> AdminDecision:
        rec = self.registry.get(capability_id)
        if rec is None:
            return AdminDecision("HARVEST_OR_BUILD", "CAPABILITY_NOT_REGISTERED", capability_id, action=action.value)
        if not rec.current:
            return AdminDecision("REBIND_OR_REQUALIFY", "CAPABILITY_STALE", capability_id, rec.executor_id, action.value)
        if not rec.healthy:
            return AdminDecision("REPAIR_OR_FAILOVER", "EXECUTOR_UNHEALTHY", capability_id, rec.executor_id, action.value)
        if lease and lease.active and lease.foreign and lease.owner != self.AGENT_ID:
            return AdminDecision("JOIN_OR_WAIT", "ACTIVE_FOREIGN_FENCE", capability_id, rec.executor_id, action.value)

        if rec.scope == Scope.FUSE_OWNED:
            if requested_effect in CONSEQUENTIAL_EXTERNAL and requested_effect not in mission.allowed_effects:
                return AdminDecision("BLOCKED_EFFECT_GATE", "EXTERNAL_EFFECT_NOT_AUTHORIZED", capability_id, rec.executor_id, action.value)
            return AdminDecision("AUTHORIZED", "FUSE_INTERNAL_SUPER_ADMIN", capability_id, rec.executor_id, action.value)

        if requested_effect not in mission.allowed_effects:
            return AdminDecision("BLOCKED_EFFECT_GATE", "MISSION_EFFECT_NOT_AUTHORIZED", capability_id, rec.executor_id, action.value)
        if rec.requires_credentials and rec.executor_id not in mission.provider_credentials_bound:
            return AdminDecision("REBIND_REQUIRED", "REAL_PROVIDER_CREDENTIAL_REQUIRED", capability_id, rec.executor_id, action.value)
        if rec.executor_id not in mission.provider_authorities:
            return AdminDecision("AUTHORITY_REQUIRED", "REAL_PROVIDER_AUTHORITY_REQUIRED", capability_id, rec.executor_id, action.value)
        return AdminDecision("AUTHORIZED", "QUALIFIED_PROVIDER_AUTHORITY", capability_id, rec.executor_id, action.value)

    def next_route(self, failure_count_same_mechanism: int) -> str:
        return "CHANGED_MECHANISM_RECOMPILE" if failure_count_same_mechanism >= 2 else "AUTO_ROUTE"


    def currentness_gate(
        self,
        fabric: CapabilityCurrentnessFabric,
        requirement: CapabilityRouteRequirement,
        *,
        now: str,
        census_complete: bool = False,
    ) -> FCOACurrentnessGateDecision:
        requirement.validate()
        snapshot = fabric.snapshot(
            requirement.capability_id,
            now=now,
            requirement=requirement,
            census_complete=census_complete,
        )
        ranked = fabric.rank(requirement, now=now)
        selected = next((item for item in ranked if item.selected), None)
        if selected is not None:
            return FCOACurrentnessGateDecision(
                "QUALIFIED",
                requirement.capability_id,
                snapshot.state.value,
                selected.adapter_id,
                selected.provider,
                ("CURRENTNESS_AND_ROUTE_REQUIREMENTS_PROVEN",),
            )

        if snapshot.state is CapabilitySurfaceState.STALE_REQUALIFICATION_REQUIRED:
            reason = "CURRENTNESS_STALE_REQUALIFICATION_REQUIRED"
            state = "REBIND_OR_REQUALIFY"
        elif snapshot.state is CapabilitySurfaceState.ABSENT_AFTER_ESTATE_CENSUS:
            reason = "CAPABILITY_ABSENT_AFTER_ESTATE_CENSUS"
            state = "HARVEST_OR_BUILD"
        elif snapshot.state is CapabilitySurfaceState.UNKNOWN_NOT_ABSENT:
            reason = "CURRENTNESS_UNKNOWN_NOT_ABSENT"
            state = "CENSUS_REQUIRED"
        else:
            reason = "NO_QUALIFIED_FRESH_ADAPTER"
            state = "REBIND_OR_REQUALIFY"
        route_reasons = tuple(
            sorted({
                reason,
                *(
                    r
                    for item in ranked
                    for r in item.reasons
                ),
            })
        )
        return FCOACurrentnessGateDecision(
            state,
            requirement.capability_id,
            snapshot.state.value,
            reasons=route_reasons,
        )

    def authorize_with_currentness(
        self,
        capability_id: str,
        action: AdminAction,
        mission: MissionAuthority,
        *,
        fabric: CapabilityCurrentnessFabric,
        requirement: CapabilityRouteRequirement,
        now: str,
        requested_effect: str = "READ_ONLY",
        lease: LeaseState | None = None,
        census_complete: bool = False,
    ) -> tuple[AdminDecision, FCOACurrentnessGateDecision]:
        rec = self.registry.get(capability_id)
        if rec is None:
            gate = self.currentness_gate(
                fabric,
                requirement,
                now=now,
                census_complete=census_complete,
            )
            return (
                AdminDecision(
                    "HARVEST_OR_BUILD",
                    "CAPABILITY_NOT_REGISTERED",
                    capability_id,
                    action=action.value,
                ),
                gate,
            )

        # FUSE-owned internal administration retains its existing authority path.
        # Provider/external routing must additionally pass fresh Capability Truth.
        if rec.scope is Scope.FUSE_OWNED:
            admin = self.authorize(
                capability_id,
                action,
                mission,
                requested_effect=requested_effect,
                lease=lease,
            )
            gate = self.currentness_gate(
                fabric,
                requirement,
                now=now,
                census_complete=census_complete,
            )
            return admin, gate

        gate = self.currentness_gate(
            fabric,
            requirement,
            now=now,
            census_complete=census_complete,
        )
        if not gate.qualified:
            return (
                AdminDecision(
                    gate.state,
                    ";".join(gate.reasons) or "CURRENTNESS_GATE_FAILED",
                    capability_id,
                    rec.executor_id,
                    action.value,
                ),
                gate,
            )

        admin = self.authorize(
            capability_id,
            action,
            mission,
            requested_effect=requested_effect,
            lease=lease,
        )
        return admin, gate
