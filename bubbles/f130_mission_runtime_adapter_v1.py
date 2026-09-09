from __future__ import annotations

"""Bounded JSON adapter for the existing Bubbles Command Bus F130 court."""

from dataclasses import asdict
from pathlib import Path
import tempfile
from typing import Mapping

from bubbles.chat_governor_omega3.mission_runtime_host_v1 import MissionRuntimeHostInterlock
from bubbles.chat_governor_omega3.state import DurableState
from federation.fuse_mission_runtime_interlock_v1 import (
    MissionRuntimeSnapshot,
    ProofBinding,
    RuntimeTask,
    RuntimeTaskState,
    TerminalPrepareReceipt,
)

ADAPTER_SCHEMA = "F130-MISSION-RUNTIME-COMMAND-ADAPTER-V1"
WHOLE_MISSION_SCOPE = "WHOLE_OWNER_MISSION"


class F130CommandError(ValueError):
    pass


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise F130CommandError(f"{field} must be a JSON object")
    return value


def snapshot_from_mapping(value: Mapping[str, object]) -> MissionRuntimeSnapshot:
    tasks_raw = value.get("tasks", ())
    proofs_raw = value.get("proofs", ())
    if not isinstance(tasks_raw, list):
        raise F130CommandError("snapshot.tasks must be a JSON array")
    if not isinstance(proofs_raw, list):
        raise F130CommandError("snapshot.proofs must be a JSON array")
    tasks = []
    for item_raw in tasks_raw:
        item = _mapping(item_raw, "snapshot.tasks[]")
        tasks.append(RuntimeTask(
            task_id=str(item["task_id"]),
            state=RuntimeTaskState(str(item["state"])),
            required=bool(item.get("required", True)),
            dependencies=tuple(str(x) for x in item.get("dependencies", ())),
            safe=bool(item.get("safe", True)),
            authorized=bool(item.get("authorized", True)),
            available=bool(item.get("available", True)),
            owner_only=bool(item.get("owner_only", False)),
            priority=int(item.get("priority", 0)),
            lease_expires_at_epoch=float(item.get("lease_expires_at_epoch", 0.0)),
            heartbeat_at_epoch=float(item.get("heartbeat_at_epoch", 0.0)),
            heartbeat_ttl_seconds=float(item.get("heartbeat_ttl_seconds", 120.0)),
            effect_id=str(item.get("effect_id", "")),
            effect_possible=bool(item.get("effect_possible", False)),
            required_proof_ids=tuple(str(x) for x in item.get("required_proof_ids", ())),
            recovery_exhausted=bool(item.get("recovery_exhausted", False)),
        ))
    proofs = []
    for item_raw in proofs_raw:
        item = _mapping(item_raw, "snapshot.proofs[]")
        proofs.append(ProofBinding(
            proof_id=str(item["proof_id"]),
            task_id=str(item["task_id"]),
            dependency=str(item["dependency"]),
            bound_epoch=str(item["bound_epoch"]),
            current_epoch=str(item["current_epoch"]),
            fresh=bool(item.get("fresh", True)),
        ))
    return MissionRuntimeSnapshot(
        mission_id=str(value["mission_id"]),
        current_mission_id=str(value["current_mission_id"]),
        objective=str(value["objective"]),
        contract_epoch=int(value["contract_epoch"]),
        ledger_tail=int(value["ledger_tail"]),
        tasks=tuple(tasks),
        proofs=tuple(proofs),
        objective_satisfied=bool(value.get("objective_satisfied", False)),
        completion_claim_requested=bool(value.get("completion_claim_requested", False)),
        candidate_response=str(value.get("candidate_response", "")),
        status_only_requested=bool(value.get("status_only_requested", False)),
        proposed_owner_message=str(value.get("proposed_owner_message", "")),
        genuine_owner_decisions=tuple(str(x) for x in value.get("genuine_owner_decisions", ())),
        irreducible_blocker=str(value.get("irreducible_blocker", "")),
        exhaustion_evidence_ref=str(value.get("exhaustion_evidence_ref", "")),
    )


def prepare_from_mapping(value: Mapping[str, object]) -> TerminalPrepareReceipt:
    return TerminalPrepareReceipt(
        schema=str(value["schema"]),
        version=str(value["version"]),
        mission_id=str(value["mission_id"]),
        contract_epoch=int(value["contract_epoch"]),
        ledger_tail=int(value["ledger_tail"]),
        state_digest=str(value["state_digest"]),
    )


def _decision_record(hosted) -> dict[str, object]:
    decision = hosted.decision
    record = asdict(decision)
    record["action"] = decision.action.value
    return record


def execute_f130_mission_runtime(payload: Mapping[str, object]) -> dict[str, object]:
    if str(payload.get("snapshot_scope", "")) != WHOLE_MISSION_SCOPE:
        raise F130CommandError("snapshot_scope must be WHOLE_OWNER_MISSION")
    snapshot = snapshot_from_mapping(_mapping(payload.get("snapshot"), "snapshot"))
    now_epoch = float(payload.get("now_epoch", 0.0))
    mode = str(payload.get("mode", "PREFINAL")).upper()
    with tempfile.TemporaryDirectory(prefix="f130-bubbles-host-") as td:
        host = MissionRuntimeHostInterlock(DurableState(str(Path(td) / "chatgov.sqlite3")))
        if mode == "PREFINAL":
            hosted = host.before_final_response(snapshot, now_epoch=now_epoch)
        elif mode == "TERMINAL_COMMIT":
            prepare = prepare_from_mapping(_mapping(payload.get("prepare"), "prepare"))
            hosted = host.commit_terminal(snapshot, prepare, now_epoch=now_epoch)
        else:
            raise F130CommandError("mode must be PREFINAL or TERMINAL_COMMIT")
    decision = hosted.decision
    return {
        "schema": ADAPTER_SCHEMA,
        "kind": "F130_MISSION_RUNTIME_HOSTED_COURT",
        "mode": mode,
        "mission_id": snapshot.mission_id,
        "checkpoint_id": hosted.checkpoint_id,
        "decision": _decision_record(hosted),
        "action": decision.action.value,
        "next_task_id": decision.next_task_id,
        "final_response_allowed": decision.final_response_allowed,
        "auto_continue_required": decision.auto_continue_required,
        "completion_verified": decision.completion_verified,
        "provider_effects": False,
        "external_effects": 0,
        "truth_boundary": {
            "whole_mission_snapshot_is_caller_supplied": True,
            "bubbles_local_work_graph_is_not_whole_mission_authority": True,
            "hosted_receipt_alone_proves_autopilot_consumption": False,
            "native_chatgpt_serving_stack_interception_proven": False,
        },
    }


__all__ = [
    "ADAPTER_SCHEMA",
    "F130CommandError",
    "WHOLE_MISSION_SCOPE",
    "execute_f130_mission_runtime",
    "prepare_from_mapping",
    "snapshot_from_mapping",
]
