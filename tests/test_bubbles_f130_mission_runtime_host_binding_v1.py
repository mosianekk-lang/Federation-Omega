from __future__ import annotations

import json
import tempfile
import unittest

from bubbles.autonomic_federation_runtime import BubblesAutonomicFederationRuntime
from bubbles.command_bus import build_receipt
from federation.fuse_mission_runtime_interlock_v1 import (
    MissionRuntimeInterlock,
    MissionRuntimeSnapshot,
    ProofBinding,
    RuntimeAction,
    RuntimeTask,
    RuntimeTaskState,
)


MISSION_ID = "FUSE-MOBILE-HISTORICAL-F130"


def _historical_snapshot(**overrides) -> MissionRuntimeSnapshot:
    base = dict(
        mission_id=MISSION_ID,
        current_mission_id=MISSION_ID,
        objective="Deliver one complete verified FUSE Mobile application",
        contract_epoch=14,
        ledger_tail=100,
        tasks=(
            RuntimeTask(
                task_id="F126",
                state=RuntimeTaskState.DONE,
                priority=10,
                required_proof_ids=("proof-f126",),
            ),
            RuntimeTask(task_id="F127", state=RuntimeTaskState.READY, priority=20),
        ),
        proofs=(
            ProofBinding(
                proof_id="proof-f126",
                task_id="F126",
                dependency="source-epoch",
                bound_epoch="14",
                current_epoch="14",
                fresh=True,
            ),
        ),
        objective_satisfied=False,
        completion_claim_requested=True,
    )
    base.update(overrides)
    return MissionRuntimeSnapshot(**base)


def _snapshot_mapping(snapshot: MissionRuntimeSnapshot) -> dict[str, object]:
    return {
        "mission_id": snapshot.mission_id,
        "current_mission_id": snapshot.current_mission_id,
        "objective": snapshot.objective,
        "contract_epoch": snapshot.contract_epoch,
        "ledger_tail": snapshot.ledger_tail,
        "tasks": [
            {
                "task_id": t.task_id,
                "state": t.state.value,
                "required": t.required,
                "dependencies": list(t.dependencies),
                "safe": t.safe,
                "authorized": t.authorized,
                "available": t.available,
                "owner_only": t.owner_only,
                "priority": t.priority,
                "lease_expires_at_epoch": t.lease_expires_at_epoch,
                "heartbeat_at_epoch": t.heartbeat_at_epoch,
                "heartbeat_ttl_seconds": t.heartbeat_ttl_seconds,
                "effect_id": t.effect_id,
                "effect_possible": t.effect_possible,
                "required_proof_ids": list(t.required_proof_ids),
                "recovery_exhausted": t.recovery_exhausted,
            }
            for t in snapshot.tasks
        ],
        "proofs": [
            {
                "proof_id": p.proof_id,
                "task_id": p.task_id,
                "dependency": p.dependency,
                "bound_epoch": p.bound_epoch,
                "current_epoch": p.current_epoch,
                "fresh": p.fresh,
            }
            for p in snapshot.proofs
        ],
        "objective_satisfied": snapshot.objective_satisfied,
        "completion_claim_requested": snapshot.completion_claim_requested,
        "candidate_response": snapshot.candidate_response,
        "status_only_requested": snapshot.status_only_requested,
        "proposed_owner_message": snapshot.proposed_owner_message,
        "genuine_owner_decisions": list(snapshot.genuine_owner_decisions),
        "irreducible_blocker": snapshot.irreducible_blocker,
        "exhaustion_evidence_ref": snapshot.exhaustion_evidence_ref,
    }


