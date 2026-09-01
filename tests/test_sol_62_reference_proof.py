from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOL = ROOT / "sol_61_runtime"
if str(SOL) not in sys.path:
    sys.path.insert(0, str(SOL))

from prove_sol_62_runtime import run  # noqa: E402


class Sol62ReferenceProofTests(unittest.TestCase):
    def test_reference_runtime_receipt_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            receipt = run(Path(td) / "proof")
        self.assertEqual(receipt["status"], "SOL_6_2_REFERENCE_RUNTIME_VERIFIED")
        self.assertGreaterEqual(receipt["unit_tests_run"], 15)
        self.assertTrue(all(receipt["gates"].values()))
        self.assertTrue(receipt["truth_boundary"]["provider_effect_proof_binding_enforced_in_reference_runtime"])
        self.assertFalse(receipt["truth_boundary"]["provider_live_production_cutover"])


if __name__ == "__main__":
    unittest.main()
