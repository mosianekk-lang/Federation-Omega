from __future__ import annotations

import os
import tempfile
import unittest

from bubbles.chat_governor_omega3.mission_runtime_host_v1 import MissionRuntimeHostInterlock
from bubbles.chat_governor_omega3.state import DurableState
from federation.fuse_mission_runtime_interlock_v1 import (
    MissionRuntimeInterlock,
    MissionRuntimeSnapshot,
    ProofBinding,
    RuntimeAction,
    RuntimeTask,
    RuntimeTaskState,
)


class MissionRuntimeInterlockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.interlock = MissionRuntimeInterlock()

    @staticmethod
    def snapshot(**overrides) -> MissionRuntimeSnapshot:
        base = dict(
            mission_id="FUSE-MOBILE",
            current_mission_id="FUSE-MOBILE",
            objective="Deliver one complete verified FUSE Mobile application",
            contract_epoch=14,
            ledger_tail=100,
        )
        base.update(overrides)
        return MissionRuntimeSnapshot(**base)

    def test_f126_milestone_cannot_end_owner_mission_and_f127_is_selected(self) -> None:
        tasks = (
            RuntimeTask("F126_REPOSITORY_HYGIENE", RuntimeTaskState.DONE, priority=100),
            RuntimeTask("F127_VERSION_CONTRACT", RuntimeTaskState.READY, dependencies=("F126_REPOSITORY_HYGIENE",), priority=95),
            RuntimeTask("FINAL_APK", RuntimeTaskState.READY, dependencies=("F127_VERSION_CONTRACT",), priority=90),
            RuntimeTask("API35_MDTAF", RuntimeTaskState.READY, dependencies=("FINAL_APK",), priority=80),
            RuntimeTask("API36_MDTAF", RuntimeTaskState.READY, dependencies=("FINAL_APK",), priority=80),
            RuntimeTask("SEMANTIC_PATH", RuntimeTaskState.READY, dependencies=("API35_MDTAF", "API36_MDTAF"), priority=70),
            RuntimeTask("OWNER_DEVICE", RuntimeTaskState.READY, dependencies=("SEMANTIC_PATH",), priority=60),
        )
        decision = self.interlock.decide(
            self.snapshot(
                tasks=tasks,
                completion_claim_requested=True,
                candidate_response="F126 repository hygiene recovery is complete.",
            ),
            now_epoch=1000,
        )
        self.assertEqual(RuntimeAction.DISPATCH_TASK, decision.action)
        self.assertEqual("F127_VERSION_CONTRACT", decision.next_task_id)
        self.assertFalse(decision.final_response_allowed)
        self.assertTrue(decision.auto_continue_required)
        self.assertFalse(decision.completion_verified)

    def test_expired_worker_without_possible_effect_is_reclaimed(self) -> None:
        task = RuntimeTask(
            "BUILD_APK",
            RuntimeTaskState.RUNNING,
            lease_expires_at_epoch=100,
            heartbeat_at_epoch=80,
            heartbeat_ttl_seconds=10,
        )
        decision = self.interlock.decide(self.snapshot(tasks=(task,)), now_epoch=200)
        self.assertEqual(RuntimeAction.RECOVER_ORPHAN, decision.action)
        self.assertEqual("BUILD_APK", decision.next_task_id)

    def test_expired_worker_with_possible_effect_reads_back_before_retry(self) -> None:
        task = RuntimeTask(
            "DEPLOY_GATEWAY",
            RuntimeTaskState.RUNNING,
            lease_expires_at_epoch=100,
            heartbeat_at_epoch=80,
            heartbeat_ttl_seconds=10,
            effect_id="effect-42",
            effect_possible=True,
        )
        decision = self.interlock.decide(self.snapshot(tasks=(task,)), now_epoch=200)
        self.assertEqual(RuntimeAction.READBACK_EFFECT, decision.action)
        self.assertEqual("DEPLOY_GATEWAY", decision.next_task_id)

    def test_explicit_ambiguous_effect_reads_back_before_retry(self) -> None:
        task = RuntimeTask("PUBLISH", RuntimeTaskState.EFFECT_AMBIGUOUS, effect_id="E1", effect_possible=True)
        decision = self.interlock.decide(self.snapshot(tasks=(task,)), now_epoch=10)
        self.assertEqual(RuntimeAction.READBACK_EFFECT, decision.action)

    def test_dependency_scoped_stale_proof_invalidates_done_task(self) -> None:
        task = RuntimeTask(
            "API36_MDTAF",
            RuntimeTaskState.DONE,
            required_proof_ids=("proof-api36",),
            priority=90,
        )
        proof = ProofBinding(
            proof_id="proof-api36",
            task_id="API36_MDTAF",
            dependency="APK_SHA256",
            bound_epoch="sha256:old",
            current_epoch="sha256:new",
        )
        decision = self.interlock.decide(self.snapshot(tasks=(task,), proofs=(proof,)), now_epoch=10)
        self.assertEqual(RuntimeAction.REVERIFY_PROOF, decision.action)
        self.assertEqual("API36_MDTAF", decision.next_task_id)
        self.assertFalse(decision.final_response_allowed)

    def test_machine_resolvable_owner_handoff_is_rejected(self) -> None:
        task = RuntimeTask(
            "RERUN_CI",
            RuntimeTaskState.OWNER_HELD,
            owner_only=False,
            safe=True,
            authorized=True,
            available=True,
        )
        decision = self.interlock.decide(self.snapshot(tasks=(task,)), now_epoch=10)
        self.assertEqual(RuntimeAction.REJECT_OWNER_HANDOFF, decision.action)
        self.assertEqual("RERUN_CI", decision.next_task_id)

    def test_status_response_is_allowed_without_terminating_mission(self) -> None:
        task = RuntimeTask("F127_VERSION_CONTRACT", RuntimeTaskState.READY, priority=5)
        decision = self.interlock.decide(
            self.snapshot(tasks=(task,), status_only_requested=True),
            now_epoch=10,
        )
        self.assertEqual(RuntimeAction.ALLOW_STATUS_CONTINUE, decision.action)
        self.assertTrue(decision.final_response_allowed)
        self.assertTrue(decision.auto_continue_required)
        self.assertEqual("F127_VERSION_CONTRACT", decision.next_task_id)
        self.assertFalse(decision.completion_verified)

    def test_terminal_requires_prepare_then_commit(self) -> None:
        task = RuntimeTask("OWNER_OUTCOME", RuntimeTaskState.DONE)
        snapshot = self.snapshot(tasks=(task,), objective_satisfied=True)
        first = self.interlock.decide(snapshot, now_epoch=10)
        self.assertEqual(RuntimeAction.PREPARE_TERMINAL, first.action)
        self.assertIsNotNone(first.prepare)
        self.assertFalse(first.final_response_allowed)
        committed = self.interlock.commit_terminal(snapshot, first.prepare, now_epoch=10)  # type: ignore[arg-type]
        self.assertEqual(RuntimeAction.COMPLETE_VERIFIED, committed.action)
        self.assertTrue(committed.final_response_allowed)
        self.assertFalse(committed.auto_continue_required)
        self.assertTrue(committed.completion_verified)

    def test_terminal_compare_and_swap_rejects_ledger_tail_race(self) -> None:
        task = RuntimeTask("OWNER_OUTCOME", RuntimeTaskState.DONE)
        snapshot = self.snapshot(tasks=(task,), objective_satisfied=True, ledger_tail=100)
        prepared = self.interlock.prepare_terminal(snapshot, now_epoch=10)
        changed = self.snapshot(tasks=(task,), objective_satisfied=True, ledger_tail=101)
        decision = self.interlock.commit_terminal(changed, prepared, now_epoch=10)
        self.assertEqual(RuntimeAction.TERMINAL_COMMIT_CONFLICT, decision.action)
        self.assertFalse(decision.final_response_allowed)
        self.assertTrue(decision.auto_continue_required)

    def test_missing_required_proof_blocks_completion(self) -> None:
        task = RuntimeTask("FINAL_APK", RuntimeTaskState.DONE, required_proof_ids=("apk-proof",))
        decision = self.interlock.decide(
            self.snapshot(tasks=(task,), objective_satisfied=True),
            now_epoch=10,
        )
        self.assertEqual(RuntimeAction.REVERIFY_PROOF, decision.action)
        self.assertFalse(decision.final_response_allowed)

    def test_genuine_owner_only_decision_surfaces_after_machine_work_is_absent(self) -> None:
        task = RuntimeTask(
            "PHYSICAL_CONSENT",
            RuntimeTaskState.OWNER_HELD,
            owner_only=True,
            available=False,
        )
        decision = self.interlock.decide(
            self.snapshot(tasks=(task,), genuine_owner_decisions=("Approve physical-device pairing",)),
            now_epoch=10,
        )
        self.assertEqual(RuntimeAction.OWNER_DECISION_REQUIRED, decision.action)
        self.assertTrue(decision.final_response_allowed)
        self.assertFalse(decision.auto_continue_required)

    def test_proven_irreducible_blocker_is_not_mislabelled_complete(self) -> None:
        task = RuntimeTask(
            "PHYSICAL_DEVICE",
            RuntimeTaskState.PROVIDER_HELD,
            recovery_exhausted=True,
            available=False,
        )
        decision = self.interlock.decide(
            self.snapshot(
                tasks=(task,),
                irreducible_blocker="No callable physical-device bridge remains",
                exhaustion_evidence_ref="proof:route-exhaustion",
            ),
            now_epoch=10,
        )
        self.assertEqual(RuntimeAction.BLOCKED_IRREDUCIBLY, decision.action)
        self.assertTrue(decision.final_response_allowed)
        self.assertFalse(decision.completion_verified)

    def test_highest_priority_ready_task_wins(self) -> None:
        tasks = (
            RuntimeTask("LOW", RuntimeTaskState.READY, priority=1),
            RuntimeTask("HIGH", RuntimeTaskState.READY, priority=99),
        )
        decision = self.interlock.decide(self.snapshot(tasks=tasks), now_epoch=10)
        self.assertEqual("HIGH", decision.next_task_id)

    def test_ten_deterministic_runs_are_identical(self) -> None:
        snapshot = self.snapshot(tasks=(RuntimeTask("NEXT", RuntimeTaskState.READY, priority=1),))
        digests = {self.interlock.decide(snapshot, now_epoch=10).receipt_digest for _ in range(10)}
        self.assertEqual(1, len(digests))


