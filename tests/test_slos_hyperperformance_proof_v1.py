from __future__ import annotations

import unittest

from superior_logic.prove_hyperperformance_v1 import run


class SlosHyperperformanceProofTests(unittest.TestCase):
    def test_reference_proof_receipt(self) -> None:
        receipt = run()
        self.assertEqual(receipt["state"], "DETERMINISTIC_VERIFIED")
        self.assertEqual(receipt["gate_count"], receipt["passed_count"])
        self.assertFalse(receipt["provider_effect_performed"])
        self.assertFalse(receipt["speculative_provider_mutation"])
        self.assertFalse(receipt["stable_release_promoted"])


if __name__ == "__main__":
    unittest.main()
