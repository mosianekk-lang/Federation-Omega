from __future__ import annotations

import unittest

from repair import AutonomousRepairFabric, RepairCandidate


class AutonomousRepairFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fabric = AutonomousRepairFabric(recurrence_threshold=3)
        self.candidate = RepairCandidate(
            repair_id="repair-1",
            incident_class="TRANSIENT",
            change_set=("increase-backoff",),
            expected_effects={"error_rate": 0.2},
            rollback_steps=("restore-backoff",),
        )

    def test_recurrence_and_synthesis(self) -> None:
        for _ in range(2):
            self.assertFalse(self.fabric.record_failure("TRANSIENT", "sig-a")["recurrent"])
        self.assertTrue(self.fabric.record_failure("TRANSIENT", "sig-a")["recurrent"])
        ranked = self.fabric.synthesise("TRANSIENT", "sig-a", [self.candidate])
        self.assertEqual(ranked[0].repair_id, "repair-1")

    def test_shadow_differential_rollback_canary_and_promotion(self) -> None:
        shadow = self.fabric.shadow_execute(self.candidate, lambda _: {"passed": True, "error_rate": 0.01})
        differential = self.fabric.differential_validate(
            {"latency": 100.0}, {"latency": 102.0}, {"latency": 5.0}
        )
        rollback = self.fabric.rehearse_rollback(self.candidate, lambda steps: steps == ("restore-backoff",))
        canary = self.fabric.canary_validate({"error_rate": 0.01, "success_rate": 0.99}, {
            "error_rate": ("LTE", 0.05), "success_rate": ("GTE", 0.98)
        })
        receipt = self.fabric.evaluate_promotion(
            self.candidate,
            shadow=shadow,
            differential=differential,
            rollback=rollback,
            canary=canary,
            proposer="planner",
            executor="worker",
            certifier="auditor",
        )
        self.assertEqual(receipt.state, "PROMOTION_ELIGIBLE")
        self.assertEqual(self.fabric.promote(self.candidate, receipt)["state"], "PROMOTED")
        self.assertEqual(self.fabric.promote(self.candidate, receipt)["state"], "PROMOTED")

    def test_failed_gate_denies_promotion(self) -> None:
        receipt = self.fabric.evaluate_promotion(
            self.candidate,
            shadow={"passed": True, "mutated_live_state": False},
            differential={"passed": False},
            rollback={"passed": True},
            canary={"passed": True},
            proposer="planner",
            executor="worker",
            certifier="auditor",
        )
        self.assertEqual(receipt.state, "PROMOTION_DENIED")
        with self.assertRaisesRegex(RuntimeError, "REPAIR_NOT_ELIGIBLE"):
            self.fabric.promote(self.candidate, receipt)

    def test_controller_self_modification_requires_owner_and_separation(self) -> None:
        controller = RepairCandidate(
            repair_id="controller-1",
            incident_class="LOGIC",
            change_set=("change-controller-policy",),
            expected_effects={"reliability": 0.1},
            rollback_steps=("restore-controller-policy",),
            risk="HIGH",
            controller_change=True,
        )
        base = dict(
            shadow={"passed": True, "mutated_live_state": False},
            differential={"passed": True},
            rollback={"passed": True},
            canary={"passed": True},
            proposer="planner",
            executor="worker",
            certifier="auditor",
        )
        self.assertEqual(self.fabric.evaluate_promotion(controller, **base).state, "PROMOTION_DENIED")
        self.assertEqual(self.fabric.evaluate_promotion(controller, owner_authorised=True, **base).state, "PROMOTION_ELIGIBLE")


if __name__ == "__main__":
    unittest.main()
