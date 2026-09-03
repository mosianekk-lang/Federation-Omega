from __future__ import annotations

"""Bubbles Ω Autonomic Federation Runtime v1.

A thin execution lifecycle over existing Federation owners:
- MissionIR: mission/effect/authority/proof/value contract
- DurableMissionRuntimeV1: event truth, checkpoints and result continuity
- ProviderAuthorityFabric: exact provider-grant resolution
- ProviderCellMesh: proof-adjusted provider selection and semantic readback
- MissionProofPassport: mission evidence projection on the existing ledger
- OwnerValueOptimizer: measured matched-cohort value decisions

This module is not a background ChatGPT daemon and creates no provider identity,
credential, IAM grant, billing authority, second scheduler, second memory root,
second proof plane, or replacement value court.
"""

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from federation.mission_ir import MissionIR
from federation.sentinel_omega.owner_value_ingress import OwnerValueMissionRecord
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import ProofEntry, ProofStatus, WorkItem, WorkStatus

from .mission_proof_passport import MissionProofPassport, PassportEventKind
from .owner_value_optimizer import OwnerValueOptimizer
from .provider_authority_fabric import (
    AuthorityGrant,
    AuthorityGrantSource,
    AuthorityLeaseDecision,
    AuthorityState,
    CapabilityAuthorityContract,
    ProviderAuthorityFabric,
)
from .provider_cell_mesh import (
    ProviderCellHealth,
    ProviderCellMesh,
    ProviderCellSpec,
    ProviderExecutionReceipt,
    ProviderSelection,
)


SCHEMA = "BUBBLES-OMEGA-AUTONOMIC-FEDERATION-RUNTIME-V1"
WORK_AUTHORITY = "AUTHORITY_PREFLIGHT"
WORK_EXECUTION = "PROVIDER_EXECUTION"
WORK_READBACK = "SEMANTIC_READBACK"
WORK_PROOF = "PROOF_FINALIZE"
WORK_VALUE = "OWNER_VALUE_MEASURE"


