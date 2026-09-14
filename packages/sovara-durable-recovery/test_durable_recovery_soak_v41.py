#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from run_durable_recovery_soak_v41 import (
    MINIMUM_CYCLES,
    run_tick,
    validate_ledger,
)


START = datetime(2026, 8, 22, 16, 0, tzinfo=timezone.utc)


class FakeCanary:
    def __init__(self, *, passing: bool = True) -> None:
        self.passing = passing
        self.calls = 0

    def __call__(self, _: Path) -> dict[str, object]:
        self.calls += 1
        proof = hashlib.sha256(f"proof-{self.calls}".encode()).hexdigest()
        head = hashlib.sha256(f"head-{self.calls}".encode()).hexdigest()
        return {
            "contract": "SOVARA_DURABLE_RECOVERY_CANARY_V40",
            "status": "PASS" if self.passing else "FAIL",
            "assertions": {"restartRecovery": self.passing},
            "proofSha256": proof,
            "finalEventChain": {"headSha256": head},
        }


class DurableRecoverySoakV41Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.state = root / "state.json"
        self.ledger = root / "ledger.jsonl"
        self.receipt = root / "receipt.json"

    def tick(self, at: datetime, runner: FakeCanary, **kwargs: object):
        return run_tick(
            state_path=self.state,
            ledger_path=self.ledger,
            receipt_path=self.receipt,
            now=at,
            start_at=START,
            canary_runner=runner,
            **kwargs,
        )

    def test_initial_cycle_runs_now_with_fixed_utc_schedule(self):
        runner = FakeCanary()
        receipt = self.tick(START, runner)
        self.assertEqual(receipt["status"], "RUNNING")
        self.assertEqual(receipt["cycleCount"], 1)
        self.assertEqual(receipt["lastCycle"]["scheduledAt"], "2026-08-22T16:00:00Z")
        self.assertTrue(receipt["sanitized"])

    def test_early_tick_does_not_run_a_cycle(self):
        runner = FakeCanary()
        self.tick(START, runner)
        receipt = self.tick(START + timedelta(minutes=59), runner)
        self.assertEqual(receipt["cycleCount"], 1)
        self.assertEqual(runner.calls, 1)

    def test_cycle_id_is_idempotent(self):
        runner = FakeCanary()
        first = self.tick(START, runner, cycle_id="cycle-owner-0")
        second = self.tick(START + timedelta(hours=1), runner, cycle_id="cycle-owner-0")
        self.assertEqual(first["ledgerHeadSha256"], second["ledgerHeadSha256"])
        self.assertEqual(runner.calls, 1)

    def test_auto_pass_requires_24_hours_and_25_passing_cycles(self):
        runner = FakeCanary()
        receipt = None
        for hour in range(MINIMUM_CYCLES):
            receipt = self.tick(START + timedelta(hours=hour), runner)
            if hour < 24:
                self.assertEqual(receipt["status"], "RUNNING")
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["cycleCount"], 25)
        self.assertEqual(receipt["passedCycles"], 25)
        self.assertEqual(receipt["expectedEndAt"], "2026-08-23T16:00:00Z")

    def test_failed_cycle_fails_closed(self):
        receipt = self.tick(START, FakeCanary(passing=False))
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["failedCycles"], 1)
        self.assertEqual(receipt["failureCode"], "CANARY_CYCLE_FAILED")

    def test_ledger_corruption_fails_closed_before_next_canary(self):
        runner = FakeCanary()
        self.tick(START, runner)
        value = self.ledger.read_text(encoding="utf-8").replace('"status":"PASS"', '"status":"FAIL"')
        self.ledger.write_text(value, encoding="utf-8")
        receipt = self.tick(START + timedelta(hours=1), runner)
        self.assertEqual(receipt["status"], "FAIL")
        self.assertEqual(receipt["failureCode"], "STATE_OR_LEDGER_CORRUPTION")
        self.assertEqual(runner.calls, 1)

    def test_valid_ledger_is_reconciled_after_state_write_interruption(self):
        runner = FakeCanary()
        first = self.tick(START, runner)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        state.update(
            cycleCount=0, passedCycles=0, failedCycles=0,
            ledgerHeadSha256="", lastCycleId=None,
        )
        self.state.write_text(json.dumps(state), encoding="utf-8")
        second = self.tick(START + timedelta(minutes=10), runner)
        self.assertEqual(second["cycleCount"], 1)
        self.assertEqual(second["ledgerHeadSha256"], first["ledgerHeadSha256"])
        self.assertEqual(runner.calls, 1)

    def test_hash_chain_validates_all_records(self):
        runner = FakeCanary()
        for hour in range(3):
            self.tick(START + timedelta(hours=hour), runner)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        records = validate_ledger(self.ledger, state)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[1]["prevSha256"], records[0]["eventSha256"])


if __name__ == "__main__":
    unittest.main()
