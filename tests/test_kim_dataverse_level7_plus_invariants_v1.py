from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_level7_plus_invariants_v1 import level7_plus_invariants


class KimDataverseLevel7PlusInvariantTests(unittest.TestCase):
    def test_required_constitutional_invariants_are_present_and_unique(self) -> None:
        invariants = level7_plus_invariants()
        self.assertEqual(len(invariants), len(set(invariants)))
        for required in (
            "INTELLIGENCE_DOES_NOT_INHERIT_AUTHORITY",
            "SOL_REMAINS_SINGLE_CONSTITUTIONAL_KERNEL",
            "SELF_RESOLVABLE_MAINTENANCE_DOES_NOT_INTERRUPT_OWNER",
            "CHAT_IS_NOT_REQUIRED_PERSISTENT_CARRIER",
            "LEVEL7_REQUIRES_EMPIRICAL_OPERATION",
        ):
            self.assertIn(required, invariants)


if __name__ == "__main__":
    unittest.main()
