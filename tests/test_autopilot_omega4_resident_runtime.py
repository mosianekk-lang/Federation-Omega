from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from federation import autopilot_omega4_resident_runtime as runtime


class AutoPilotOmega4ResidentRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "scheduler").mkdir(parents=True)
        self.output = self.root / "out"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_tasks(self, tasks: list[dict[str, object]]) -> None:
        (self.root / "scheduler/tasks.json").write_text(
            json.dumps({"version": "test", "tasks": tasks}, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _safe_handler(root: Path, output: Path, task: dict[str, object]) -> dict[str, object]:
        output.mkdir(parents=True, exist_ok=True)
        result = {"task_id": task["task_id"], "verified": True}
        (output / "safe-result.json").write_text(
            json.dumps(result, sort_keys=True) + "\n", encoding="utf-8"
        )
        return result

    def test_safe_hourly_task_executes_and_same_bucket_is_idempotent(self) -> None:
        self._write_tasks(
            [
                {
                    "task_id": "SAFE-001",
                    "title": "Safe resident check",
                    "cadence": "hourly",
                    "state": "READY",
                }
            ]
        )
        handlers = {
            "SAFE-001": runtime.TaskHandler("SAFE-001", self._safe_handler, "NO_EFFECT")
        }
        now = datetime(2026, 9, 5, 12, 15, tzinfo=timezone.utc)
        with mock.patch.object(runtime, "HANDLERS", handlers):
            receipt1, state1 = runtime.run_cycle(
                root=self.root,
                output_dir=self.output,
                now_utc=now,
                host_provider="test-host",
                host_run_id="1",
                source_sha="a" * 40,
                trigger="schedule",
            )
        self.assertEqual(receipt1["executed_count"], 1)
        self.assertEqual(receipt1["failure_count"], 0)
        self.assertFalse(receipt1["external_effect_attempted"])
        self.assertFalse(receipt1["provider_mutation_attempted"])
        self.assertEqual(state1["generation"], 1)

        previous = self.root / "previous-state.json"
        previous.write_text(json.dumps(state1), encoding="utf-8")
        with mock.patch.object(runtime, "HANDLERS", handlers):
            receipt2, state2 = runtime.run_cycle(
                root=self.root,
                output_dir=self.output,
                previous_state_path=previous,
                now_utc=now,
                host_provider="test-host",
                host_run_id="2",
                source_sha="a" * 40,
                trigger="schedule",
            )
        self.assertEqual(receipt2["executed_count"], 0)
        self.assertTrue(receipt2["previous_state_restored"])
        self.assertEqual(state2["generation"], 2)
        reasons = {row["reason"] for row in receipt2["skipped"]}
        self.assertIn("IDEMPOTENT_BUCKET_ALREADY_EXECUTED", reasons)

    def test_external_effect_handler_is_never_executed(self) -> None:
        self._write_tasks(
            [
                {
                    "task_id": "EXTSAFE-001",
                    "title": "External action",
                    "cadence": "hourly",
                    "state": "READY",
                }
            ]
        )
        handlers = {
            "EXTSAFE-001": runtime.TaskHandler(
                "EXTSAFE-001", self._safe_handler, "REVERSIBLE_EXTERNAL"
            )
        }
        with mock.patch.object(runtime, "HANDLERS", handlers):
            receipt, _ = runtime.run_cycle(
                root=self.root,
                output_dir=self.output,
                now_utc=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            )
        self.assertEqual(receipt["executed_count"], 0)
        self.assertEqual(receipt["failure_count"], 0)
        self.assertEqual(receipt["held"][0]["reason"], "RESIDENT_EFFECT_CLASS_NOT_ALLOWED")

    def test_ready_task_without_admitted_handler_is_held(self) -> None:
        self._write_tasks(
            [
                {
                    "task_id": "UNKNOWN-001",
                    "title": "Unknown work",
                    "cadence": "hourly",
                    "state": "READY",
                }
            ]
        )
        with mock.patch.object(runtime, "HANDLERS", {}):
            receipt, _ = runtime.run_cycle(
                root=self.root,
                output_dir=self.output,
                now_utc=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            )
        self.assertEqual(receipt["executed_count"], 0)
        self.assertEqual(receipt["held"][0]["reason"], "NO_RESIDENT_SAFE_HANDLER_ADMITTED")

    def test_invalid_previous_state_fails_closed(self) -> None:
        self._write_tasks([])
        previous = self.root / "bad-state.json"
        previous.write_text(json.dumps({"schema": "WRONG"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "STATE_SCHEMA_MISMATCH"):
            runtime.run_cycle(
                root=self.root,
                output_dir=self.output,
                previous_state_path=previous,
                now_utc=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
            )


if __name__ == "__main__":
    unittest.main()
