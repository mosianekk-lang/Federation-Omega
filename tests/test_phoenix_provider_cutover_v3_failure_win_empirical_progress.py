from __future__ import annotations

import json
import unittest
from pathlib import Path


CONTROL = Path("governance/failure_win_v2_empirical_progress_20260827.json")


class FailureWinEmpiricalProgressAirlockTests(unittest.TestCase):
    def test_second_recovery_advances_repeat_and_soak_without_behavior_promotion(self):
        payload = json.loads(CONTROL.read_text(encoding="utf-8"))
        state = payload["federation_omega"]
        self.assertEqual(state["distinct_real_successes"], 2)
        self.assertEqual(state["required_real_successes"], 3)
        self.assertGreaterEqual(state["soak_seconds"], state["required_soak_seconds"])
        self.assertTrue(state["rollback"])
        self.assertFalse(state["behavior_proven"])
        self.assertEqual(payload["receiver_manifest"]["v2_behavior_proven"], 0)


if __name__ == "__main__":
    unittest.main()
