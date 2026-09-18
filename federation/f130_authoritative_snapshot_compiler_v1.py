from __future__ import annotations

"""Authoritative F130 snapshot compiler for FRCB v7.

The compiler projects current durable Federation mission truth into the existing
F130 MissionRuntimeSnapshot. Caller-supplied terminal booleans, tasks and proof
bindings are not accepted as evidence inputs.

This module creates no scheduler, proof root, mission truth store, provider
runtime, or terminal authority. F130 remains the terminal authority.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping

from bubbles.mission_proof_passport import MissionProofPassport, PassportSnapshot
from federation.fuse_mission_runtime_interlock_v1 import (
    MissionRuntimeInterlock,
    MissionRuntimeSnapshot,
    ProofBinding,
    RuntimeTask,
    RuntimeTaskState,
    TerminalPrepareReceipt,
)
from federation.runtime_convergence_binding_v6 import RuntimeConvergenceReceiptV6
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import (
    MissionProjection,
    ProofStatus,
    WorkStatus,
)

SCHEMA = "FUSE-F130-AUTHORITATIVE-SNAPSHOT-COMPILER-V1"
VERSION = "1.0.0"
COMPILER_ID = "FRCB-V7-DURABLE-MISSION-SNAPSHOT-COMPILER"
PREPARE_SCHEMA = "FUSE-F130-AUTHORITATIVE-PREPARE-V1"


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=lambda item: item.value if hasattr(item, "value") else str(item),
    )


def _digest(value: Any) -> str:
    return "sha256:" + sha256(_stable(value).encode("utf-8")).hexdigest()


def _projection_material(projection: MissionProjection) -> Mapping[str, object]:
    return {
        "mission": asdict(projection.mission),
        "status": projection.status,
        "work_items": {
            work_id: {
                "lane": item.lane,
                "objective": item.objective,
                "dependencies": list(item.dependencies),
                "shared_state_key": item.shared_state_key,
                "status": item.status.value,
                "result_refs": list(item.result_refs),
            }
            for work_id, item in sorted(projection.work_items.items())
        },
        "proof_vector": {
            axis: {
                "status": entry.status.value,
                "evidence_refs": list(entry.evidence_refs),
                "claim_limit": entry.claim_limit,
                "observed_at": entry.observed_at,
            }
            for axis, entry in sorted(projection.proof_vector.items())
        },
        "success_evidence": {
            criterion: list(refs)
            for criterion, refs in sorted(projection.success_evidence.items())
        },
        "resolvers": {
            resolver_id: {
                "status": resolver.status.value,
                "occurrence_count": resolver.occurrence_count,
                "evidence_refs": list(resolver.evidence_refs),
            }
            for resolver_id, resolver in sorted(projection.resolvers.items())
        },
        "closure_lock": asdict(projection.closure_lock),
        "source_decisions": list(projection.source_decisions),
        "last_event_hash": projection.last_event_hash,
    }


def _passport_material(passport: PassportSnapshot) -> Mapping[str, object]:
    return {
        "schema": passport.schema,
        "mission_id": passport.mission_id,
        "event_count": passport.event_count,
        "event_refs": list(passport.event_refs),
        "proof_refs": list(passport.proof_refs),
        "authority_resolved": passport.authority_resolved,
        "semantic_readback_verified": passport.semantic_readback_verified,
        "final_verified": passport.final_verified,
        "proof_complete": passport.proof_complete,
        "hold_readback": passport.hold_readback,
        "total_cost_microunits": passport.total_cost_microunits,
        "total_latency_ms": passport.total_latency_ms,
        "external_effect_count": passport.external_effect_count,
        "ledger_verified": passport.ledger_verified,
        "ledger_head_hash": passport.ledger_head_hash,
        "provider_effect_authorized": passport.provider_effect_authorized,
        "owner_value_proven": passport.owner_value_proven,
        "secret_value_recorded": passport.secret_value_recorded,
    }


def _proof_id(kind: str, task_id: str, evidence: object) -> str:
    return f"V7-{kind}-" + _digest(
        {"task_id": task_id, "evidence": evidence}
    ).split(":", 1)[1][:32].upper()


def _effectful(projection: MissionProjection) -> bool:
    for constraint in projection.mission.constraints:
        if constraint in {
            "MISSION_IR_EFFECT_CLASS:BOUNDED_EFFECT",
            "MISSION_IR_EFFECT_CLASS:CONSEQUENTIAL_EFFECT",
        }:
            return True
    return False


@dataclass(frozen=True, slots=True)
class AuthoritativeSnapshotReceipt:
    schema: str
    version: str
    compiler_id: str
    mission_id: str
    source_frontier: str
    policy_sha256: str
    environment_sha256: str
    contract_epoch: int
    ledger_tail: int
    ledger_head_hash: str
    mission_event_count: int
    projection_sha256: str
    proof_state_sha256: str
    passport_sha256: str
    v6_receipt_digest: str
    epoch_id: str
    task_ids: tuple[str, ...]
    proof_ids: tuple[str, ...]
    pending_request_ids: tuple[str, ...]
    closure_gaps: tuple[str, ...]
    compiler_gaps: tuple[str, ...]
    objective_satisfied: bool
    receipt_digest: str
    truth_boundary: Mapping[str, bool]

    def deterministic_payload(self) -> Mapping[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "compiler_id": self.compiler_id,
            "mission_id": self.mission_id,
            "source_frontier": self.source_frontier,
            "policy_sha256": self.policy_sha256,
            "environment_sha256": self.environment_sha256,
            "contract_epoch": self.contract_epoch,
            "ledger_tail": self.ledger_tail,
            "ledger_head_hash": self.ledger_head_hash,
            "mission_event_count": self.mission_event_count,
            "projection_sha256": self.projection_sha256,
            "proof_state_sha256": self.proof_state_sha256,
            "passport_sha256": self.passport_sha256,
            "v6_receipt_digest": self.v6_receipt_digest,
            "epoch_id": self.epoch_id,
            "task_ids": list(self.task_ids),
            "proof_ids": list(self.proof_ids),
            "pending_request_ids": list(self.pending_request_ids),
            "closure_gaps": list(self.closure_gaps),
            "compiler_gaps": list(self.compiler_gaps),
            "objective_satisfied": self.objective_satisfied,
            "truth_boundary": dict(self.truth_boundary),
        }

    def verify(self) -> bool:
        boundary = dict(self.truth_boundary)
        return bool(
            self.schema == SCHEMA
            and self.version == VERSION
            and self.compiler_id == COMPILER_ID
            and self.mission_id.strip()
            and self.source_frontier.strip()
            and self.policy_sha256.strip()
            and self.environment_sha256.strip()
            and self.contract_epoch >= 1
            and self.ledger_tail >= self.mission_event_count >= 1
            and self.ledger_head_hash.strip()
            and self.projection_sha256.startswith("sha256:")
            and self.proof_state_sha256.startswith("sha256:")
            and self.passport_sha256.startswith("sha256:")
            and self.v6_receipt_digest.startswith("sha256:")
            and self.epoch_id.startswith("mission-epoch:")
            and boundary.get("snapshot_compiled_from_durable_state") is True
            and boundary.get("caller_terminal_booleans_accepted") is False
            and boundary.get("durable_ledger_verified") is True
            and boundary.get("passport_ledger_head_matched") is True
            and boundary.get("v6_provider_execution_readback_verified") is True
            and boundary.get("required_done_tasks_require_proof") is True
            and boundary.get("f130_remains_terminal_authority") is True
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


@dataclass(frozen=True, slots=True)
class AuthoritativeSnapshotCompilation:
    snapshot: MissionRuntimeSnapshot
    receipt: AuthoritativeSnapshotReceipt
    passport: PassportSnapshot


@dataclass(frozen=True, slots=True)
class AuthoritativeTerminalPrepare:
    schema: str
    version: str
    mission_id: str
    compiler_receipt_digest: str
    ledger_head_hash: str
    projection_sha256: str
    epoch_id: str
    f130_prepare: TerminalPrepareReceipt
    receipt_digest: str

    def deterministic_payload(self) -> Mapping[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "mission_id": self.mission_id,
            "compiler_receipt_digest": self.compiler_receipt_digest,
            "ledger_head_hash": self.ledger_head_hash,
            "projection_sha256": self.projection_sha256,
            "epoch_id": self.epoch_id,
            "f130_prepare": asdict(self.f130_prepare),
        }

    def verify(self) -> bool:
        return bool(
            self.schema == PREPARE_SCHEMA
            and self.version == VERSION
            and self.mission_id.strip()
            and self.compiler_receipt_digest.startswith("sha256:")
            and self.ledger_head_hash.strip()
            and self.projection_sha256.startswith("sha256:")
            and self.epoch_id.startswith("mission-epoch:")
            and self.f130_prepare.mission_id == self.mission_id
            and self.receipt_digest == _digest(self.deterministic_payload())
        )


class F130AuthoritativeSnapshotCompiler:
    """Compile current durable mission evidence into the existing F130 contract."""

    def compile(
        self,
        *,
        runtime: DurableMissionRuntimeV1,
        passport: MissionProofPassport,
        mission_id: str,
        v6_receipt: RuntimeConvergenceReceiptV6,
        completion_claim_requested: bool = True,
    ) -> AuthoritativeSnapshotCompilation:
        mission_id = str(mission_id).strip()
        if not mission_id:
            raise ValueError("F130_AUTHORITATIVE_MISSION_ID_REQUIRED")
        if not v6_receipt.verify():
            raise ValueError("F130_AUTHORITATIVE_V6_RECEIPT_INVALID")
        if v6_receipt.mission_id != mission_id:
            raise ValueError("F130_AUTHORITATIVE_V6_MISSION_MISMATCH")
        if (
            not v6_receipt.provider_execution_verified
            or not v6_receipt.provider_semantic_readback_verified
        ):
            raise ValueError("F130_AUTHORITATIVE_V6_PROVIDER_PROOF_REQUIRED")

        ledger_state = runtime.ledger.verify()
        if ledger_state.get("state") != "VERIFIED":
            raise ValueError("F130_AUTHORITATIVE_LEDGER_NOT_VERIFIED")
        ledger_head = str(ledger_state.get("head_hash") or "").strip()
        if not ledger_head:
            raise ValueError("F130_AUTHORITATIVE_LEDGER_HEAD_REQUIRED")

        projection = runtime.project(mission_id)
        mission_events = runtime.ledger.events(mission_id)
        all_events = runtime.ledger.events()
        if not mission_events:
            raise ValueError("F130_AUTHORITATIVE_MISSION_EVENTS_REQUIRED")

        passport_snapshot = passport.snapshot(mission_id)
        if not passport_snapshot.ledger_verified:
            raise ValueError("F130_AUTHORITATIVE_PASSPORT_LEDGER_NOT_VERIFIED")
        if passport_snapshot.ledger_head_hash != ledger_head:
            raise ValueError("F130_AUTHORITATIVE_PASSPORT_LEDGER_HEAD_MISMATCH")

        projection_material = _projection_material(projection)
        projection_sha = _digest(projection_material)
        proof_state_sha = _digest(projection_material["proof_vector"])
        passport_sha = _digest(_passport_material(passport_snapshot))
        mission_event_count = len(mission_events)
        ledger_tail = len(all_events)
        contract_epoch = mission_event_count
        epoch_id = (
            "mission-epoch:"
            + _digest({
                "mission_id": mission_id,
                "ledger_head": ledger_head,
                "mission_event_count": mission_event_count,
                "ledger_tail": ledger_tail,
                "projection_sha": projection_sha,
                "v6_receipt_digest": v6_receipt.receipt_digest,
            }).split(":", 1)[1]
        )

        ready_ids = {item.work_id for item in projection.ready_work_wave()}
        effect_possible = _effectful(projection)
        compiler_gaps: list[str] = []
        tasks: list[RuntimeTask] = []
        proofs: list[ProofBinding] = []

        for work_id, item in sorted(projection.work_items.items()):
            required = item.status not in {WorkStatus.SUPERSEDED, WorkStatus.CANCELLED}
            proof_ids: tuple[str, ...] = ()

            if item.status is WorkStatus.VERIFIED:
                refs = tuple(str(ref).strip() for ref in item.result_refs if str(ref).strip())
                if not refs:
                    state = RuntimeTaskState.BLOCKED
                    compiler_gaps.append(f"WORK_RESULT_PROOF:{work_id}")
                else:
                    proof_id = _proof_id("WORK", work_id, refs)
                    proofs.append(
                        ProofBinding(
                            proof_id=proof_id,
                            task_id=work_id,
                            dependency=f"DURABLE_WORK_RESULT:{work_id}",
                            bound_epoch=epoch_id,
                            current_epoch=epoch_id,
                            fresh=True,
                        )
                    )
                    proof_ids = (proof_id,)
                    state = RuntimeTaskState.DONE
            elif item.status in {WorkStatus.SUPERSEDED, WorkStatus.CANCELLED}:
                state = RuntimeTaskState.DONE
                required = False
            elif item.status is WorkStatus.RUNNING:
                state = RuntimeTaskState.RUNNING
            elif item.status is WorkStatus.READY or work_id in ready_ids:
                state = RuntimeTaskState.READY
            else:
                state = RuntimeTaskState.BLOCKED

            tasks.append(
                RuntimeTask(
                    task_id=work_id,
                    state=state,
                    required=required,
                    dependencies=tuple(item.dependencies),
                    safe=state is RuntimeTaskState.READY,
                    authorized=state is RuntimeTaskState.READY,
                    available=state is RuntimeTaskState.READY,
                    owner_only=False,
                    priority=0,
                    effect_possible=effect_possible and state is RuntimeTaskState.RUNNING,
                    required_proof_ids=proof_ids,
                )
            )

        pending_requests = runtime.pending_requests(mission_id)
        for request in pending_requests:
            task_id = f"PENDING_REQUEST::{request.request_id}"
            tasks.append(
                RuntimeTask(
                    task_id=task_id,
                    state=RuntimeTaskState.BLOCKED,
                    required=True,
                    safe=False,
                    authorized=False,
                    available=False,
                    owner_only=False,
                    required_proof_ids=(),
                )
            )
            compiler_gaps.append(f"PENDING_REQUEST:{request.request_id}")

        def add_synthetic_done(task_id: str, dependency: str, evidence: object) -> None:
            proof_id = _proof_id("SYNTH", task_id, evidence)
            proofs.append(
                ProofBinding(
                    proof_id=proof_id,
                    task_id=task_id,
                    dependency=dependency,
                    bound_epoch=epoch_id,
                    current_epoch=epoch_id,
                    fresh=True,
                )
            )
            tasks.append(
                RuntimeTask(
                    task_id=task_id,
                    state=RuntimeTaskState.DONE,
                    required=True,
                    required_proof_ids=(proof_id,),
                )
            )

        add_synthetic_done(
            "MISSION_LEDGER_INTEGRITY",
            "DURABLE_LEDGER_HEAD",
            {"head": ledger_head, "events": ledger_tail},
        )
        add_synthetic_done(
            "FRCB_V6_CONVERGENCE",
            "FRCB_V6_RECEIPT",
            v6_receipt.receipt_digest,
        )

        closure_gaps = tuple(projection.closure_gaps())
        if projection.closable and not compiler_gaps:
            add_synthetic_done(
                "MISSION_PROJECTION_CLOSURE",
                "DURABLE_PROJECTION",
                {"projection_sha": projection_sha, "ledger_head": ledger_head},
            )
        else:
            tasks.append(
                RuntimeTask(
                    task_id="MISSION_PROJECTION_CLOSURE",
                    state=RuntimeTaskState.BLOCKED,
                    required=True,
                )
            )
            if closure_gaps:
                compiler_gaps.extend(f"CLOSURE:{gap}" for gap in closure_gaps)

        passport_ready = bool(
            passport_snapshot.proof_complete
            and passport_snapshot.semantic_readback_verified
            and passport_snapshot.final_verified
            and not passport_snapshot.hold_readback
        )
        if passport_ready:
            add_synthetic_done(
                "MISSION_PROOF_PASSPORT",
                "MISSION_PROOF_PASSPORT",
                {
                    "passport_sha": passport_sha,
                    "ledger_head": passport_snapshot.ledger_head_hash,
                    "proof_refs": passport_snapshot.proof_refs,
                },
            )
        else:
            tasks.append(
                RuntimeTask(
                    task_id="MISSION_PROOF_PASSPORT",
                    state=RuntimeTaskState.BLOCKED,
                    required=True,
                )
            )
            compiler_gaps.append("MISSION_PROOF_PASSPORT_NOT_COMPLETE")

        # Every required DONE task emitted by this compiler must have proof.
        for task in tasks:
            if (
                task.required
                and task.state is RuntimeTaskState.DONE
                and not task.required_proof_ids
            ):
                raise ValueError(
                    f"F130_AUTHORITATIVE_REQUIRED_DONE_TASK_WITHOUT_PROOF:{task.task_id}"
                )

        objective_satisfied = bool(
            projection.closable
            and not compiler_gaps
            and passport_ready
            and not pending_requests
            and v6_receipt.provider_execution_verified
            and v6_receipt.provider_semantic_readback_verified
        )

        snapshot = MissionRuntimeSnapshot(
            mission_id=mission_id,
            current_mission_id=mission_id,
            objective=projection.mission.objective,
            contract_epoch=contract_epoch,
            ledger_tail=ledger_tail,
            tasks=tuple(tasks),
            proofs=tuple(proofs),
            objective_satisfied=objective_satisfied,
            completion_claim_requested=bool(completion_claim_requested),
        )

        truth_boundary = MappingProxyType({
            "snapshot_compiled_from_durable_state": True,
            "caller_terminal_booleans_accepted": False,
            "durable_ledger_verified": True,
            "passport_ledger_head_matched": True,
            "v6_provider_execution_readback_verified": True,
            "required_done_tasks_require_proof": True,
            "pending_requests_block_terminality": True,
            "projection_closure_required": True,
            "passport_proof_complete_required": True,
            "f130_remains_terminal_authority": True,
        })
        material = {
            "schema": SCHEMA,
            "version": VERSION,
            "compiler_id": COMPILER_ID,
            "mission_id": mission_id,
            "source_frontier": runtime.source_frontier,
            "policy_sha256": runtime.policy_sha256,
            "environment_sha256": runtime.environment_sha256,
            "contract_epoch": contract_epoch,
            "ledger_tail": ledger_tail,
            "ledger_head_hash": ledger_head,
            "mission_event_count": mission_event_count,
            "projection_sha256": projection_sha,
            "proof_state_sha256": proof_state_sha,
            "passport_sha256": passport_sha,
            "v6_receipt_digest": v6_receipt.receipt_digest,
            "epoch_id": epoch_id,
            "task_ids": [task.task_id for task in tasks],
            "proof_ids": [proof.proof_id for proof in proofs],
            "pending_request_ids": [request.request_id for request in pending_requests],
            "closure_gaps": list(closure_gaps),
            "compiler_gaps": list(dict.fromkeys(compiler_gaps)),
            "objective_satisfied": objective_satisfied,
            "truth_boundary": dict(truth_boundary),
        }
        receipt = AuthoritativeSnapshotReceipt(
            schema=SCHEMA,
            version=VERSION,
            compiler_id=COMPILER_ID,
            mission_id=mission_id,
            source_frontier=runtime.source_frontier,
            policy_sha256=runtime.policy_sha256,
            environment_sha256=runtime.environment_sha256,
            contract_epoch=contract_epoch,
            ledger_tail=ledger_tail,
            ledger_head_hash=ledger_head,
            mission_event_count=mission_event_count,
            projection_sha256=projection_sha,
            proof_state_sha256=proof_state_sha,
            passport_sha256=passport_sha,
            v6_receipt_digest=v6_receipt.receipt_digest,
            epoch_id=epoch_id,
            task_ids=tuple(task.task_id for task in tasks),
            proof_ids=tuple(proof.proof_id for proof in proofs),
            pending_request_ids=tuple(request.request_id for request in pending_requests),
            closure_gaps=closure_gaps,
            compiler_gaps=tuple(dict.fromkeys(compiler_gaps)),
            objective_satisfied=objective_satisfied,
            receipt_digest=_digest(material),
            truth_boundary=truth_boundary,
        )
        if not receipt.verify():
            raise ValueError("F130_AUTHORITATIVE_SNAPSHOT_RECEIPT_SELF_VERIFICATION_FAILED")
        return AuthoritativeSnapshotCompilation(
            snapshot=snapshot,
            receipt=receipt,
            passport=passport_snapshot,
        )


class F130AuthoritativeTerminalBinder:
    """Replay-resistant adapter from current durable mission truth into F130."""

    def __init__(
        self,
        *,
        compiler: F130AuthoritativeSnapshotCompiler | None = None,
        f130: MissionRuntimeInterlock | None = None,
    ) -> None:
        self.compiler = compiler or F130AuthoritativeSnapshotCompiler()
        self.f130 = f130 or MissionRuntimeInterlock()

    def prepare(
        self,
        *,
        runtime: DurableMissionRuntimeV1,
        passport: MissionProofPassport,
        mission_id: str,
        v6_receipt: RuntimeConvergenceReceiptV6,
        now_epoch: float,
    ) -> AuthoritativeTerminalPrepare:
        compiled = self.compiler.compile(
            runtime=runtime,
            passport=passport,
            mission_id=mission_id,
            v6_receipt=v6_receipt,
            completion_claim_requested=True,
        )
        prepare = self.f130.prepare_terminal(
            compiled.snapshot,
            now_epoch=now_epoch,
        )
        material = {
            "schema": PREPARE_SCHEMA,
            "version": VERSION,
            "mission_id": mission_id,
            "compiler_receipt_digest": compiled.receipt.receipt_digest,
            "ledger_head_hash": compiled.receipt.ledger_head_hash,
            "projection_sha256": compiled.receipt.projection_sha256,
            "epoch_id": compiled.receipt.epoch_id,
            "f130_prepare": asdict(prepare),
        }
        receipt = AuthoritativeTerminalPrepare(
            schema=PREPARE_SCHEMA,
            version=VERSION,
            mission_id=mission_id,
            compiler_receipt_digest=compiled.receipt.receipt_digest,
            ledger_head_hash=compiled.receipt.ledger_head_hash,
            projection_sha256=compiled.receipt.projection_sha256,
            epoch_id=compiled.receipt.epoch_id,
            f130_prepare=prepare,
            receipt_digest=_digest(material),
        )
        if not receipt.verify():
            raise ValueError("F130_AUTHORITATIVE_PREPARE_RECEIPT_SELF_VERIFICATION_FAILED")
        return receipt

    def commit(
        self,
        *,
        runtime: DurableMissionRuntimeV1,
        passport: MissionProofPassport,
        mission_id: str,
        v6_receipt: RuntimeConvergenceReceiptV6,
        prepared: AuthoritativeTerminalPrepare,
        now_epoch: float,
    ):
        if not prepared.verify():
            raise ValueError("F130_AUTHORITATIVE_PREPARE_INVALID")
        if prepared.mission_id != mission_id:
            raise ValueError("F130_AUTHORITATIVE_PREPARE_MISSION_MISMATCH")

        current = self.compiler.compile(
            runtime=runtime,
            passport=passport,
            mission_id=mission_id,
            v6_receipt=v6_receipt,
            completion_claim_requested=True,
        )
        expected = (
            ("compiler_receipt_digest", current.receipt.receipt_digest),
            ("ledger_head_hash", current.receipt.ledger_head_hash),
            ("projection_sha256", current.receipt.projection_sha256),
            ("epoch_id", current.receipt.epoch_id),
        )
        for field, value in expected:
            if getattr(prepared, field) != value:
                raise ValueError(
                    f"F130_AUTHORITATIVE_SNAPSHOT_DRIFT:{field}:"
                    f"{getattr(prepared, field)}!={value}"
                )

        return self.f130.commit_terminal(
            current.snapshot,
            prepared.f130_prepare,
            now_epoch=now_epoch,
        )


__all__ = [
    "AuthoritativeSnapshotCompilation",
    "AuthoritativeSnapshotReceipt",
    "AuthoritativeTerminalPrepare",
    "COMPILER_ID",
    "F130AuthoritativeSnapshotCompiler",
    "F130AuthoritativeTerminalBinder",
    "PREPARE_SCHEMA",
    "SCHEMA",
    "VERSION",
]