class F130BubblesHostBindingTests(unittest.TestCase):
    def test_bubbles_prefinal_historical_f126_done_f127_ready_dispatches_successor(self):
        with tempfile.TemporaryDirectory() as td:
            runtime = BubblesAutonomicFederationRuntime(
                td,
                source_frontier="main:test",
                policy_sha256="policy",
                environment_sha256="environment",
                cells=(),
            )
            hosted = runtime.before_final_response(_historical_snapshot(), now_epoch=1000.0)
        self.assertEqual(RuntimeAction.DISPATCH_TASK, hosted.decision.action)
        self.assertEqual("F127", hosted.decision.next_task_id)
        self.assertFalse(hosted.final_response_allowed)
        self.assertTrue(hosted.auto_continue_required)
        self.assertFalse(hosted.decision.completion_verified)

    def test_existing_command_bus_hosts_same_read_only_f130_decision(self):
        snapshot = _historical_snapshot()
        command = {
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "adapter_id": "bubbles_command_bus",
            "action": "f130_mission_runtime",
            "effect": "READ",
            "target_alias": "FUSE_F130_MISSION_RUNTIME",
            "payload": {
                "snapshot_scope": "WHOLE_OWNER_MISSION",
                "mode": "PREFINAL",
                "now_epoch": 1000.0,
                "snapshot": _snapshot_mapping(snapshot),
            },
        }
        receipt = build_receipt(json.dumps(command), actor="mosianekk-lang", event_name="workflow_dispatch", source_ref="test:f130")
        self.assertEqual("SUCCESS", receipt["state"])
        execution = receipt["execution"]
        self.assertEqual("DISPATCH_TASK", execution["action"])
        self.assertEqual("F127", execution["next_task_id"])
        self.assertFalse(execution["final_response_allowed"])
        self.assertTrue(execution["auto_continue_required"])
        self.assertFalse(execution["completion_verified"])
        self.assertEqual(0, execution["external_effects"])

    def test_f130_command_bus_action_cannot_be_promoted_to_write(self):
        command = {
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "adapter_id": "bubbles_command_bus",
            "action": "f130_mission_runtime",
            "effect": "LOW_RISK_WRITE",
            "target_alias": "FUSE_F130_MISSION_RUNTIME",
            "payload": {
                "snapshot_scope": "WHOLE_OWNER_MISSION",
                "mode": "PREFINAL",
                "snapshot": _snapshot_mapping(_historical_snapshot()),
            },
        }
        receipt = build_receipt(json.dumps(command), actor="mosianekk-lang", event_name="workflow_dispatch", source_ref="test:f130")
        self.assertEqual("CONSTRAINT", receipt["state"])
        self.assertIn("read-only", receipt["reason"])

    def test_hosted_action_rejects_partial_snapshot_scope(self):
        command = {
            "schema": "BUBBLES-CONTROL-COMMAND-V1",
            "adapter_id": "bubbles_command_bus",
            "action": "f130_mission_runtime",
            "effect": "READ",
            "target_alias": "FUSE_F130_MISSION_RUNTIME",
            "payload": {
                "snapshot_scope": "BUBBLES_PROVIDER_LOCAL",
                "snapshot": _snapshot_mapping(_historical_snapshot()),
            },
        }
        receipt = build_receipt(json.dumps(command), actor="mosianekk-lang", event_name="workflow_dispatch", source_ref="test:f130")
        self.assertEqual("FAILURE", receipt["state"])
        self.assertIn("WHOLE_OWNER_MISSION", receipt["reason"])

    def test_terminal_prepare_conflict_and_unchanged_commit(self):
        interlock = MissionRuntimeInterlock()
        complete = _historical_snapshot(tasks=(), proofs=(), objective_satisfied=True, ledger_tail=200)
        prepare_decision = interlock.decide(complete, now_epoch=1000.0)
        self.assertEqual(RuntimeAction.PREPARE_TERMINAL, prepare_decision.action)
        self.assertIsNotNone(prepare_decision.prepare)

        changed = _historical_snapshot(tasks=(), proofs=(), objective_satisfied=True, ledger_tail=201)
        conflict = interlock.commit_terminal(changed, prepare_decision.prepare, now_epoch=1001.0)
        self.assertEqual(RuntimeAction.TERMINAL_COMMIT_CONFLICT, conflict.action)
        self.assertFalse(conflict.completion_verified)

        committed = interlock.commit_terminal(complete, prepare_decision.prepare, now_epoch=1001.0)
        self.assertEqual(RuntimeAction.COMPLETE_VERIFIED, committed.action)
        self.assertTrue(committed.completion_verified)


if __name__ == "__main__":
    unittest.main()
