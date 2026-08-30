from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from benchmarking.cfbe_omega.closure_matrix_v1 import (
    first_closure,
    load_matrix,
    plan_wave,
    validate_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "benchmarking" / "cfbe_omega" / "convergence_fabric_v2_capability_closure_matrix_v1.json"


class ConvergenceClosureMatrixTests(unittest.TestCase):
    def test_matrix_loads_and_registers_required_closure_cells(self):
        matrix = load_matrix(MATRIX_PATH)
        ids = {row["id"] for row in matrix["rows"]}
        self.assertEqual(len(ids), 18)
        self.assertTrue({"C01", "C02", "C03", "C05", "C07", "C12", "C16", "C18"}.issubset(ids))
        self.assertEqual(matrix["scheduler_policy"]["wip_limit_per_rail"], 2)
        self.assertTrue(matrix["scheduler_policy"]["blocked_lane_isolation"])

    def test_first_closure_is_capability_graph_slice(self):
        matrix = load_matrix(MATRIX_PATH)
        decision = first_closure(matrix)
        self.assertEqual(decision.capability_id, "C03")
        self.assertEqual(decision.closure_state, "INTEGRATE")
        self.assertIn("selector", decision.next_action.lower())
        self.assertFalse(decision.blockers)

    def test_wave_enforces_rail_wip_and_holds_external_or_data_gates(self):
        matrix = load_matrix(MATRIX_PATH)
        receipt = plan_wave(matrix)
        self.assertFalse(receipt.provider_effect_authorized)
        self.assertFalse(receipt.financial_effect_authorized)
        self.assertTrue(receipt.receipt_sha256)
        self.assertTrue(all(count <= 2 for count in receipt.selected_per_rail.values()))
        held = {item.capability_id: item for item in receipt.held}
        self.assertIn("DATA_NEEDED", held["C07"].blockers)
        self.assertIn("DATA_NEEDED", held["C12"].blockers)
        self.assertIn("PROVIDER_GATED", held["C14"].blockers)
        self.assertIn("VALUE_GATED", held["C15"].blockers)
        self.assertIn("DATA_NEEDED", held["C16"].blockers)

    def test_live_financial_authority_cannot_be_inherited(self):
        matrix = load_matrix(MATRIX_PATH)
        self.assertTrue(matrix["truth_boundary"]["live_financial_effect_requires_separate_explicit_authority"])
        omega = next(row for row in matrix["rows"] if row["id"] == "C16")
        self.assertIn("live capital separately explicitly authorized", omega["provider_gate"])
        receipt = plan_wave(matrix)
        self.assertFalse(receipt.financial_effect_authorized)

    def test_unknown_dependency_is_rejected(self):
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        broken = copy.deepcopy(matrix)
        broken["rows"][0]["dependencies"] = ["C99"]
        with self.assertRaisesRegex(ValueError, "UNKNOWN_DEPENDENCY"):
            validate_matrix(broken)

    def test_dependency_cycle_is_rejected(self):
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        broken = copy.deepcopy(matrix)
        row1 = next(row for row in broken["rows"] if row["id"] == "C01")
        row2 = next(row for row in broken["rows"] if row["id"] == "C02")
        row1["dependencies"] = ["C02"]
        row2["dependencies"] = ["C01"]
        with self.assertRaisesRegex(ValueError, "DEPENDENCY_CYCLE"):
            validate_matrix(broken)


if __name__ == "__main__":
    unittest.main()
