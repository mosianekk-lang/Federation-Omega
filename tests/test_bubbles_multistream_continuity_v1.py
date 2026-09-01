from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bubbles.chat_governor_omega3.continuity import (
    CommandEnvelope,
    CommandState,
    ContinuityLaneSpec,
    ContinuityLaneState,
    EffectClass,
    MultistreamContinuityFabric,
    PathRole,
    intent_sha256,
)


class MultistreamContinuityFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "continuity.sqlite3"
        self.fabric = MultistreamContinuityFabric(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def command(self, cid: str, *, priority: float = 50) -> CommandEnvelope:
        return CommandEnvelope(
            command_id=cid,
            mission_id=f"mission-{cid}",
            intent_sha256=intent_sha256(f"intent:{cid}"),
            priority=priority,
        )

    def lane(
        self,
        cid: str,
        lid: str,
        *,
        path: str = "p1",
        role: PathRole = PathRole.PRIMARY,
        effect: EffectClass = EffectClass.NO_EFFECT,
        permit: str = "",
        deps: tuple[str, ...] = (),
        group: str = "",
    ) -> ContinuityLaneSpec:
        return ContinuityLaneSpec(
            lane_id=lid,
            command_id=cid,
            mission_id=f"mission-{cid}",
            path_id=path,
            path_role=role,
            effect_class=effect,
            effect_permit_ref=permit,
            dependencies=deps,
            concurrency_group=group,
        )

    def test_new_command_is_additive_and_does_not_cancel_running_prior_work(self) -> None:
        self.fabric.add_command(self.command("old"), [self.lane("old", "old-a")], now=0)
        lease = self.fabric.lease_wave(worker_id="w1", max_lanes=1, lease_seconds=100, now=1)
        self.assertEqual(("old-a",), tuple(item.lane_id for item in lease))
        self.fabric.add_command(self.command("new"), [self.lane("new", "new-a")], now=2)
        snap = self.fabric.snapshot()
        commands = {item["command_id"]: item["state"] for item in snap["commands"]}
        lanes = {item["lane_id"]: item["state"] for item in snap["lanes"]}
        self.assertEqual(CommandState.ACTIVE.value, commands["old"])
        self.assertEqual(CommandState.ACTIVE.value, commands["new"])
        self.assertEqual(ContinuityLaneState.RUNNING.value, lanes["old-a"])
        self.assertEqual(ContinuityLaneState.READY.value, lanes["new-a"])

    def test_host_interruption_recovers_safe_lane_but_holds_possible_external_effect(self) -> None:
        self.fabric.add_command(
            self.command("c"),
            [
                self.lane("c", "safe"),
                self.lane(
                    "c", "external",
                    effect=EffectClass.REVERSIBLE_EXTERNAL,
                    permit="permit://bounded",
                ),
            ],
            now=0,
        )
        lease = self.fabric.lease_wave(worker_id="w", max_lanes=2, lease_seconds=10, now=1)
        self.assertEqual({"safe", "external"}, {item.lane_id for item in lease})
        recovered = self.fabric.reconcile_after_host_interrupt(now=12)
        self.assertEqual(("safe",), recovered["recovered_ready"])
        self.assertEqual(("external",), recovered["effect_readback_required"])
        states = {item["lane_id"]: item["state"] for item in self.fabric.snapshot()["lanes"]}
        self.assertEqual(ContinuityLaneState.READY.value, states["safe"])
        self.assertEqual(ContinuityLaneState.HOLD_READBACK.value, states["external"])

    def test_effect_readback_prevents_duplicate_effect_replay(self) -> None:
        self.fabric.add_command(
            self.command("c"),
            [self.lane("c", "e", effect=EffectClass.REVERSIBLE_EXTERNAL, permit="permit://one")],
            now=0,
        )
        self.fabric.lease_wave(worker_id="w", lease_seconds=5, now=1)
        self.fabric.reconcile_after_host_interrupt(now=7)
        self.fabric.record_effect_readback("e", effect_observed=True, result_ref="proof://receiver", now=8)
        self.assertEqual((), self.fabric.lease_wave(worker_id="w2", now=9))
        lane = self.fabric.snapshot()["lanes"][0]
        self.assertEqual(ContinuityLaneState.COMPLETE.value, lane["state"])
        self.assertEqual("proof://receiver", lane["result_ref"])

    def test_negative_readback_allows_retry_without_assuming_effect(self) -> None:
        self.fabric.add_command(
            self.command("c"),
            [self.lane("c", "e", effect=EffectClass.REVERSIBLE_EXTERNAL, permit="permit://one")],
            now=0,
        )
        self.fabric.lease_wave(worker_id="w", lease_seconds=5, now=1)
        self.fabric.reconcile_after_host_interrupt(now=7)
        self.fabric.record_effect_readback("e", effect_observed=False, now=8)
        leases = self.fabric.lease_wave(worker_id="w2", now=9)
        self.assertEqual(("e",), tuple(item.lane_id for item in leases))
        self.assertEqual(2, leases[0].attempt)

    def test_multistream_and_multipath_wave_uses_bounded_fairness(self) -> None:
        self.fabric.add_command(
            self.command("a", priority=90),
            [
                self.lane("a", "a-primary", path="route-a", role=PathRole.PRIMARY),
                self.lane("a", "a-challenger", path="route-b", role=PathRole.CHALLENGER),
            ],
            now=0,
        )
        self.fabric.add_command(
            self.command("b", priority=80),
            [self.lane("b", "b-primary", path="route-c", role=PathRole.PRIMARY)],
            now=0,
        )
        leases = self.fabric.lease_wave(
            worker_id="w", max_lanes=3, max_per_command=1, lease_seconds=30, now=1
        )
        self.assertEqual(2, len(leases))
        self.assertEqual({"a", "b"}, {item.command_id for item in leases})
        self.assertTrue(any(item.path_role in {"PRIMARY", "CHALLENGER"} for item in leases))

    def test_effect_lane_serialization_and_high_consequence_hold(self) -> None:
        self.fabric.add_command(
            self.command("a"),
            [
                self.lane("a", "e1", effect=EffectClass.REVERSIBLE_EXTERNAL, permit="permit://1"),
                self.lane("a", "e2", effect=EffectClass.REVERSIBLE_EXTERNAL, permit="permit://2"),
                self.lane("a", "high", effect=EffectClass.HIGH_CONSEQUENCE, permit="permit://owner"),
            ],
            now=0,
        )
        leases = self.fabric.lease_wave(worker_id="w", max_lanes=4, now=1)
        self.assertEqual(
            1,
            sum(item.effect_class == EffectClass.REVERSIBLE_EXTERNAL.value for item in leases),
        )
        self.assertNotIn("high", {item.lane_id for item in leases})

    def test_external_lane_without_permit_is_not_auto_leased(self) -> None:
        self.fabric.add_command(
            self.command("a"),
            [self.lane("a", "e1", effect=EffectClass.REVERSIBLE_EXTERNAL)],
            now=0,
        )
        self.assertEqual((), self.fabric.lease_wave(worker_id="w", now=1))

    def test_cancel_and_pause_require_explicit_control(self) -> None:
        self.fabric.add_command(self.command("a"), [self.lane("a", "a1")], now=0)
        with self.assertRaises(PermissionError):
            self.fabric.cancel_command("a")
        with self.assertRaises(PermissionError):
            self.fabric.pause_command("a")
        self.fabric.pause_command("a", explicit=True, now=1)
        self.assertEqual((), self.fabric.lease_wave(worker_id="w", now=2))
        self.fabric.resume_command("a", explicit=True, now=3)
        self.assertEqual(
            ("a1",),
            tuple(item.lane_id for item in self.fabric.lease_wave(worker_id="w", now=4)),
        )

    def test_cancel_running_external_preserves_readback_hold(self) -> None:
        self.fabric.add_command(
            self.command("a"),
            [
                self.lane("a", "external", effect=EffectClass.REVERSIBLE_EXTERNAL, permit="permit://1"),
                self.lane("a", "future-safe"),
            ],
            now=0,
        )
        leases = self.fabric.lease_wave(worker_id="w", max_lanes=1, now=1)
        self.assertEqual(("external",), tuple(item.lane_id for item in leases))
        self.fabric.cancel_command("a", explicit=True, now=2)
        snapshot = self.fabric.snapshot()
        command = snapshot["commands"][0]
        states = {item["lane_id"]: item["state"] for item in snapshot["lanes"]}
        self.assertEqual(CommandState.CANCELLED.value, command["state"])
        self.assertEqual(ContinuityLaneState.HOLD_READBACK.value, states["external"])
        self.assertEqual(ContinuityLaneState.CANCELLED.value, states["future-safe"])
        self.assertEqual((), self.fabric.lease_wave(worker_id="w2", now=3))
        self.fabric.record_effect_readback("external", effect_observed=False, now=4)
        states = {item["lane_id"]: item["state"] for item in self.fabric.snapshot()["lanes"]}
        self.assertEqual(ContinuityLaneState.CANCELLED.value, states["external"])
        self.assertEqual((), self.fabric.lease_wave(worker_id="w3", now=5))

    def test_cancelled_external_observed_effect_is_recorded_complete(self) -> None:
        self.fabric.add_command(
            self.command("a"),
            [self.lane("a", "external", effect=EffectClass.REVERSIBLE_EXTERNAL, permit="permit://1")],
            now=0,
        )
        self.fabric.lease_wave(worker_id="w", max_lanes=1, now=1)
        self.fabric.cancel_command("a", explicit=True, now=2)
        self.fabric.record_effect_readback(
            "external", effect_observed=True, result_ref="proof://provider", now=3
        )
        lane = self.fabric.snapshot()["lanes"][0]
        self.assertEqual(ContinuityLaneState.COMPLETE.value, lane["state"])
        self.assertEqual("proof://provider", lane["result_ref"])

    def test_dependency_failure_blocks_only_descendant_not_independent_stream(self) -> None:
        self.fabric.add_command(
            self.command("a"),
            [self.lane("a", "root"), self.lane("a", "child", deps=("root",))],
            now=0,
        )
        self.fabric.add_command(self.command("b"), [self.lane("b", "independent")], now=0)
        leases = self.fabric.lease_wave(worker_id="w", max_lanes=2, now=1)
        self.assertEqual({"root", "independent"}, {item.lane_id for item in leases})
        self.fabric.fail_lane("root", error="synthetic", worker_id="w", now=2)
        self.fabric.complete_lane("independent", result_ref="proof://b", worker_id="w", now=2)
        self.fabric.reconcile_after_host_interrupt(now=3)
        states = {item["lane_id"]: item["state"] for item in self.fabric.snapshot()["lanes"]}
        self.assertEqual(ContinuityLaneState.BLOCKED.value, states["child"])
        self.assertEqual(ContinuityLaneState.COMPLETE.value, states["independent"])

    def test_cross_process_reopen_preserves_streams_and_checkpoint(self) -> None:
        self.fabric.add_command(self.command("a"), [self.lane("a", "a1")], now=0)
        self.fabric.lease_wave(worker_id="w", lease_seconds=5, now=1)
        self.fabric.checkpoint_lane("a1", "checkpoint://1", worker_id="w", now=2)
        reopened = MultistreamContinuityFabric(self.db)
        recovered = reopened.reconcile_after_host_interrupt(now=7)
        self.assertEqual(("a1",), recovered["recovered_ready"])
        lane = reopened.snapshot()["lanes"][0]
        self.assertEqual("checkpoint://1", lane["checkpoint_ref"])

    def test_command_idempotency_conflict_fails_closed(self) -> None:
        self.fabric.add_command(self.command("a"), [], now=0)
        self.assertEqual(
            "IDEMPOTENT_COMMAND_REUSE",
            self.fabric.add_command(self.command("a"), [], now=1)["state"],
        )
        bad = CommandEnvelope("a", "mission-a", intent_sha256("different"))
        with self.assertRaises(ValueError):
            self.fabric.add_command(bad, [], now=2)

    def test_truth_boundary_never_claims_hidden_background_execution(self) -> None:
        receipt = self.fabric.receipt()
        self.assertFalse(receipt.host_background_execution_claimed)
        self.assertFalse(receipt.new_command_cancels_prior_work_by_default)
        self.assertTrue(receipt.explicit_control_required_for_pause_cancel_replace)


if __name__ == "__main__":
    unittest.main()
