from __future__ import annotations

import unittest

from superior_logic.prove_convergence_v1 import run


class SlosConvergenceProofTests(unittest.TestCase):
    def test_reference_proof_receipt(self):
        receipt = run()
        self.assertEqual("DETERMINISTIC_VERIFIED", receipt["state"])
        self.assertEqual(receipt["gate_count"], receipt["passed_count"])
        self.assertFalse(receipt["provider_effect_performed"])
        self.assertFalse(receipt["provider_authority_inherited"])
        self.assertFalse(receipt["stable_release_promoted"])


if __name__ == "__main__":
    unittest.main()
