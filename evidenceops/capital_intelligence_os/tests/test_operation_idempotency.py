import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from superior_logic.operations import OperationConflictError
from superior_logic.runtime import SuperiorLogicRuntime
from superior_logic.slrk import CapabilityContract, CapabilityState


class OperationIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "runtime.db"
        self.runtime = SuperiorLogicRuntime(self.db_path)

    def tearDown(self):
        self.runtime.close()
        self.tmp.cleanup()

    def test_mission_replay_returns_original_result_without_duplicate_state_or_event(self):
        operation_id = "op:mission:replay:0001"
        first = self.runtime.create_mission(
            "Kim Kagiso Mosiane",
            "Proceed atomically",
            operation_id=operation_id,
            principal="test-suite",
        )
        second = self.runtime.create_mission(
            "Kim Kagiso Mosiane",
            "Proceed atomically",
            operation_id=operation_id,
            principal="test-suite",
        )

        self.assertEqual(first, second)
        state = self.runtime.snapshot()
        self.assertEqual(1, state["mission_count"])
        self.assertEqual(1, state["event_count"])
        self.assertEqual(1, state["operation_count"])
        receipt = self.runtime.operation_receipt(operation_id)
        self.assertEqual(first, receipt["result"]["mission_id"])
        self.assertEqual("MISSION_CREATE", receipt["operation_type"])
        self.assertEqual("test-suite", receipt["principal"])
        self.assertTrue(state["event_chain_valid"])

    def test_operation_id_reuse_with_different_request_is_blocked(self):
        operation_id = "op:mission:conflict:0001"
        self.runtime.create_mission(
            "Kim Kagiso Mosiane",
            "Original instruction",
            operation_id=operation_id,
        )
        with self.assertRaises(OperationConflictError):
            self.runtime.create_mission(
                "Kim Kagiso Mosiane",
                "Different instruction",
                operation_id=operation_id,
            )

        self.assertEqual(1, self.runtime.snapshot()["mission_count"])
        self.assertEqual(1, self.runtime.snapshot()["event_count"])

    def test_capability_replay_does_not_duplicate_event(self):
        contract = CapabilityContract(
            capability_id="CAP-IDEMPOTENT",
            name="Idempotent capability",
            state=CapabilityState.EXECUTABLE_NOW,
        )
        operation_id = "op:capability:replay:0001"
        self.runtime.register_capability(contract, operation_id=operation_id)
        self.runtime.register_capability(contract, operation_id=operation_id)

        state = self.runtime.snapshot()
        self.assertEqual(1, state["capability_count"])
        self.assertEqual(1, state["event_count"])
        self.assertEqual(1, state["operation_count"])

    def test_concurrent_same_operation_id_produces_one_mutation(self):
        operation_id = "op:mission:concurrent:0001"

        def create(_: int) -> str:
            return self.runtime.create_mission(
                "Kim Kagiso Mosiane",
                "Concurrent replay",
                operation_id=operation_id,
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            mission_ids = list(pool.map(create, range(24)))

        self.assertEqual(1, len(set(mission_ids)))
        state = self.runtime.snapshot()
        self.assertEqual(1, state["mission_count"])
        self.assertEqual(1, state["event_count"])
        self.assertEqual(1, state["operation_count"])
        self.assertTrue(state["event_chain_valid"])

    def test_replay_survives_runtime_restart(self):
        operation_id = "op:mission:restart:0001"
        mission_id = self.runtime.create_mission(
            "Kim Kagiso Mosiane",
            "Restart-safe replay",
            operation_id=operation_id,
        )
        self.runtime.close()
        self.runtime = SuperiorLogicRuntime(self.db_path)

        replayed = self.runtime.create_mission(
            "Kim Kagiso Mosiane",
            "Restart-safe replay",
            operation_id=operation_id,
        )
        self.assertEqual(mission_id, replayed)
        state = self.runtime.snapshot()
        self.assertEqual(1, state["mission_count"])
        self.assertEqual(1, state["event_count"])
        self.assertEqual(1, state["operation_count"])
        self.assertTrue(state["event_chain_valid"])

    def test_receipt_failure_rolls_back_state_and_event(self):
        with patch.object(
            self.runtime.operation_journal,
            "record",
            side_effect=RuntimeError("injected_receipt_failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected_receipt_failure"):
                self.runtime.create_mission(
                    "Kim Kagiso Mosiane",
                    "Rollback receipt failure",
                    operation_id="op:mission:receiptfail:0001",
                )

        state = self.runtime.snapshot()
        self.assertEqual(0, state["mission_count"])
        self.assertEqual(0, state["event_count"])
        self.assertEqual(0, state["operation_count"])
        self.assertTrue(state["event_chain_valid"])


if __name__ == "__main__":
    unittest.main()
