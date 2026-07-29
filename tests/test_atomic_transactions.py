import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from superior_logic.runtime import SuperiorLogicRuntime
from superior_logic.slrk import (
    CapabilityContract,
    CapabilityState,
    EngineEnvironment,
    EnginePromotionRequest,
    FaultRecord,
    FaultSeverity,
    RouteState,
)


class AtomicMutationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = SuperiorLogicRuntime(Path(self.tmp.name) / "runtime.db")

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def count(self, table: str) -> int:
        allowed = {
            "missions",
            "events",
            "capability_contracts",
            "fault_records",
            "route_memory",
            "engine_promotions",
        }
        self.assertIn(table, allowed)
        return self.runtime.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    @staticmethod
    def fail_event(*args, **kwargs):
        raise RuntimeError("injected_event_failure")

    def test_mission_rolls_back_when_event_fails(self):
        with patch.object(
            self.runtime, "_insert_event_locked", side_effect=self.fail_event
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_event_failure"):
                self.runtime.create_mission("Kim Kagiso Mosiane", "atomic mission")

        self.assertEqual(0, self.count("missions"))
        self.assertEqual(0, self.count("events"))

    def test_capability_rolls_back_when_event_fails(self):
        contract = CapabilityContract(
            capability_id="CAP-ATOMIC-1",
            name="Atomic capability",
            state=CapabilityState.EXECUTABLE_NOW,
        )
        with patch.object(
            self.runtime, "_insert_event_locked", side_effect=self.fail_event
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_event_failure"):
                self.runtime.register_capability(contract)

        self.assertEqual(0, self.count("capability_contracts"))
        self.assertEqual(0, self.count("events"))

    def test_fault_and_route_roll_back_when_event_fails(self):
        record = FaultRecord(
            fault_id="FAULT-ATOMIC-1",
            layer_type="ROUTE_LAYER",
            detected_problem="Known route failed",
            banned_pattern="Blind retry",
            bypass_rule="Use a verified alternate route",
            severity=FaultSeverity.BLOCK,
            proof_required="Changed-condition readback",
            route_id="route-atomic-1",
        )
        with patch.object(
            self.runtime, "_insert_event_locked", side_effect=self.fail_event
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_event_failure"):
                self.runtime.register_fault(record)

        self.assertEqual(0, self.count("fault_records"))
        self.assertEqual(0, self.count("route_memory"))
        self.assertEqual(0, self.count("events"))

    def test_route_clear_rolls_back_when_event_fails(self):
        record = FaultRecord(
            fault_id="FAULT-ATOMIC-2",
            layer_type="ROUTE_LAYER",
            detected_problem="Known route failed",
            banned_pattern="Blind retry",
            bypass_rule="Use a verified alternate route",
            severity=FaultSeverity.BLOCK,
            proof_required="Changed-condition readback",
            route_id="route-atomic-2",
        )
        self.runtime.register_fault(record)
        event_count_before = self.count("events")

        with patch.object(
            self.runtime, "_insert_event_locked", side_effect=self.fail_event
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_event_failure"):
                self.runtime.clear_route(
                    "route-atomic-2", "route repaired", conditions_changed=True
                )

        self.assertEqual(
            RouteState.BANNED_UNLESS_CLEARED.value,
            self.runtime.route_state("route-atomic-2")["state"],
        )
        self.assertEqual(event_count_before, self.count("events"))

    def test_engine_promotion_rolls_back_when_event_fails(self):
        request = EnginePromotionRequest(
            engine_id="ENG-ATOMIC-1",
            target_environment=EngineEnvironment.SANDBOX,
            objective="Prove atomic promotion recording",
            risk_class="LOW",
            profile_complete=False,
            governor_attached=False,
            fault_rules_attached=False,
            proof_rules_attached=False,
            tests_passed=False,
            proof_ledger_written=False,
            risk_accepted=False,
            rollback_ready=False,
            status_path_ready=False,
            last_known_good_registered=False,
        )
        with patch.object(
            self.runtime, "_insert_event_locked", side_effect=self.fail_event
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_event_failure"):
                self.runtime.evaluate_engine_promotion(request)

        self.assertEqual(0, self.count("engine_promotions"))
        self.assertEqual(0, self.count("events"))

    def test_successful_mutations_keep_chain_valid(self):
        self.runtime.create_mission("Kim Kagiso Mosiane", "atomic mission")
        self.runtime.register_capability(
            CapabilityContract(
                capability_id="CAP-ATOMIC-2",
                name="Atomic capability",
                state=CapabilityState.EXECUTABLE_NOW,
            )
        )

        self.assertEqual(2, self.count("events"))
        self.assertEqual(1, self.count("missions"))
        self.assertEqual(1, self.count("capability_contracts"))
        self.assertTrue(self.runtime.verify_event_chain())


if __name__ == "__main__":
    unittest.main()
