from pathlib import Path
import tempfile
import unittest

from benchmarking.cfbe_omega.mission_result_fabric_adapter_v1 import compile_mission_result_identity
from federation.mission_ir import MissionIR
from formation_omega.durable_mission_runtime_v1 import DurableMissionRuntimeV1
from formation_omega.mission_convergence import WorkItem, WorkStatus


class DurableMissionRuntimeV1Tests(unittest.TestCase):
    def _mission(self, *, source="main@test", objective="Complete one restart-safe bounded mission."):
        return MissionIR(
            mission_id="BCO-MISSION-001",
            objective=objective,
            domain="TEST",
            outcome_contract="One verified restart-safe mission result.",
            source_frontier=source,
            privacy_class="PUBLIC",
            rights_state="NOT_APPLICABLE",
            effect_class="READ_ONLY",
            rollback_required=False,
            proof_requirements=("READBACK",),
        ).normalized()

    def _runtime(self, root, *, source="main@test", policy="policy-v1", environment="env-v1"):
        return DurableMissionRuntimeV1(
            root,
            source_frontier=source,
            policy_sha256=policy,
            environment_sha256=environment,
        )

    def _prepare_restart_state(self, root):
        runtime = self._runtime(root)
        mission = self._mission()
        runtime.open(mission, required_proof_axes=("source",), trace_id="trace-001")
        runtime.set_work_item(
            mission.mission_id,
            WorkItem.create(work_id="A", lane="plan", objective="Compile deterministic plan"),
        )
        runtime.update_work_status(mission.mission_id, "A", WorkStatus.VERIFIED, result_refs=("result:A",))
        runtime.set_work_item(
            mission.mission_id,
            WorkItem.create(
                work_id="B",
                lane="verify",
                objective="Verify resumed work",
                dependencies=("A",),
            ),
        )
        request = runtime.request(
            mission.mission_id,
            step_id="B",
            request_type="OWNER_OR_PROVIDER_INPUT",
            target="test-target",
            reason="Wait for bounded continuation input.",
            input_identity={"need": "approval"},
            continuation_key="continue-B",
            required_authority=("TEST_BOUNDED",),
            expires_at="2026-09-01T01:00:00+02:00",
            created_at="2026-08-31T22:30:00+02:00",
        )
        checkpoint = runtime.checkpoint(
            mission.mission_id,
            trace_id="trace-001",
            created_at="2026-08-31T22:31:00+02:00",
        )
        return runtime, mission, request, checkpoint

    def test_checkpoint_restart_restores_work_and_pending_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, mission, request, checkpoint = self._prepare_restart_state(tmp)
            restarted = self._runtime(tmp)
            receipt = restarted.resume(mission, now="2026-08-31T22:32:00+02:00", trace_id="trace-restart")
            self.assertEqual("RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED", receipt.state)
            self.assertTrue(receipt.replayed_from_event_truth)
            self.assertEqual(checkpoint.checkpoint_id, receipt.checkpoint_id)
            self.assertEqual((request.request_id,), receipt.pending_request_ids)
            self.assertEqual(("B",), receipt.ready_work_ids)
            projection = restarted.project(mission.mission_id)
            self.assertEqual(WorkStatus.VERIFIED, projection.work_items["A"].status)
            self.assertEqual("CHECKPOINT_VALID", restarted.verify(mission.mission_id)["checkpoint_state"])

    def test_corrupt_checkpoint_is_ignored_and_event_truth_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime, mission, _, _ = self._prepare_restart_state(tmp)
            runtime.checkpoint_path(mission.mission_id).write_text("{not-json", encoding="utf-8")
            restarted = self._runtime(tmp)
            receipt = restarted.resume(mission, now="2026-08-31T22:32:00+02:00")
            self.assertEqual("RESUMED_FROM_EVENT_TRUTH", receipt.state)
            self.assertEqual("CHECKPOINT_INVALID_JSON", receipt.reason)
            self.assertTrue(receipt.replayed_from_event_truth)
            self.assertEqual(("B",), receipt.ready_work_ids)

    def test_source_policy_environment_and_mission_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(tmp)
            mission = self._mission()
            runtime.open(mission, required_proof_axes=("source",))

            changed_source = self._mission(source="main@changed")
            source_runtime = self._runtime(tmp, source="main@changed")
            self.assertEqual(
                "HOLD_SOURCE_DRIFT",
                source_runtime.resume(changed_source, now="2026-08-31T22:32:00+02:00").state,
            )

            policy_runtime = self._runtime(tmp, policy="policy-v2")
            self.assertEqual(
                "HOLD_POLICY_DRIFT",
                policy_runtime.resume(mission, now="2026-08-31T22:32:00+02:00").state,
            )

            environment_runtime = self._runtime(tmp, environment="env-v2")
            self.assertEqual(
                "HOLD_ENVIRONMENT_DRIFT",
                environment_runtime.resume(mission, now="2026-08-31T22:32:00+02:00").state,
            )

            changed_mission = self._mission(objective="Complete a materially different restart-safe mission.")
            identity_runtime = self._runtime(tmp)
            self.assertEqual(
                "HOLD_MISSION_IDENTITY_DRIFT",
                identity_runtime.resume(changed_mission, now="2026-08-31T22:32:00+02:00").state,
            )

    def test_pending_request_identity_conflict_and_resolution_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(tmp)
            mission = self._mission()
            runtime.open(mission, required_proof_axes=("source",))
            request = runtime.request(
                mission.mission_id,
                request_id="REQ-EXACT-1",
                step_id="A",
                request_type="INPUT",
                target="target",
                reason="Need one response.",
                input_identity={"value": "alpha"},
                continuation_key="continue-A",
                created_at="2026-08-31T22:30:00+02:00",
            )
            replay = runtime.request(
                mission.mission_id,
                request_id="REQ-EXACT-1",
                step_id="A",
                request_type="INPUT",
                target="target",
                reason="Need one response.",
                input_identity={"value": "alpha"},
                continuation_key="continue-A",
            )
            self.assertEqual(request.request_id, replay.request_id)
            with self.assertRaisesRegex(ValueError, "IDENTITY_CONFLICT"):
                runtime.request(
                    mission.mission_id,
                    request_id="REQ-EXACT-1",
                    step_id="A",
                    request_type="INPUT",
                    target="target",
                    reason="Need one response.",
                    input_identity={"value": "changed"},
                    continuation_key="continue-A",
                )

            resolved = runtime.resolve_request(
                mission.mission_id,
                request.request_id,
                response_ref="response:1",
                response_sha256="a" * 64,
                proof_refs=("proof:response",),
                resolved_at="2026-08-31T22:31:00+02:00",
            )
            self.assertEqual("RESOLVED", resolved.state)
            replayed_resolution = runtime.resolve_request(
                mission.mission_id,
                request.request_id,
                response_ref="response:1",
                response_sha256="a" * 64,
                proof_refs=("proof:response",),
                resolved_at="2026-08-31T22:31:30+02:00",
            )
            self.assertEqual("RESOLVED", replayed_resolution.state)
            with self.assertRaisesRegex(ValueError, "TRANSITION_CONFLICT"):
                runtime.resolve_request(
                    mission.mission_id,
                    request.request_id,
                    response_ref="response:changed",
                    response_sha256="b" * 64,
                )

    def test_expired_pending_request_holds_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(tmp)
            mission = self._mission()
            runtime.open(mission, required_proof_axes=("source",))
            request = runtime.request(
                mission.mission_id,
                step_id="A",
                request_type="AUTHORITY",
                target="provider",
                reason="Wait for bounded authority.",
                input_identity={"scope": "bounded"},
                continuation_key="continue-A",
                required_authority=("PROVIDER_BOUNDED",),
                expires_at="2026-08-31T22:31:00+02:00",
                created_at="2026-08-31T22:30:00+02:00",
            )
            runtime.checkpoint(mission.mission_id, created_at="2026-08-31T22:30:30+02:00")
            restarted = self._runtime(tmp)
            receipt = restarted.resume(mission, now="2026-08-31T22:32:00+02:00")
            self.assertEqual("HOLD_PENDING_REQUEST_EXPIRED", receipt.state)
            projected = {item.request_id: item for item in restarted.requests(mission.mission_id)}
            self.assertEqual("EXPIRED", projected[request.request_id].state)

    def test_bound_result_reuses_after_restart_and_expiry_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(tmp)
            mission = self._mission()
            runtime.open(mission, required_proof_axes=("source",))
            identity = compile_mission_result_identity(
                mission,
                step_id="compile-plan",
                input_identity={"payload": "alpha"},
                policy_identity={"policy": "v1"},
                environment_identity={"runtime": "python312"},
                proof_scope="BCO_TEST",
                fresh_until="2026-08-31T22:40:00+02:00",
            )
            runtime.bind_result(
                mission.mission_id,
                identity,
                result_ref="runtime/result.json",
                result_sha256="c" * 64,
                proof_refs=("proof:result",),
                recorded_at="2026-08-31T22:30:00+02:00",
                now="2026-08-31T22:30:00+02:00",
            )
            runtime.checkpoint(mission.mission_id, created_at="2026-08-31T22:31:00+02:00")

            restarted = self._runtime(tmp)
            good = restarted.resume(mission, now="2026-08-31T22:32:00+02:00")
            self.assertEqual("RESUMED_EVENT_REPLAY_CHECKPOINT_VALIDATED", good.state)
            self.assertEqual("HIT", restarted.result_index.lookup(identity, now="2026-08-31T22:32:00+02:00").state)

            expired = self._runtime(tmp)
            held = expired.resume(mission, now="2026-08-31T22:41:00+02:00")
            self.assertEqual("HOLD_RESULT_FRESHNESS_EXPIRED", held.state)

    def test_ledger_tamper_is_rejected_on_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = self._runtime(tmp)
            mission = self._mission()
            runtime.open(mission, required_proof_axes=("source",))
            path = Path(tmp) / "mission-events.jsonl"
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("BCO_MISSION_IR_BOUND", "BCO_MISSION_IR_BROKEN", 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "MCE_LEDGER_HASH_MISMATCH"):
                self._runtime(tmp)


if __name__ == "__main__":
    unittest.main()
