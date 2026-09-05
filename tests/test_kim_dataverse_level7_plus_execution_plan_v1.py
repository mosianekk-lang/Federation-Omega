from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarking/cfbe_omega/KIM_DATAVERSE_LEVEL7_PLUS_EXECUTION_PLAN_V1_20260901.md"


class KimDataverseLevel7PlusExecutionPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PLAN.read_text(encoding="utf-8")

    def test_phoenix_repair_is_automatic_first_lane(self) -> None:
        self.assertIn("Repair serving-main Phoenix regression", self.text)

    def test_empirical_level7_is_continuously_qualified_not_self_declared(self) -> None:
        self.assertIn("do not self-declare operational Level 7", self.text)

    def test_wif_gate_is_lane_local_not_global_blocker(self) -> None:
        self.assertIn("does not block the automatic internal lanes above", self.text)


if __name__ == "__main__":
    unittest.main()