class MissionRuntimeHostBindingTests(unittest.TestCase):
    def test_host_persists_blocked_final_decision_and_terminal_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = DurableState(os.path.join(tmp, "mission-runtime.sqlite3"))
            host = MissionRuntimeHostInterlock(state)
            active = MissionRuntimeSnapshot(
                mission_id="FUSE-MOBILE",
                current_mission_id="FUSE-MOBILE",
                objective="Deliver FUSE Mobile",
                contract_epoch=1,
                ledger_tail=1,
                tasks=(RuntimeTask("F127", RuntimeTaskState.READY),),
            )
            first = host.before_final_response(active, now_epoch=10)
            self.assertFalse(first.final_response_allowed)
            checkpoint = state.latest_checkpoint("FUSE-MOBILE")
            self.assertIsNotNone(checkpoint)
            self.assertEqual("MISSION_RUNTIME_PRE_FINAL", checkpoint["payload"]["event"])  # type: ignore[index]

            done = MissionRuntimeSnapshot(
                mission_id="FUSE-MOBILE",
                current_mission_id="FUSE-MOBILE",
                objective="Deliver FUSE Mobile",
                contract_epoch=1,
                ledger_tail=2,
                tasks=(RuntimeTask("OWNER_OUTCOME", RuntimeTaskState.DONE),),
                objective_satisfied=True,
            )
            prepare = host.interlock.prepare_terminal(done, now_epoch=10)
            terminal = host.commit_terminal(done, prepare, now_epoch=10)
            self.assertTrue(terminal.final_response_allowed)
            proof_checkpoint = state.latest_checkpoint("FUSE-MOBILE")
            self.assertEqual(1, proof_checkpoint["proof_bearing"])  # type: ignore[index]
            self.assertEqual("MISSION_RUNTIME_TERMINAL_COMMIT", proof_checkpoint["payload"]["event"])  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
