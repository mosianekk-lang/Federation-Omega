from __future__ import annotations

import unittest

from benchmarking.cfbe_omega.kim_dataverse_l7_plus_freeze_v1 import source_feature_freeze


class KimDataverseLevel7PlusFreezeTests(unittest.TestCase):
    def test_feature_growth_is_frozen_for_admission(self) -> None:
        self.assertTrue(source_feature_freeze())


if __name__ == "__main__":
    unittest.main()
