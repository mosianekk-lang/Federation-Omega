from __future__ import annotations

import unittest

from bubbles.agent_fabric import (
    BubblesOmegaAgentFabric,
    DirectiveMission,
    DirectiveTask,
    EffectClass,
    EffectPermit,
    MissionState,
    TaskState,
    WorkerKind,
    WorkerSpec,
)


class BubblesOmegaAgentFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = BubblesOmegaAgentFabric()

    @staticmethod
    def mission() -> DirectiveMission:
        return DirectiveMission(
            mission_id="M-001",
            objective="Complete a directive with proof",
            tasks=(
                DirectiveTask("discover", "Find sources", ("research",)),
                DirectiveTask("build", "Build implementation", ("software", "testing"), depends_on=("discover",)),
                DirectiveTask("prove", "Verify proof", ("proof", "readback"), depends_on=("build",)),
            ),
        )

    def test_compile_builds_dependency_waves_and_agents_plus_bots(self) -> None:
        plan = self.fabric.compile(self.mission())
        self.assertEqual((("discover",), ("build",), ("prove",)), plan.waves)
        self.assertFalse(plan.unresolved_tasks)
        assignment = next(item for item in plan.assignments if item.task_id == "build")
        self.assertIn("BUBBLES-OMEGA-FORGE", assignment.primary_agents)
        self.assertIn("BUBBLES-OMEGA-PROOF-BOT", assignment.support_bots)
        self.assertIn("BUBBLES-OMEGA-CHECKPOINT-BOT", assignment.support_bots)

    def test_empty_and_invalid_missions_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one task"):
            self.fabric.compile(DirectiveMission("empty", "empty", ()))
        with self.assertRaisesRegex(ValueError, "max_safe_parallel"):
            self.fabric.compile(DirectiveMission("m", "m", (DirectiveTask("x", "x", ("research",)),), max_safe_parallel=0))
        with self.assertRaisesRegex(ValueError, "max_effect_lanes"):
            self.fabric.compile(DirectiveMission("m2", "m2", (DirectiveTask("x", "x", ("research",)),), max_effect_lanes=-1))

    def test_invalid_worker_parallel_limit_fails_closed(self) -> None:
        workers = (
            WorkerSpec("BUBBLES-OMEGA-CONTROLLER", "controller", WorkerKind.AGENT, ("orchestration",), max_parallel=0),
        )
        with self.assertRaisesRegex(ValueError, "worker max_parallel"):
            BubblesOmegaAgentFabric(workers)

    def test_cycle_fails_closed(self) -> None:
        mission = DirectiveMission(
            "cycle",
            "bad graph",
            (
                DirectiveTask("a", "a", ("research",), depends_on=("b",)),
                DirectiveTask("b", "b", ("software",), depends_on=("a",)),
            ),
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.fabric.compile(mission)

    def test_unrelated_lane_remains_ready(self) -> None:
        mission = DirectiveMission(
            "parallel",
            "isolate failures",
            (
                DirectiveTask("a", "lane a", ("research",)),
                DirectiveTask("b", "lane b", ("software",)),
                DirectiveTask("c", "depends a", ("proof",), depends_on=("a",)),
            ),
        )
        self.fabric.task_state[("parallel", "a")] = TaskState.FAILURE
        self.assertIn("b", self.fabric.ready_tasks(mission))
        self.assertNotIn("c", self.fabric.ready_tasks(mission))

    def test_unresolved_capability_is_not_released_as_ready_work(self) -> None:
        mission = DirectiveMission("gap", "gap", (DirectiveTask("x", "x", ("capability-that-does-not-exist",)),))
        self.assertEqual(("x",), self.fabric.compile(mission).unresolved_tasks)
        self.assertEqual((), self.fabric.ready_tasks(mission))

    def test_ready_tasks_enforces_one_effect_lane(self) -> None:
        mission = DirectiveMission(
            "effects",
            "serialize provider lanes",
            (
                DirectiveTask("read-a", "read a", ("provider-read",), target="a", effect=EffectClass.READ_ONLY_PROVIDER),
                DirectiveTask("read-b", "read b", ("provider-read",), target="b", effect=EffectClass.READ_ONLY_PROVIDER),
                DirectiveTask("internal", "internal", ("research",)),
            ),
            max_safe_parallel=3,
            max_effect_lanes=1,
        )
        ready = self.fabric.ready_tasks(mission)
        self.assertEqual(1, sum(task_id.startswith("read-") for task_id in ready))
        self.assertIn("internal", ready)

    def test_running_effect_lane_blocks_second_effect_but_not_internal_lane(self) -> None:
        mission = DirectiveMission(
            "effects-running",
            "respect in-flight lanes",
            (
                DirectiveTask("read-a", "read a", ("provider-read",), target="a", effect=EffectClass.READ_ONLY_PROVIDER),
                DirectiveTask("read-b", "read b", ("provider-read",), target="b", effect=EffectClass.READ_ONLY_PROVIDER),
                DirectiveTask("internal", "internal", ("research",)),
            ),
            max_safe_parallel=3,
            max_effect_lanes=1,
        )
        self.fabric.task_state[(mission.mission_id, "read-a")] = TaskState.RUNNING
        ready = self.fabric.ready_tasks(mission)
        self.assertNotIn("read-b", ready)
        self.assertIn("internal", ready)

    def test_running_parallel_slots_are_subtracted(self) -> None:
        mission = DirectiveMission(
            "slots",
            "respect running work",
            (
                DirectiveTask("a", "a", ("research",)),
                DirectiveTask("b", "b", ("software",)),
                DirectiveTask("c", "c", ("proof",)),
            ),
            max_safe_parallel=2,
        )
        self.fabric.task_state[(mission.mission_id, "a")] = TaskState.RUNNING
        self.assertEqual(1, len(self.fabric.ready_tasks(mission)))

    def test_worker_specific_parallel_capacity_is_enforced(self) -> None:
        workers = (
            WorkerSpec("BUBBLES-OMEGA-CONTROLLER", "controller", WorkerKind.AGENT, ("orchestration",)),
            WorkerSpec("ONE-SLOT", "one slot", WorkerKind.AGENT, ("special",), max_parallel=1),
        )
        fabric = BubblesOmegaAgentFabric(workers)
        mission = DirectiveMission(
            "worker-capacity",
            "respect worker capacity",
            (
                DirectiveTask("a", "a", ("special",)),
                DirectiveTask("b", "b", ("special",)),
            ),
            max_safe_parallel=2,
        )
        fabric.task_state[(mission.mission_id, "a")] = TaskState.RUNNING
        self.assertEqual((), fabric.ready_tasks(mission))

    def test_read_only_provider_task_requires_exact_route_bound_permit(self) -> None:
        mission = DirectiveMission(
            "provider",
            "read provider",
            (DirectiveTask("read", "read", ("provider-read",), target="drive", effect=EffectClass.READ_ONLY_PROVIDER),),
        )
        blocked = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=lambda *_: {"state": "SUCCESS", "evidence_refs": ["should-not-run"]},
            route_fingerprint="route-a",
        )
        self.assertEqual(TaskState.CONSTRAINT, blocked.state)
        self.fabric.reopen_task(mission, "read", changed_route_fingerprint="route-b")
        wrong_route = EffectPermit("p-wrong", "provider", "read", "drive", EffectClass.READ_ONLY_PROVIDER, "route-a")
        held = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=lambda *_: {"state": "SUCCESS", "evidence_refs": ["should-not-run"]},
            route_fingerprint="route-b",
            permit=wrong_route,
        )
        self.assertEqual(TaskState.CONSTRAINT, held.state)
        self.assertIn("PERMIT", held.note)
        self.fabric.reopen_task(mission, "read", changed_route_fingerprint="route-c")
        permit = EffectPermit("p1", "provider", "read", "drive", EffectClass.READ_ONLY_PROVIDER, "route-c")
        passed = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=lambda *_: {"state": "SUCCESS", "evidence_refs": ["provider-readback-1"]},
            route_fingerprint="route-c",
            permit=permit,
        )
        self.assertEqual(TaskState.SUCCESS, passed.state)
        self.assertIn("provider-readback-1", passed.evidence_refs)

    def test_provider_success_without_readback_evidence_is_held(self) -> None:
        mission = DirectiveMission(
            "no-proof",
            "provider result must carry proof",
            (DirectiveTask("read", "read", ("provider-read",), target="drive", effect=EffectClass.READ_ONLY_PROVIDER),),
        )
        permit = EffectPermit("p-no-proof", mission.mission_id, "read", "drive", EffectClass.READ_ONLY_PROVIDER, "route-a")
        receipt = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="route-a",
            permit=permit,
        )
        self.assertEqual(TaskState.CONSTRAINT, receipt.state)
        self.assertIn("READBACK_EVIDENCE", receipt.note)

    def test_non_internal_permit_is_consumed_before_dispatch(self) -> None:
        mission = DirectiveMission(
            "consume-before-dispatch",
            "consume permit before executor",
            (DirectiveTask("read", "read", ("provider-read",), target="drive", effect=EffectClass.READ_ONLY_PROVIDER),),
        )
        permit = EffectPermit("permit-before", mission.mission_id, "read", "drive", EffectClass.READ_ONLY_PROVIDER, "route-a")

        def executor(*_):
            self.assertIn(permit.permit_id, self.fabric.consumed_permits)
            return {"state": "SUCCESS", "evidence_refs": ["readback"]}

        receipt = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=executor,
            route_fingerprint="route-a",
            permit=permit,
        )
        self.assertEqual(TaskState.SUCCESS, receipt.state)

    def test_failed_provider_dispatch_still_consumes_permit(self) -> None:
        mission = DirectiveMission(
            "failed-dispatch",
            "prevent permit replay",
            (DirectiveTask("read", "read", ("provider-read",), target="drive", effect=EffectClass.READ_ONLY_PROVIDER),),
        )
        permit = EffectPermit("permit-once", mission.mission_id, "read", "drive", EffectClass.READ_ONLY_PROVIDER, "route-a")
        failed = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=lambda *_: (_ for _ in ()).throw(RuntimeError("transport failed")),
            route_fingerprint="route-a",
            permit=permit,
        )
        self.assertEqual(TaskState.FAILURE, failed.state)
        self.assertIn(permit.permit_id, self.fabric.consumed_permits)
        self.fabric.reopen_task(mission, "read", changed_route_fingerprint="route-b")
        held = self.fabric.run_task(
            mission=mission,
            task_id="read",
            executor=lambda *_: {"state": "SUCCESS", "evidence_refs": ["readback"]},
            route_fingerprint="route-b",
            permit=permit,
        )
        self.assertEqual(TaskState.CONSTRAINT, held.state)

    def test_default_fleet_does_not_inherit_write_authority(self) -> None:
        mission = DirectiveMission(
            "write",
            "write provider",
            (DirectiveTask("write", "write", ("integration",), target="provider", effect=EffectClass.REVERSIBLE_WRITE),),
        )
        self.assertEqual(("write",), self.fabric.compile(mission).unresolved_tasks)

    def test_custom_write_worker_still_requires_guard_verifier_permit_and_proof(self) -> None:
        workers = (
            WorkerSpec("BUBBLES-OMEGA-CONTROLLER", "controller", WorkerKind.AGENT, ("orchestration",)),
            WorkerSpec("WRITE-AGENT", "writer", WorkerKind.AGENT, ("integration",), EffectClass.REVERSIBLE_WRITE),
        )
        fabric = BubblesOmegaAgentFabric(workers)
        mission = DirectiveMission(
            "write-custom",
            "write safely",
            (DirectiveTask("write", "write", ("integration",), target="provider", effect=EffectClass.REVERSIBLE_WRITE),),
        )
        permit_a = EffectPermit("write-a", mission.mission_id, "write", "provider", EffectClass.REVERSIBLE_WRITE, "route-a")
        no_guard = fabric.run_task(
            mission=mission,
            task_id="write",
            executor=lambda *_: {"state": "SUCCESS", "evidence_refs": ["provider-proof"]},
            route_fingerprint="route-a",
            permit=permit_a,
        )
        self.assertEqual(TaskState.CONSTRAINT, no_guard.state)
        self.assertIn("GUARD_REQUIRED", no_guard.note)
        fabric.reopen_task(mission, "write", changed_route_fingerprint="route-b")
        permit_b = EffectPermit("write-b", mission.mission_id, "write", "provider", EffectClass.REVERSIBLE_WRITE, "route-b")
        no_verifier = fabric.run_task(
            mission=mission,
            task_id="write",
            executor=lambda *_: {"state": "SUCCESS", "evidence_refs": ["provider-proof"]},
            route_fingerprint="route-b",
            permit=permit_b,
            guard=lambda _: (True, "ok"),
        )
        self.assertEqual(TaskState.CONSTRAINT, no_verifier.state)
        self.assertIn("VERIFIER_REQUIRED", no_verifier.note)
        fabric.reopen_task(mission, "write", changed_route_fingerprint="route-c")
        permit_c = EffectPermit("write-c", mission.mission_id, "write", "provider", EffectClass.REVERSIBLE_WRITE, "route-c")
        passed = fabric.run_task(
            mission=mission,
            task_id="write",
            executor=lambda *_: {"state": "SUCCESS", "evidence_refs": ["provider-proof"]},
            route_fingerprint="route-c",
            permit=permit_c,
            guard=lambda _: (True, "ok"),
            verifier=lambda *_: (True, "verified", ("independent-readback",)),
        )
        self.assertEqual(TaskState.SUCCESS, passed.state)
        self.assertIn("independent-readback", passed.evidence_refs)

    def test_guard_and_verifier_exceptions_fail_closed(self) -> None:
        mission = DirectiveMission("callback-errors", "callback errors", (DirectiveTask("x", "x", ("research",)),))
        guard_error = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="r1",
            guard=lambda _: (_ for _ in ()).throw(RuntimeError("secret guard details")),
        )
        self.assertEqual(TaskState.CONSTRAINT, guard_error.state)
        self.assertEqual("GUARD_ERROR:RuntimeError", guard_error.note)
        self.fabric.reopen_task(mission, "x", changed_route_fingerprint="r2")
        verifier_error = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="r2",
            verifier=lambda *_: (_ for _ in ()).throw(RuntimeError("secret verifier details")),
        )
        self.assertEqual(TaskState.CONSTRAINT, verifier_error.state)
        self.assertIn("VERIFIER_ERROR:RuntimeError", verifier_error.note)

    def test_receipt_does_not_persist_raw_task_payload(self) -> None:
        mission = DirectiveMission("privacy", "privacy", (DirectiveTask("x", "x", ("research",)),))
        receipt = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS", "private_payload": "do-not-persist", "answer": 42},
            route_fingerprint="r1",
        )
        self.assertEqual(TaskState.SUCCESS, receipt.state)
        self.assertNotIn("private_payload", receipt.result)
        self.assertFalse(receipt.result["payload_persisted"])
        self.assertEqual("do-not-persist", self.fabric.task_output(mission.mission_id, "x")["private_payload"])

    def test_idempotency_returns_same_success_receipt_within_one_mission(self) -> None:
        mission = DirectiveMission("idem", "once", (DirectiveTask("x", "x", ("research",), idempotency_key="same"),))
        calls = {"count": 0}

        def executor(*_):
            calls["count"] += 1
            return {"state": "SUCCESS"}

        one = self.fabric.run_task(mission=mission, task_id="x", executor=executor, route_fingerprint="r1")
        two = self.fabric.run_task(mission=mission, task_id="x", executor=executor, route_fingerprint="r2")
        self.assertEqual(one.receipt_id, two.receipt_id)
        self.assertEqual(1, calls["count"])

    def test_idempotency_does_not_collide_across_missions(self) -> None:
        calls = {"count": 0}

        def executor(*_):
            calls["count"] += 1
            return {"state": "SUCCESS"}

        one = DirectiveMission("mission-one", "one", (DirectiveTask("x", "x", ("research",), idempotency_key="same"),))
        two = DirectiveMission("mission-two", "two", (DirectiveTask("x", "x", ("research",), idempotency_key="same"),))
        self.fabric.run_task(mission=one, task_id="x", executor=executor, route_fingerprint="r1")
        self.fabric.run_task(mission=two, task_id="x", executor=executor, route_fingerprint="r1")
        self.assertEqual(2, calls["count"])

    def test_unchanged_failed_route_is_quarantined(self) -> None:
        mission = DirectiveMission("retry", "recover", (DirectiveTask("x", "x", ("research",)),))
        failed = self.fabric.run_task(mission=mission, task_id="x", executor=lambda *_: {"state": "FAILURE"}, route_fingerprint="bad-route")
        self.assertEqual(TaskState.FAILURE, failed.state)
        self.fabric.reopen_task(mission, "x", changed_route_fingerprint="new-route")
        held = self.fabric.run_task(mission=mission, task_id="x", executor=lambda *_: {"state": "SUCCESS"}, route_fingerprint="bad-route")
        self.assertEqual(TaskState.CONSTRAINT, held.state)
        self.assertIn("UNCHANGED_FAILED_ROUTE", held.note)

    def test_guard_and_verifier_fail_closed(self) -> None:
        mission = DirectiveMission("verify", "verify", (DirectiveTask("x", "x", ("research",)),))
        held = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="r1",
            guard=lambda _: (False, "REALITYGUARD_HOLD"),
        )
        self.assertEqual(TaskState.CONSTRAINT, held.state)
        self.fabric.reopen_task(mission, "x", changed_route_fingerprint="r2")
        held2 = self.fabric.run_task(
            mission=mission,
            task_id="x",
            executor=lambda *_: {"state": "SUCCESS"},
            route_fingerprint="r2",
            verifier=lambda *_: (False, "NO_SEMANTIC_READBACK", ("j1",)),
        )
        self.assertEqual(TaskState.CONSTRAINT, held2.state)
        self.assertIn("j1", held2.evidence_refs)

    def test_completion_requires_every_required_task_success(self) -> None:
        mission = self.mission()
        for task_id in ("discover", "build", "prove"):
            self.fabric.run_task(
                mission=mission,
                task_id=task_id,
                executor=lambda *_: {"state": "SUCCESS", "evidence_refs": [f"proof-{task_id}"]},
                route_fingerprint=f"route-{task_id}",
            )
        self.assertEqual(MissionState.COMPLETE, self.fabric.mission_state(mission))
        receipt = self.fabric.completion_receipt(mission)
        self.assertTrue(receipt["directive_complete"])
        self.assertEqual(3, len(receipt["proof_refs"]))

    def test_benchmark_snapshot_records_observed_agent_work(self) -> None:
        mission = DirectiveMission("metrics", "measure", (DirectiveTask("x", "x", ("research",)),))
        self.fabric.run_task(mission=mission, task_id="x", executor=lambda *_: {"state": "SUCCESS"}, route_fingerprint="r1")
        snapshot = self.fabric.benchmark_snapshot()
        self.assertEqual(1, snapshot["BUBBLES-OMEGA-SCOUT"]["attempts"])
        self.assertEqual(1.0, snapshot["BUBBLES-OMEGA-SCOUT"]["reliability"])


if __name__ == "__main__":
    unittest.main()