class BubblesAutonomicFederationRuntime:
    def __init__(
        self,
        root: str | Path,
        *,
        source_frontier: str,
        policy_sha256: str,
        environment_sha256: str,
        cells: Sequence[ProviderCellSpec],
        grant_source: AuthorityGrantSource | None = None,
        minimum_owner_value_pairs: int = 10,
    ) -> None:
        self.durable = DurableMissionRuntimeV1(
            root,
            source_frontier=source_frontier,
            policy_sha256=policy_sha256,
            environment_sha256=environment_sha256,
        )
        self.authority = ProviderAuthorityFabric(grant_source)
        self.mesh = ProviderCellMesh(cells)
        self.passport = MissionProofPassport(self.durable)
        self.value = OwnerValueOptimizer(minimum_pairs=minimum_owner_value_pairs)

    @staticmethod
    def _work_items() -> tuple[WorkItem, ...]:
        return (
            WorkItem.create(
                work_id=WORK_AUTHORITY,
                lane="authority",
                objective="Resolve exact mission-bound provider authority or preserve the gate.",
                status=WorkStatus.READY,
            ),
            WorkItem.create(
                work_id=WORK_EXECUTION,
                lane="provider",
                objective="Dispatch through the best currently proven provider cell.",
                dependencies=(WORK_AUTHORITY,),
                status=WorkStatus.PLANNED,
            ),
            WorkItem.create(
                work_id=WORK_READBACK,
                lane="readback",
                objective="Require provider-native semantic readback before effect/result promotion.",
                dependencies=(WORK_EXECUTION,),
                status=WorkStatus.PLANNED,
            ),
            WorkItem.create(
                work_id=WORK_PROOF,
                lane="proof",
                objective="Compile the mission proof passport without self-certification.",
                dependencies=(WORK_READBACK,),
                status=WorkStatus.PLANNED,
            ),
            WorkItem.create(
                work_id=WORK_VALUE,
                lane="value",
                objective="Evaluate only measured matched owner-value cohorts.",
                dependencies=(WORK_PROOF,),
                status=WorkStatus.PLANNED,
            ),
        )

    def compile(self, mission: MissionIR, *, trace_id: str) -> dict[str, Any]:
        mission = mission.normalized()
        mission.validate()
        self.durable.open(
            mission,
            required_proof_axes=(
                "source",
                "identity",
                "authorization",
                "execution",
                "semantic_proof",
                "independent_proof",
                "resilience",
                "rollback",
            ),
            trace_id=trace_id,
        )
        projection = self.durable.project(mission.mission_id)
        for item in self._work_items():
            if item.work_id not in projection.work_items:
                projection = self.durable.set_work_item(mission.mission_id, item)

        source_ref = mission.source_frontier
        self.passport.record(
            mission.mission_id,
            PassportEventKind.SOURCE,
            state="VERIFIED",
            proof_refs=(source_ref, f"mission-ir:{mission.digest()}"),
            data={"mission_ir_sha256": mission.digest(), "source_frontier": source_ref},
            idempotency_key=f"SOURCE:{mission.digest()}",
        )
        self.durable.bind_proof(
            mission.mission_id,
            ProofEntry.create(
                axis="source",
                status=ProofStatus.PROVEN,
                evidence_refs=(source_ref, f"mission-ir:{mission.digest()}"),
                claim_limit="Source/MissionIR binding only; no provider runtime or effect authority.",
            ),
        )
        return self.status(mission.mission_id)

    def resolve_authority(
        self,
        mission: MissionIR,
        contract: CapabilityAuthorityContract,
        *,
        now_epoch: float,
        grants: Sequence[AuthorityGrant] = (),
    ) -> AuthorityLeaseDecision:
        decision = self.authority.resolve(
            mission,
            contract,
            now_epoch=now_epoch,
            grants=grants,
        )
        self.passport.record(
            mission.mission_id,
            PassportEventKind.AUTHORITY,
            state=decision.state,
            proof_refs=decision.proof_refs,
            data={
                "capability_id": decision.capability_id,
                "provider": decision.provider,
                "connector": decision.connector,
                "action": decision.action,
                "grant_id": decision.grant_id,
                "provider_effect_authorized": decision.provider_effect_authorized,
                "reason": decision.reason,
            },
            idempotency_key=f"AUTH:{decision.contract_sha256}:{decision.state}:{decision.grant_id}",
        )
        if decision.state in {AuthorityState.RESOLVED.value, AuthorityState.NOT_REQUIRED.value}:
            refs = tuple(decision.proof_refs) or (f"authority:{decision.state}",)
            self.durable.update_work_status(
                mission.mission_id,
                WORK_AUTHORITY,
                WorkStatus.VERIFIED,
                result_refs=refs,
            )
            self.durable.update_work_status(
                mission.mission_id,
                WORK_EXECUTION,
                WorkStatus.READY,
            )
            self.durable.bind_proof(
                mission.mission_id,
                ProofEntry.create(
                    axis="authorization",
                    status=ProofStatus.PROVEN,
                    evidence_refs=refs,
                    claim_limit=(
                        "No effect authority required for this mission."
                        if decision.state == AuthorityState.NOT_REQUIRED.value
                        else "Exact mission-bound provider grant resolved; individual provider outcome still unproven."
                    ),
                ),
            )
        else:
            self.durable.update_work_status(
                mission.mission_id,
                WORK_AUTHORITY,
                WorkStatus.HELD,
                result_refs=(f"authority-gate:{decision.state}",),
            )
        return decision

    def select_provider(
        self,
        mission: MissionIR,
        capability_id: str,
        *,
        health: Sequence[ProviderCellHealth],
    ) -> ProviderSelection:
        return self.mesh.select(mission, capability_id, health=health)

    def execute_provider(
        self,
        mission: MissionIR,
        selection: ProviderSelection,
        *,
        authority: AuthorityLeaseDecision,
        payload: Mapping[str, Any],
        execute,
        readback,
    ) -> ProviderExecutionReceipt:
        if selection.state != "SELECTED":
            self.durable.update_work_status(
                mission.mission_id,
                WORK_EXECUTION,
                WorkStatus.HELD,
                result_refs=(f"provider-gate:{selection.reason}",),
            )
            return ProviderExecutionReceipt(
                schema="BUBBLES-OMEGA-PROVIDER-CELL-MESH-V1",
                mission_id=mission.mission_id,
                capability_id=selection.capability_id,
                cell_id="",
                provider="",
                state="PROVIDER_GATED",
                operation_id="",
                idempotency_key="",
                transport_ok=False,
                provider_native=False,
                semantic_readback_verified=False,
                effect_attempted=False,
                effect_class=mission.effect_class,
                provider_effect_authorized=False,
                reason=selection.reason,
            )

        receipt = self.mesh.dispatch(
            mission,
            selection,
            authority=authority,
            payload=payload,
            execute=execute,
            readback=readback,
        )
        self.passport.record(
            mission.mission_id,
            PassportEventKind.PROVIDER_DISPATCH,
            state=receipt.state,
            proof_refs=receipt.proof_refs,
            data={
                "cell_id": receipt.cell_id,
                "provider": receipt.provider,
                "operation_id": receipt.operation_id,
                "effect_attempted": receipt.effect_attempted,
                "cost_microunits": receipt.cost_microunits,
                "latency_ms": receipt.latency_ms,
                "provider_effect_authorized": receipt.provider_effect_authorized,
                "reason": receipt.reason,
            },
            idempotency_key=f"DISPATCH:{receipt.idempotency_key}:{receipt.state}",
        )

        if receipt.state == "PROVIDER_SEMANTIC_READBACK_VERIFIED":
            refs = tuple(receipt.proof_refs) + tuple(
                item for item in (receipt.result_ref, receipt.readback_ref, receipt.result_sha256) if item
            )
            self.durable.update_work_status(
                mission.mission_id,
                WORK_EXECUTION,
                WorkStatus.VERIFIED,
                result_refs=refs,
            )
            self.durable.update_work_status(
                mission.mission_id,
                WORK_READBACK,
                WorkStatus.VERIFIED,
                result_refs=refs,
            )
            self.durable.update_work_status(
                mission.mission_id,
                WORK_PROOF,
                WorkStatus.READY,
            )
            self.passport.record(
                mission.mission_id,
                PassportEventKind.SEMANTIC_READBACK,
                state="PROVIDER_SEMANTIC_READBACK_VERIFIED",
                proof_refs=refs,
                data={
                    "provider": receipt.provider,
                    "readback_ref": receipt.readback_ref,
                    "cost_microunits": receipt.cost_microunits,
                    "latency_ms": receipt.latency_ms,
                },
                idempotency_key=f"READBACK:{receipt.idempotency_key}:{receipt.readback_ref}",
            )
            for axis, claim in (
                ("execution", "Provider-native execution receipt bound to the mission."),
                ("semantic_proof", "Provider-native semantic readback verified."),
                ("independent_proof", "Readback route is distinct from source admission."),
            ):
                self.durable.bind_proof(
                    mission.mission_id,
                    ProofEntry.create(
                        axis=axis,
                        status=ProofStatus.PROVEN,
                        evidence_refs=refs,
                        claim_limit=claim,
                    ),
                )
        elif receipt.state in {"HOLD_READBACK", "READBACK_REQUIRED"}:
            self.durable.update_work_status(
                mission.mission_id,
                WORK_EXECUTION,
                WorkStatus.HELD,
                result_refs=(receipt.result_ref or receipt.state,),
            )
            self.durable.update_work_status(
                mission.mission_id,
                WORK_READBACK,
                WorkStatus.HELD,
                result_refs=(receipt.readback_ref or receipt.state,),
            )
        else:
            self.durable.update_work_status(
                mission.mission_id,
                WORK_EXECUTION,
                WorkStatus.HELD,
                result_refs=(receipt.state,),
            )
        return receipt

    def finalize_proof(self, mission_id: str) -> dict[str, Any]:
        before = self.passport.snapshot(mission_id)
        if not before.authority_resolved or not before.semantic_readback_verified or before.hold_readback:
            self.durable.update_work_status(
                mission_id,
                WORK_PROOF,
                WorkStatus.HELD,
                result_refs=("proof-gate:authority-or-semantic-readback",),
            )
            return before.to_dict()

        self.passport.record(
            mission_id,
            PassportEventKind.FINAL,
            state="VERIFIED",
            proof_refs=before.proof_refs,
            data={
                "authority_resolved": before.authority_resolved,
                "semantic_readback_verified": before.semantic_readback_verified,
                "external_effect_count": before.external_effect_count,
            },
            idempotency_key=f"FINAL:{before.ledger_head_hash}",
        )
        after = self.passport.snapshot(mission_id)
        self.durable.update_work_status(
            mission_id,
            WORK_PROOF,
            WorkStatus.VERIFIED,
            result_refs=(after.ledger_head_hash or "passport:verified",),
        )
        self.durable.update_work_status(
            mission_id,
            WORK_VALUE,
            WorkStatus.READY,
        )
        return after.to_dict()

    def evaluate_owner_value(
        self,
        mission_id: str,
        records: Sequence[OwnerValueMissionRecord],
    ) -> dict[str, Any]:
        decision = self.value.evaluate(records)
        self.passport.record(
            mission_id,
            PassportEventKind.VALUE,
            state=decision.state,
            proof_refs=decision.proof_refs,
            data={
                "measured_pair_count": decision.measured_pair_count,
                "score": decision.score,
                "champion": decision.champion,
                "owner_value_proven": decision.owner_value_proven,
            },
            idempotency_key=f"VALUE:{decision.state}:{decision.measured_pair_count}:{decision.score}",
        )
        if decision.state == "MEASURED_COHORT_EVALUATED":
            self.durable.update_work_status(
                mission_id,
                WORK_VALUE,
                WorkStatus.VERIFIED,
                result_refs=decision.proof_refs or ("owner-value:measured",),
            )
        else:
            self.durable.update_work_status(
                mission_id,
                WORK_VALUE,
                WorkStatus.HELD,
                result_refs=("owner-value:data-gated",),
            )
        return decision.to_dict()

    def status(self, mission_id: str) -> dict[str, Any]:
        projection = self.durable.project(mission_id)
        passport = self.passport.snapshot(mission_id)
        return {
            "schema": SCHEMA,
            "mission_id": mission_id,
            "mission_status": projection.status,
            "work_items": {
                work_id: {
                    "lane": item.lane,
                    "status": item.status.value,
                    "dependencies": list(item.dependencies),
                    "result_refs": list(item.result_refs),
                }
                for work_id, item in sorted(projection.work_items.items())
            },
            "passport": passport.to_dict(),
            "pending_requests": [asdict(item) for item in self.durable.pending_requests(mission_id)],
            "truth_boundary": {
                "source_runtime_is_provider_identity": False,
                "durable_runtime_is_hidden_background_chatgpt": False,
                "provider_selection_is_provider_authority": False,
                "proof_complete_is_owner_value": False,
                "external_effect_requires_exact_authority_and_semantic_readback": True,
                "second_scheduler_created": False,
                "second_memory_root_created": False,
            },
        }


__all__ = [
    "BubblesAutonomicFederationRuntime",
    "SCHEMA",
    "WORK_AUTHORITY",
    "WORK_EXECUTION",
    "WORK_PROOF",
    "WORK_READBACK",
    "WORK_VALUE",
]
