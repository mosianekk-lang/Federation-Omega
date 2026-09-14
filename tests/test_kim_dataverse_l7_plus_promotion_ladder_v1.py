from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_promotion_ladder_v1 import AutonomyMaturity, can_promote


class KimDataverseLevel7PlusPromotionLadderTests(unittest.TestCase):
    def test_promotion_is_one_step_and_evidence_bound(self) -> None:
        self.assertTrue(can_promote(AutonomyMaturity.SHADOW, AutonomyMaturity.ADVISORY, evidence_complete=True, authority_expansion=False))
        self.assertFalse(can_promote(AutonomyMaturity.SHADOW, AutonomyMaturity.OPERATIONAL, evidence_complete=True, authority_expansion=False))
        self.assertFalse(can_promote(AutonomyMaturity.ADVISORY, AutonomyMaturity.BOUNDED_CONTROL, evidence_complete=False, authority_expansion=False))

    def test_authority_expansion_never_promotes_through_autonomy_ladder(self) -> None:
        self.assertFalse(can_promote(AutonomyMaturity.ADVISORY, AutonomyMaturity.BOUNDED_CONTROL, evidence_complete=True, authority_expansion=True))


if __name__ == "__main__":
    unittest.main()
