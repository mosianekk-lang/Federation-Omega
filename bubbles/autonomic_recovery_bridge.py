from __future__ import annotations

"""Bridge Sentinel Ω recovery decisions into the Bubbles Ω mission/provider fabric.

The bridge plans recovery but never bypasses Bubbles provider authority or
semantic readback. Internal A0/A1 repairs can become READY_INTERNAL. Reversible
A2 provider repairs stop at PROVIDER_AUTHORITY_PREFLIGHT_REQUIRED after a live
provider cell is selected. A3 remains owner-reserved.
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Sequence

from federation.mission_ir import MissionIR
from federation.sentinel_omega.autonomic_immune_system import (
    AuthorityTier,
    AutonomicImmuneController,
    FailureFingerprint,
    RemediationDisposition,
    RepairAttempt,
)

from .mission_telemetry import MissionTelemetryBridge, MissionTraceReceipt
from .provider_cell_mesh import ProviderCellMesh, ProviderSelection
from .provider_cell_registry import RegistryProjection


SCHEMA = "BUBBLES-OMEGA-AUTONOMIC-RECOVERY-BRIDGE-V1"


@dataclass(frozen=True, slots=True)
class RecoveryProviderBinding:
    runbook_id: str
    capability_id: str


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    schema: str
    mission_id: str
    fingerprint_digest: str
    state: str
    disposition: str
    reason: str
    runbook_id: str
    authority_tier: str
    capability_id: str = ""
    selected_cell_id: str = ""
    selected_provider: str = ""
    selected_connector: str = ""
    affected_nodes: tuple[str, ...] = ()
    proof_requirements: tuple[str, ...] = ()
    owner_interrupt_required: bool = False
    telemetry: MissionTraceReceipt | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.telemetry is not None:
            payload["telemetry"] = self.telemetry.to_dict()
        return payload


class AutonomicRecoveryBridge:
    def __init__(
        self,
        controller: AutonomicImmuneController,
        *,
        provider_bindings: Sequence[RecoveryProviderBinding] = (),
        telemetry: MissionTelemetryBridge | None = None,
    ) -> None:
        self.controller = controller
        self.provider_bindings = {item.runbook_id: item for item in provider_bindings}
        self.telemetry = telemetry or MissionTelemetryBridge()

    def _trace(
        self,
        mission: MissionIR,
        fingerprint: FailureFingerprint,
        *,
        state: str,
        disposition: str,
        runbook_id: str,
    ) -> MissionTraceReceipt:
        envelope = self.telemetry.envelope(
            mission_id=mission.mission_id,
            step="autonomic recovery decision",
            kind="recovery",
            status=state,
            attributes={
                "bubbles.recovery.disposition": disposition,
                "bubbles.recovery.runbook_id": runbook_id,
                "bubbles.failure.fingerprint": fingerprint.digest(),
                "bubbles.failure.target": fingerprint.target,
                "bubbles.failure.class": fingerprint.failure_class,
            },
        )
        return self.telemetry.local_receipt(
            mission.mission_id,
            envelope,
            proof_refs=(f"failure-fingerprint:{fingerprint.digest()}",),
        )

    def plan(
        self,
        mission: MissionIR,
        fingerprint: FailureFingerprint,
        *,
        authority_ceiling: AuthorityTier,
        state_epoch: str,
        registry: RegistryProjection,
        safe_alternate_routes: Sequence[str] = (),
    ) -> RecoveryPlan:
        mission = mission.normalized()
        mission.validate()
        decision = self.controller.decide(
            fingerprint,
            authority_ceiling=authority_ceiling,
            state_epoch=state_epoch,
            safe_alternate_routes=safe_alternate_routes,
        )

        state = "HOLD_PROVIDER_EDGE"
        capability_id = ""
        selection = ProviderSelection(
            schema="BUBBLES-OMEGA-PROVIDER-CELL-MESH-V1",
            mission_id=mission.mission_id,
            capability_id="",
            state="PROVIDER_GATED",
            reason="RECOVERY_PROVIDER_SELECTION_NOT_REQUIRED_OR_NOT_RESOLVED",
        )

        if decision.disposition == RemediationDisposition.ESCALATE_OWNER:
            state = "OWNER_ACTION_REQUIRED"
        elif decision.disposition == RemediationDisposition.REROUTE:
            state = "READY_REROUTE"
        elif decision.disposition == RemediationDisposition.HOLD_PROVIDER_EDGE:
            state = "HOLD_PROVIDER_EDGE"
        elif decision.disposition == RemediationDisposition.OBSERVE:
            state = "OBSERVE_ONLY"
        elif decision.disposition == RemediationDisposition.AUTO_REPAIR:
            if decision.authority in {AuthorityTier.A0_OBSERVE, AuthorityTier.A1_INTERNAL}:
                state = "READY_INTERNAL"
            elif decision.authority == AuthorityTier.A3_OWNER_RESERVED:
                state = "OWNER_ACTION_REQUIRED"
            else:
                binding = self.provider_bindings.get(decision.runbook_id)
                if binding is None:
                    state = "HOLD_PROVIDER_EDGE"
                else:
                    capability_id = binding.capability_id
                    mesh = ProviderCellMesh(registry.specs)
                    selection = mesh.select(mission, capability_id, health=registry.health)
                    state = (
                        "PROVIDER_AUTHORITY_PREFLIGHT_REQUIRED"
                        if selection.state == "SELECTED"
                        else "HOLD_PROVIDER_EDGE"
                    )

        telemetry = self._trace(
            mission,
            fingerprint,
            state=state,
            disposition=decision.disposition.value,
            runbook_id=decision.runbook_id,
        )
        return RecoveryPlan(
            schema=SCHEMA,
            mission_id=mission.mission_id,
            fingerprint_digest=fingerprint.digest(),
            state=state,
            disposition=decision.disposition.value,
            reason=(selection.reason if capability_id and selection.state != "SELECTED" else decision.reason),
            runbook_id=decision.runbook_id,
            authority_tier=decision.authority.value,
            capability_id=capability_id,
            selected_cell_id=selection.cell_id,
            selected_provider=selection.provider,
            selected_connector=selection.connector,
            affected_nodes=decision.affected_nodes,
            proof_requirements=decision.proof_requirements,
            owner_interrupt_required=decision.owner_interrupt_required,
            telemetry=telemetry,
        )

    def record_attempt(
        self,
        plan: RecoveryPlan,
        *,
        route_family: str,
        result: str,
        attempted_at: datetime,
        state_epoch: str,
        proof_refs: Sequence[str] = (),
    ) -> RepairAttempt:
        if not plan.runbook_id:
            raise ValueError("RECOVERY_ATTEMPT_REQUIRES_RUNBOOK")
        attempt = RepairAttempt(
            fingerprint_digest=plan.fingerprint_digest,
            runbook_id=plan.runbook_id,
            route_family=str(route_family),
            attempted_at=attempted_at,
            result=str(result),
            proof_refs=tuple(sorted({str(x) for x in proof_refs if str(x)})),
            state_epoch=str(state_epoch),
        )
        self.controller.record_attempt(attempt)
        return attempt


def default_recovery_bridge() -> AutonomicRecoveryBridge:
    """Return a conservative built-in recovery policy for common Federation faults.

    The defaults automate only observation/internal and reversible-provider
    planning. They do not grant provider authority. Billing, production cutover,
    publication and other owner-reserved classes remain A3.
    """

    from federation.sentinel_omega.autonomic_immune_system import DependencyGraph, RepairRunbook

    runbooks = (
        RepairRunbook(
            runbook_id="RB-INTERNAL-STATE-RECONCILE",
            failure_classes=("SOURCE_DRIFT", "STATE_DRIFT", "STALE_PROJECTION", "CACHE_DRIFT"),
            max_authority=AuthorityTier.A1_INTERNAL,
            reversible=True,
            requires_canary=True,
            requires_semantic_readback=True,
            rollback_ref="rollback:internal-state",
            route_family="internal-state-reconcile",
            expected_owner_burden_minutes=0.0,
        ),
        RepairRunbook(
            runbook_id="RB-GOOGLE-CLOUD-REVERSIBLE",
            failure_classes=("GOOGLE_WIF_DRIFT", "GOOGLE_IAM_REVERSIBLE", "GOOGLE_RUNTIME_DRIFT"),
            max_authority=AuthorityTier.A2_REVERSIBLE_PROVIDER,
            reversible=True,
            requires_canary=True,
            requires_semantic_readback=True,
            rollback_ref="rollback:google-cloud",
            route_family="google-cloud-reversible",
            expected_owner_burden_minutes=0.0,
        ),
        RepairRunbook(
            runbook_id="RB-APPS-SCRIPT-REVERSIBLE",
            failure_classes=("APPS_SCRIPT_DRIFT", "APPS_SCRIPT_BINDING_DRIFT"),
            max_authority=AuthorityTier.A2_REVERSIBLE_PROVIDER,
            reversible=True,
            requires_canary=True,
            requires_semantic_readback=True,
            rollback_ref="rollback:apps-script",
            route_family="apps-script-reversible",
            expected_owner_burden_minutes=0.0,
        ),
        RepairRunbook(
            runbook_id="RB-OWNER-RESERVED",
            failure_classes=("PROVIDER_BILLING", "PRODUCTION_CUTOVER", "PUBLICATION", "DESTRUCTIVE_CHANGE"),
            max_authority=AuthorityTier.A3_OWNER_RESERVED,
            reversible=False,
            requires_canary=True,
            requires_semantic_readback=True,
            route_family="owner-reserved",
            expected_owner_burden_minutes=1.0,
        ),
    )
    controller = AutonomicImmuneController(
        runbooks=runbooks,
        dependency_graph=DependencyGraph(
            {
                "provider-route": ("mission-runtime", "proof-passport"),
                "mission-runtime": ("owner-value",),
            }
        ),
    )
    return AutonomicRecoveryBridge(
        controller,
        provider_bindings=(
            RecoveryProviderBinding("RB-GOOGLE-CLOUD-REVERSIBLE", "GOOGLE_CLOUD_EFFECTS"),
            RecoveryProviderBinding("RB-APPS-SCRIPT-REVERSIBLE", "APPS_SCRIPT_EFFECTS"),
        ),
    )


__all__ = [
    "AutonomicRecoveryBridge",
    "RecoveryPlan",
    "RecoveryProviderBinding",
    "default_recovery_bridge",
]
